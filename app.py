import streamlit as st
import openai
from resume_utils import extract_text_from_pdf, extract_text_from_docx

# Streamlit page config
st.set_page_config(page_title="JD vs Resume Checker", layout="wide")
st.title("📄 JD vs Resume Relevance Checker")

# Initialize OpenAI client using secure key from secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Input fields
jd = st.text_area("Paste Job Description", height=300)
resume_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])

# Extract only experience/projects section from resume text
def extract_relevant_experience(text):
    lines = text.splitlines()
    keep = []
    capture = False
    for line in lines:
        if "experience" in line.lower() or "projects" in line.lower():
            capture = True
        if capture:
            keep.append(line)
    return "\n".join(keep[-1000:])  # just last 1000 lines in case it's long

# Use OpenAI to evaluate resume vs JD
def check_relevance(jd, resume_exp):
    prompt = f"""
You are a smart resume screening assistant.

Compare the following job description and resume experience/projects only (ignore summary or objective).

1. Rate the resume's relevance to the job out of 10, with a brief explanation.
2. Suggest 3–5 questions to verify if the candidate's experience claims are true.
3. Suggest 3–5 questions to assess whether the candidate is a good fit for the JD.

Job Description:
{jd}

Resume Experience/Projects:
{resume_exp}

Format your answer like this:
Relevance Score: X/10
Explanation: ...
Truth Check Questions:
1. ...
Fit Check Questions:
1. ...
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    return response.choices[0].message.content

# Run on button click
if st.button("Check Relevance"):
    if jd and resume_file:
        if resume_file.name.endswith(".pdf"):
            raw_resume = extract_text_from_pdf(resume_file)
        else:
            raw_resume = extract_text_from_docx(resume_file)

        resume_exp = extract_relevant_experience(raw_resume)

        if not resume_exp.strip():
            st.warning("Couldn't extract experience/projects section from the resume.")
        else:
            with st.spinner("Analyzing..."):
                result = check_relevance(jd, resume_exp)
                st.markdown(result)
    else:
        st.warning("Please provide both a Job Description and a Resume.")
