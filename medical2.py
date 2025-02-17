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

# User authentication functions
def create_user(username, password):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                 (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('medical_app.db')
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result and result[1] == hash_password(password):
        return result[0]  # Return user_id
    return None

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