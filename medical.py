import spacy
import streamlit as st
from langchain_community.llms import Ollama
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
import PyPDF2
import io

# Load the standard English model
nlp = spacy.load("en_core_web_lg")

# Initialize Ollama
llm = OllamaLLM(model="llama2")

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

def main():
    st.title("Medical Report Analysis System")
    
    # Input section
    st.header("Input")
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
                # Extract text from PDF
                user_input = extract_text_from_pdf(uploaded_file)
                
                # Show extracted text with option to edit
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
                # Extract keywords
                keywords = extract_medical_keywords(user_input)
                
                # Generate summary
                summary = generate_summary(keywords)
                
                # Generate recommendations
                recommendations = generate_recommendations(summary)
                
                # Display results
                st.header("Analysis Results")
                
                st.subheader("Detailed Recommendations")
                st.markdown(recommendations)
                
                st.warning("""
                IMPORTANT MEDICAL DISCLAIMER: This analysis is for informational purposes only 
                and should not be considered medical advice. The medication suggestions are 
                examples of commonly used treatments, but may not be suitable for your specific 
                condition. Always consult with a healthcare professional before starting any 
                medication or treatment plan. They will provide proper diagnosis, dosage, and 
                consider your personal medical history and potential drug interactions.
                """)
            
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
                st.info("Please try again with different input or contact support if the issue persists.")

if __name__ == "__main__":
    main()