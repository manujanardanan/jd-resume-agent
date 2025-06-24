
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

# Helper functions
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

def get_score(jd, resume_exp, temperature=0.3):
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
        temperature=temperature
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

def get_question_blocks(jd, resume_exp, temperature=0.5):
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
        temperature=temperature
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

# UI
st.subheader("Step 1: Upload JD")
jd_file = st.file_uploader("Upload JD (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"])
jd_text = ""
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

st.divider()
st.subheader("Step 2: Upload Resumes and Score")

resume_files = st.file_uploader("Upload resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)
score_button = st.button("Run Scoring")

if score_button and jd_text and resume_files:
    results, total_tokens = [], 0
    for i, file in enumerate(resume_files):
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
            "Reason": reason,
            "ResumeText": raw_text,
            "Shortlist": False
        })
        total_tokens += tokens_used

    st.session_state.resume_data = results
    st.session_state.total_score_tokens = total_tokens

if "resume_data" in st.session_state:
    df_display = pd.DataFrame([{
        "Filename": r["Filename"],
        "Score": r["Score"],
        "Reason": r["Reason"],
        "Shortlist": st.checkbox("Shortlist", key=r["Filename"])
    } for r in st.session_state.resume_data])

    st.dataframe(df_display.drop(columns=["Shortlist"]), use_container_width=True)
    st.caption(f"Estimated tokens: {st.session_state.total_score_tokens} | Cost: ${st.session_state.total_score_tokens / 1000 * 0.0015:.4f}")

    st.divider()
    st.subheader("Step 3: Generate Interview Questions for Shortlisted Resumes")
    if st.button("Generate Questions"):
        question_results, total_q_tokens = [], 0
        for r in st.session_state.resume_data:
            if st.session_state.get(r["Filename"], False):
                resume_exp = extract_relevant_experience(r["ResumeText"])
                truth_qs, fit_qs, tokens_used = get_question_blocks(jd_text, resume_exp)
                question_results.append({
                    "Filename": r["Filename"],
                    "Truth Check Questions": truth_qs,
                    "Fit Check Questions": fit_qs
                })
                total_q_tokens += tokens_used

        if question_results:
            q_df = pd.DataFrame(question_results)
            st.dataframe(q_df, use_container_width=True)
            csv = q_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Questions CSV", csv, "interview_questions.csv", "text/csv")
            st.caption(f"Estimated tokens: {total_q_tokens} | Cost: ${total_q_tokens / 1000 * 0.0015:.4f}")
        else:
            st.warning("No resumes were shortlisted.")
