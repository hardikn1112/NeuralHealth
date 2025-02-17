import spacy
import streamlit as st
from langchain_community.llms import Ollama
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
import PyPDF2
import io
import sqlite3
import hashlib
from datetime import datetime
import os

def hash_password(password):
    """Hash a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_history(user_id):
    """Retrieve analysis history for a user."""
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        SELECT 
            analysis_date,
            medical_terms,
            summary,
            recommendations,
            status,
            id,
            doctor_notes
        FROM analysis_history 
        WHERE user_id = ?
        ORDER BY analysis_date DESC
    """, (user_id,))
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Create doctors table
    c.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            full_name TEXT NOT NULL,
            specialization TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create doctor-patient relationships table
    c.execute('''
        CREATE TABLE IF NOT EXISTS doctor_patient (
            doctor_id INTEGER,
            patient_id INTEGER,
            assignment_date DATETIME,
            PRIMARY KEY (doctor_id, patient_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (patient_id) REFERENCES users (id)
        )
    ''')
    
    # Create analysis history table with doctor approval status
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            analysis_date DATETIME,
            medical_terms TEXT,
            summary TEXT,
            recommendations TEXT,
            doctor_id INTEGER,
            status TEXT DEFAULT 'pending',
            doctor_notes TEXT,
            last_modified DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (id),
      ''')
    history = c.fetchall()
    conn.close()
    return history

def patient_interface():
    """Handle patient view and interactions."""
    st.title("Medical Report Analysis System")
    
    # Main navigation
    nav_option = st.sidebar.radio("Navigation", ["New Analysis", "History"])
    
    if nav_option == "New Analysis":
        st.header("New Analysis")
        input_option = st.radio(
            "Choose input method:",
            ("Type Text", "Upload File")
        )
        
        if input_option == "Type Text":
            user_input = st.text_area("Enter your medical concerns or report:", height=200)
        else:
            uploaded_file = st.file_uploader("Upload medical report (PDF format)", type=['pdf'])
            if uploaded_file:
                try:
                    user_input = extract_text_from_pdf(uploaded_file)
                    st.subheader("Extracted Text from PDF")
                    user_input = st.text_area("You can edit the extracted text if needed:", 
                                            value=user_input, 
                                            height=200)
                except Exception as e:
                    st.error(f"Error processing PDF: {str(e)}")
                    user_input = ""
            else:
                user_input = ""
        
        if st.button("Analyze") and user_input:
            with st.spinner("Analyzing..."):
                try:
                    keywords = extract_medical_keywords(user_input)
                    summary = generate_summary(keywords)
                    recommendations = generate_recommendations(summary)
                    
                    # Save analysis to history
                    save_analysis(
                        st.session_state.user_id,
                        ", ".join(keywords),
                        summary,
                        recommendations
                    )
                    
                    # Display results
                    st.header("Analysis Results")
                    
                    st.subheader("Extracted Medical Terms")
                    if keywords:
                        st.write(", ".join(keywords))
                    else:
                        st.write("No specific medical terms were identified.")
                    
                    st.subheader("Summary")
                    st.write(summary)
                    
                    st.subheader("Detailed Recommendations")
                    st.markdown(recommendations)
                    
                    st.warning("""
                    IMPORTANT MEDICAL DISCLAIMER: This analysis is for informational purposes only 
                    and should not be considered medical advice. The medication suggestions are 
                    examples of commonly used treatments, but may not be suitable for your specific 
                    condition. Always consult with a healthcare professional before starting any 
                    medication or treatment plan.
                    """)
                
                except Exception as e:
                    st.error(f"An error occurred during analysis: {str(e)}")
                    st.info("Please try again with different input or contact support if the issue persists.")
    
    else:  # History page
        st.header("Analysis History")
        history = get_user_history(st.session_state.user_id)
        
        if not history:
            st.info("No analysis history found")
        else:
            for i, (date, terms, summary, recommendations, status, analysis_id, doctor_notes) in enumerate(history):
                with st.expander(f"Analysis from {date}"):
                    st.subheader("Status")
                    status_color = {
                        'pending': 'blue',
                        'approved': 'green',
                        'disapproved': 'red'
                    }.get(status, 'gray')
                    st.markdown(f"<p style='color: {status_color};'>Status: {status.upper()}</p>", 
                              unsafe_allow_html=True)
                    
                    st.subheader("Medical Terms")
                    st.write(terms)
                    
                    st.subheader("Summary")
                    st.write(summary)
                    
                    st.subheader("Recommendations")
                    st.markdown(recommendations)
                    
                    if doctor_notes:
                        st.subheader("Doctor's Notes")
                        st.info(doctor_notes)

def save_analysis(user_id, medical_terms, summary, recommendations):
    """Save analysis results to database."""
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO analysis_history 
        (user_id, analysis_date, medical_terms, summary, recommendations, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, datetime.now(), medical_terms, summary, recommendations, 'pending'))
    conn.commit()
    conn.close()


# Load the standard English model
nlp = spacy.load("en_core_web_lg")

# Initialize Ollama
llm = OllamaLLM(model="llama2")

# Database initialization
def init_db():
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Create history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            analysis_date DATETIME,
            medical_terms TEXT,
            summary TEXT,
            recommendations TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Enhanced user functions
def create_user(username, password, role='patient'):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                 (username, hash_password(password), role))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def create_doctor(user_id, full_name, specialization):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO doctors (user_id, full_name, specialization) VALUES (?, ?, ?)",
                 (user_id, full_name, specialization))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("SELECT id, password, role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result and result[1] == hash_password(password):
        return {'id': result[0], 'role': result[2]}
    return None

def assign_doctor(doctor_id, patient_id):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO doctor_patient (doctor_id, patient_id, assignment_date) VALUES (?, ?, ?)",
                 (doctor_id, patient_id, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_doctor_patients(doctor_id):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username 
        FROM users u 
        JOIN doctor_patient dp ON u.id = dp.patient_id 
        WHERE dp.doctor_id = ?
    """, (doctor_id,))
    patients = c.fetchall()
    conn.close()
    return patients

def get_doctor_id(user_id):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("SELECT id FROM doctors WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_analysis_status(analysis_id, status, doctor_notes):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        UPDATE analysis_history 
        SET status = ?, doctor_notes = ?, last_modified = ?
        WHERE id = ?
    """, (status, doctor_notes, datetime.now(), analysis_id))
    conn.commit()
    conn.close()

# Doctor interface
def doctor_interface():
    st.title("Doctor's Dashboard")
    doctor_id = get_doctor_id(st.session_state.user_id)
    
    if not doctor_id:
        st.error("Doctor account not properly configured")
        return
    
    # Get list of assigned patients
    patients = get_doctor_patients(doctor_id)
    
    if not patients:
        st.info("No patients assigned yet")
        return
    
    # Patient selector
    selected_patient = st.selectbox(
        "Select Patient",
        patients,
        format_func=lambda x: x[1]  # Show username
    )
    
    if selected_patient:
        st.header(f"Patient: {selected_patient[1]}")
        
        # Get patient's analysis history
        history = get_user_history(selected_patient[0])
        
        for analysis in history:
            with st.expander(f"Analysis from {analysis[0]}"):
                st.subheader("Medical Terms")
                st.write(analysis[1])
                
                st.subheader("Summary")
                st.write(analysis[2])
                
                st.subheader("Recommendations")
                st.markdown(analysis[3])
                
                # Status and notes
                current_status = analysis[4]
                st.subheader("Review")
                new_status = st.selectbox(
                    "Status",
                    ["pending", "approved", "disapproved"],
                    index=["pending", "approved", "disapproved"].index(current_status),
                    key=f"status_{analysis[5]}"
                )
                
                doctor_notes = st.text_area(
                    "Doctor's Notes",
                    value=analysis[6] if analysis[6] else "",
                    key=f"notes_{analysis[5]}"
                )
                
                if st.button("Update Review", key=f"update_{analysis[5]}"):
                    update_analysis_status(analysis[5], new_status, doctor_notes)
                    st.success("Review updated successfully")

# Modified main function to include doctor registration and interface
def main():
    init_db()
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
        st.session_state.role = None
    
    if st.session_state.user_id is None:
        tab1, tab2, tab3 = st.tabs(["Patient Login", "Doctor Login", "Register"])
        
        with tab1:
            st.header("Patient Login")
            username = st.text_input("Username", key="patient_login_username")
            password = st.text_input("Password", type="password", key="patient_login_password")
            
            if st.button("Login", key="patient_login"):
                user = verify_user(username, password)
                if user and user['role'] == 'patient':
                    st.session_state.user_id = user['id']
                    st.session_state.role = 'patient'
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with tab2:
            st.header("Doctor Login")
            username = st.text_input("Username", key="doctor_login_username")
            password = st.text_input("Password", type="password", key="doctor_login_password")
            
            if st.button("Login", key="doctor_login"):
                user = verify_user(username, password)
                if user and user['role'] == 'doctor':
                    st.session_state.user_id = user['id']
                    st.session_state.role = 'doctor'
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with tab3:
            st.header("Register")
            reg_role = st.selectbox("Register as", ["Patient", "Doctor"])
            new_username = st.text_input("Username", key="reg_username")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            if reg_role == "Doctor":
                full_name = st.text_input("Full Name")
                specialization = st.text_input("Specialization")
            
            if st.button("Register"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters long")
                else:
                    user_id = create_user(new_username, new_password, 
                                        'doctor' if reg_role == "Doctor" else 'patient')
                    if user_id:
                        if reg_role == "Doctor":
                            if create_doctor(user_id, full_name, specialization):
                                st.success("Doctor registration successful! Please login.")
                            else:
                                st.error("Error creating doctor profile")
                        else:
                            st.success("Patient registration successful! Please login.")
                    else:
                        st.error("Username already exists")
        
        return
    
    # Logout button in sidebar
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.role = None
        st.rerun()
    
    # Route to appropriate interface
    if st.session_state.role == 'doctor':
        doctor_interface()
    else:
        patient_interface()


def save_analysis(user_id, medical_terms, summary, recommendations):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO analysis_history 
        (user_id, analysis_date, medical_terms, summary, recommendations)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, datetime.now(), medical_terms, summary, recommendations))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("""
        SELECT analysis_date, medical_terms, summary, recommendations 
        FROM analysis_history 
        WHERE user_id = ?
        ORDER BY analysis_date DESC
    """, (user_id,))
    history = c.fetchall()
    conn.close()
    return history

# Previous functions remain the same
def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file."""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_medical_keywords(text):
    """Extract medical entities from text using spaCy."""
    doc = nlp(text)
    
    # Define medical-related labels that are available in the standard model
    medical_labels = {'DISEASE', 'CONDITION', 'SYMPTOM', 'TREATMENT', 
                     'CHEMICAL', 'MEDICINE', 'BODY_PART'}
    
    # Extract entities that might be medical-related
    medical_entities = []
    
    # Use standard entities
    for ent in doc.ents:
        # Include specific entity types and any capitalized terms that might be medical
        if (ent.label_ in ['ORG', 'GPE'] and any(word.isupper() for word in ent.text.split())) or \
           ent.label_ == 'CONDITION' or \
           (len(ent.text.split()) <= 3 and ent.text[0].isupper()):
            medical_entities.append(ent.text)
    
    # Add noun chunks that might be symptoms or conditions
    for chunk in doc.noun_chunks:
        # Look for medical-related words in the chunk
        if any(token.text.lower() in ['pain', 'ache', 'discomfort', 'swelling', 'fever', 
                                    'infection', 'inflammation', 'disease', 'syndrome', 
                                    'condition', 'symptom', 'treatment'] 
               for token in chunk):
            medical_entities.append(chunk.text)
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(medical_entities))

def generate_summary(keywords):
    """Generate a summary paragraph from extracted keywords."""
    if not keywords:
        return "No specific medical terms were identified in the input."
    return f"Based on the analysis, the key medical conditions and symptoms include: {', '.join(keywords)}."

def generate_recommendations(summary):
    """Generate medical and lifestyle recommendations using Ollama."""
    prompt_template = """
    Based on the following medical summary, provide detailed recommendations in these categories:

    1. Specific Medications:
    - List common over-the-counter medications with their generic and brand names
    - Mention typical dosage forms (tablets, capsules, etc.)
    - Include common medication classes that doctors might prescribe
    
    2. Alternative Treatments:
    - List specific supplements and natural remedies with dosages
    - Mention specific herbal medicines commonly used
    
    3. Home Remedies:
    - Provide detailed recipes or preparation methods
    - Include specific ingredients and their quantities
    - Mention how often to apply/use each remedy
    
    4. Lifestyle Modifications:
    - Specific dietary changes with food examples
    - Exact exercise recommendations with duration and frequency
    - Precise sleep and stress management techniques
    
    Format each section clearly with bullet points and include specific examples.
    Important: Begin your response with a clear medical disclaimer.

    Medical Summary: {summary}
    
    Response:
    """
    
    prompt = PromptTemplate(
        input_variables=["summary"],
        template=prompt_template
    )
    
    response = llm(prompt.format(summary=summary))
    return response


def login_page():
    st.title("Medical Report Analysis System")
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    
    if st.session_state.user_id is None:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.header("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login"):
                user_id = verify_user(username, password)
                if user_id:
                    st.session_state.user_id = user_id
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with tab2:
            st.header("Register")
            new_username = st.text_input("Username", key="reg_username")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            if st.button("Register"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters long")
                else:
                    if create_user(new_username, new_password):
                        st.success("Registration successful! Please login.")
                    else:
                        st.error("Username already exists")
        
        return False
    
    return True

def main():
    # Initialize database
    init_db()
    
    # Show login page first
    if not login_page():
        return
    
    # Main navigation
    nav_option = st.sidebar.radio("Navigation", ["New Analysis", "History"])
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.rerun()
    
    if nav_option == "New Analysis":
        st.header("New Analysis")
        # Previous analysis code here
        input_option = st.radio(
            "Choose input method:",
            ("Type Text", "Upload File")
        )
        
        if input_option == "Type Text":
            user_input = st.text_area("Enter your medical concerns or report:", height=200)
        else:
            uploaded_file = st.file_uploader("Upload medical report (PDF format)", type=['pdf'])
            if uploaded_file:
                try:
                    user_input = extract_text_from_pdf(uploaded_file)
                    st.subheader("Extracted Text from PDF")
                    user_input = st.text_area("You can edit the extracted text if needed:", 
                                            value=user_input, 
                                            height=200)
                except Exception as e:
                    st.error(f"Error processing PDF: {str(e)}")
                    user_input = ""
            else:
                user_input = ""
        
        if st.button("Analyze") and user_input:
            with st.spinner("Analyzing..."):
                try:
                    keywords = extract_medical_keywords(user_input)
                    summary = generate_summary(keywords)
                    recommendations = generate_recommendations(summary)
                    
                    # Save analysis to history
                    save_analysis(
                        st.session_state.user_id,
                        ", ".join(keywords),
                        summary,
                        recommendations
                    )
                    
                    # Display results
                    st.header("Analysis Results")

                    st.subheader("Detailed Recommendations")
                    st.markdown(recommendations)
                    
                    st.warning("""
                    IMPORTANT MEDICAL DISCLAIMER: This analysis is for informational purposes only 
                    and should not be considered medical advice. The medication suggestions are 
                    examples of commonly used treatments, but may not be suitable for your specific 
                    condition. Always consult with a healthcare professional before starting any 
                    medication or treatment plan.
                    """)
                
                except Exception as e:
                    st.error(f"An error occurred during analysis: {str(e)}")
                    st.info("Please try again with different input or contact support if the issue persists.")
    
    else:  # History page
        st.header("Analysis History")
        history = get_user_history(st.session_state.user_id)
        
        if not history:
            st.info("No analysis history found")
        else:
            for i, (date, terms, summary, recommendations) in enumerate(history):
                with st.expander(f"Analysis from {date}"):
                    
                    st.subheader("Recommendations")
                    st.markdown(recommendations)

if __name__ == "__main__":
    main()