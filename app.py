
import streamlit as st
import openai
import pandas as pd
from resume_utils import extract_text_from_pdf, extract_text_from_docx, extract_relevant_experience
from io import StringIO
import docx
import pdfplumber

st.set_page_config(page_title="Resume Scorer with Transparency", layout="wide")
st.title("📊 JD vs Resume Scoring Agent with Transparency")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "resume_data" not in st.session_state:
    st.session_state.resume_data = []
if "total_score_tokens" not in st.session_state:
    st.session_state.total_score_tokens = 0
if "jd_text" not in st.session_state:
    st.session_state.jd_text = ""

# JD Upload
st.subheader("Step 1: Upload JD")
jd_file = st.file_uploader("Upload JD (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"])
if jd_file:
    if jd_file.name.endswith(".pdf"):
        with pdfplumber.open(jd_file) as pdf:
            st.session_state.jd_text = "\n".join([page.extract_text() for page in pdf.pages])
    elif jd_file.name.endswith(".docx"):
        doc = docx.Document(jd_file)
        st.session_state.jd_text = "\n".join([para.text for para in doc.paragraphs])
    else:
        st.session_state.jd_text = StringIO(jd_file.getvalue().decode("utf-8")).read()
else:
    st.session_state.jd_text = st.text_area("Or paste JD here", height=200)

def get_score(jd, resume_exp, temperature=0.3):
    prompt = (
        "Compare the following resume experience against the job description and rate the relevance from 1 to 10. "
        "Return only:\n\n"
        "Score: X\n"
        "Reason: ...\n\n"
        f"Job Description:\n{jd}\n\nResume:\n{resume_exp}"
    )
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
    return score, reason, usage, content

st.divider()
st.subheader("Step 2: Upload Resumes and Score")
resume_files = st.file_uploader("Upload resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)
score_button = st.button("Run Scoring")
clear_button = st.button("🗑️ Clear All Resumes")

if clear_button:
    st.session_state.resume_data = []
    st.session_state.total_score_tokens = 0
    st.rerun()

if score_button and st.session_state.jd_text and resume_files:
    results, total_tokens = [], 0
    for file in resume_files:
        if file.name.endswith(".pdf"):
            raw_text = extract_text_from_pdf(file)
        else:
            raw_text = extract_text_from_docx(file)

        if not raw_text or raw_text.strip() == "":
            score, reason, tokens_used, full_response = 0, "File not readable", 0, ""
            used_block = ""
        else:
            resume_exp = extract_relevant_experience(raw_text)
            score, reason, tokens_used, full_response = get_score(st.session_state.jd_text, resume_exp)
            used_block = resume_exp
        results.append({
            "Filename": file.name,
            "Score": score,
            "Reason": reason,
            "UsedBlock": used_block
        })
        total_tokens += tokens_used

    st.session_state.resume_data = results
    st.session_state.total_score_tokens = total_tokens

if st.session_state.resume_data:
    df = pd.DataFrame(st.session_state.resume_data).sort_values(by="Score", ascending=False)
    st.dataframe(df[["Filename", "Score", "Reason"]], use_container_width=True)

    with st.expander("🔁 Re-evaluate with updated resume block"):
        selected_file = st.selectbox("Select resume", [r["Filename"] for r in st.session_state.resume_data])
        selected = next(r for r in st.session_state.resume_data if r["Filename"] == selected_file)
        updated_text = st.text_area("Update resume block for re-evaluation", selected["UsedBlock"], height=200)
        if st.button("Re-score"):
            new_score, new_reason, tokens, _ = get_score(st.session_state.jd_text, updated_text)
            selected["Score"] = new_score
            selected["Reason"] = new_reason
            selected["UsedBlock"] = updated_text
            st.success(f"Updated score: {new_score} | Reason: {new_reason}")

    with st.expander("🔍 View resume sections used in scoring"):
        explain_file = st.selectbox("Select resume to view section", [r["Filename"] for r in st.session_state.resume_data], key="explain")
        explain_selected = next(r for r in st.session_state.resume_data if r["Filename"] == explain_file)
        st.code(explain_selected["UsedBlock"], language="text")

    st.caption(f"Estimated tokens: {st.session_state.total_score_tokens} | Cost: ${st.session_state.total_score_tokens / 1000 * 0.0015:.4f}")
