
import streamlit as st
import openai
import pandas as pd
from resume_utils import extract_text_from_pdf, extract_text_from_docx
from io import StringIO
import docx
import pdfplumber

st.set_page_config(page_title="JD vs Resume Agent", layout="wide")
st.title("📄 JD vs Resume Relevance Agent")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.markdown("### 🔁 Use the tabs below to (1) Score resumes and (2) Generate interview questions")

tab1, tab2 = st.tabs(["1️⃣ Score Resumes", "2️⃣ Generate Interview Questions"])

# Extract relevant sections from resume
def extract_relevant_experience(text):
    lines = text.splitlines()
    keep = []
    capture = False
    for line in lines:
        if "experience" in line.lower() or "projects" in line.lower():
            capture = True
        if capture:
            keep.append(line)
    return "\n".join(keep[-1000:])

def get_score(jd, resume_exp):
    prompt = f"""
Compare the following resume experience against the job description and rate the relevance from 1 to 10. Return only:

Score: X
Reason: ...

Job Description:
{jd}

Resume:
{resume_exp}
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    content = response.choices[0].message.content
    usage = response.usage.total_tokens if hasattr(response, "usage") else 0
    try:
        score_line = next(line for line in content.splitlines() if "Score:" in line)
        reason_line = next(line for line in content.splitlines() if "Reason:" in line)
        score = float(score_line.split(":")[1].strip())
        reason = reason_line.split(":", 1)[1].strip()
    except:
        score, reason = 0, "Could not parse"
    return score, reason, usage

def get_question_blocks(jd, resume_exp):
    prompt = f"""
Generate two sets of interview questions based on the job description and resume experience.

Set 1: Truth Check Questions  
- 3–5 questions that help verify if the candidate truly did what they claimed  
- Include short cues: "What to listen for"

Set 2: Fit Check Questions  
- 3–5 questions to assess whether the candidate can perform well in the role  
- Include short cues: "What to listen for"

Format:
Truth Check Questions:
1. <question>
   What to listen for: <cue>

...

Fit Check Questions:
1. <question>
   What to listen for: <cue>

Job Description:
{jd}

Resume:
{resume_exp}
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    content = response.choices[0].message.content
    usage = response.usage.total_tokens if hasattr(response, "usage") else 0
    try:
        truth_section = content.split("Fit Check Questions:")[0].strip()
        fit_section = content.split("Fit Check Questions:")[1].strip()
    except:
        truth_section = "Could not parse questions"
        fit_section = "Could not parse questions"
    return truth_section, fit_section, usage

with tab1:
    st.subheader("Step 1: Upload JD and Score Resumes")
    jd_text = ""
    jd_file = st.file_uploader("Upload JD (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"], key="jd_file_score")
    if jd_file:
        if jd_file.name.endswith(".pdf"):
            with pdfplumber.open(jd_file) as pdf:
                jd_text = "\n".join([page.extract_text() for page in pdf.pages])
        elif jd_file.name.endswith(".docx"):
            doc = docx.Document(jd_file)
            jd_text = "\n".join([para.text for para in doc.paragraphs])
        else:
            jd_text = StringIO(jd_file.getvalue().decode("utf-8")).read()
    else:
        jd_text = st.text_area("Or paste JD here", height=200)

    resume_files = st.file_uploader("Upload resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)
    if st.button("Run Scoring"):
        if jd_text and resume_files:
            results, total_tokens = [], 0
            for file in resume_files:
                if file.name.endswith(".pdf"):
                    raw_text = extract_text_from_pdf(file)
                else:
                    raw_text = extract_text_from_docx(file)

                if not raw_text or raw_text.strip() == "":
                    score, reason, tokens_used = 0, "File not readable", 0
                else:
                    resume_exp = extract_relevant_experience(raw_text)
                    score, reason, tokens_used = get_score(jd_text, resume_exp)

                results.append({
                    "Filename": file.name,
                    "Score": score,
                    "Reason": reason
                })
                total_tokens += tokens_used

            df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "scored_resumes.csv", "text/csv")
            st.caption(f"Estimated tokens: {total_tokens} | Cost: ${total_tokens / 1000 * 0.0015:.4f}")
        else:
            st.warning("Please provide both JD and at least one resume.")

with tab2:
    st.subheader("Step 2: Upload Shortlisted Resumes and Generate Questions")
    jd_text_2 = st.text_area("Paste the same JD again (or new)", height=200, key="jd_text_qs")
    resumes_q = st.file_uploader("Upload shortlisted resumes", type=["pdf", "docx"], accept_multiple_files=True, key="shortlisted_files")
    if st.button("Generate Interview Questions"):
        if jd_text_2 and resumes_q:
            results, total_tokens = [], 0
            for file in resumes_q:
                if file.name.endswith(".pdf"):
                    raw_text = extract_text_from_pdf(file)
                else:
                    raw_text = extract_text_from_docx(file)

                if not raw_text or raw_text.strip() == "":
                    truth_qs, fit_qs, tokens_used = "N/A", "N/A", 0
                else:
                    resume_exp = extract_relevant_experience(raw_text)
                    truth_qs, fit_qs, tokens_used = get_question_blocks(jd_text_2, resume_exp)

                results.append({
                    "Filename": file.name,
                    "Truth Check Questions": truth_qs,
                    "Fit Check Questions": fit_qs
                })
                total_tokens += tokens_used

            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "interview_questions.csv", "text/csv")
            st.caption(f"Estimated tokens: {total_tokens} | Cost: ${total_tokens / 1000 * 0.0015:.4f}")
        else:
            st.warning("Please provide both JD and at least one resume.")
