import streamlit as st
import openai
import pandas as pd
from resume_utils import extract_text_from_pdf, extract_text_from_docx
from io import StringIO
import docx
import pdfplumber

st.set_page_config(page_title="JD vs Resume Checker", layout="wide")
st.title("📄 JD vs Resume Relevance Checker (Stable Scores + Smart Questions)")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialize session state
if "resumes_cleared" not in st.session_state:
    st.session_state.resumes_cleared = False

# Job Description input
st.subheader("Job Description")
jd_text = ""
jd_file = st.file_uploader("Upload JD (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"], key="jd_file")
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
    jd_text = st.text_area("Or paste the Job Description below", height=300)

# Resume Upload UI
st.subheader("Resume Upload")

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🗑️ Clear Resumes"):
        st.session_state.resumes_cleared = True
        st.experimental_rerun()

if st.session_state.resumes_cleared:
    resume_files = []
else:
    resume_files = st.file_uploader(
        "Upload up to 20 Resumes (PDF or DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="resume_files"
    )

# Extract relevant experience/projects
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

# Separate call for stable score
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

# Separate call for interview questions
def get_questions(jd, resume_exp):
    prompt = f"""
Generate 3–5 specific interview questions to ask this candidate based on their resume experience and the job description below.

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
    return content, usage

# Main logic
if st.button("Check All Resumes"):
    st.session_state.resumes_cleared = False
    if jd_text and resume_files:
        if len(resume_files) > 20:
            st.warning("Please upload a maximum of 20 resumes.")
        else:
            results = []
            total_tokens = 0
            with st.spinner("Analyzing resumes..."):
                for file in resume_files:
                    if file.name.endswith(".pdf"):
                        raw_text = extract_text_from_pdf(file)
                    else:
                        raw_text = extract_text_from_docx(file)

                    if not raw_text or raw_text.strip() == "":
                        score, reason, questions, tokens_used = 0, "File not readable", "N/A", 0
                    else:
                        resume_exp = extract_relevant_experience(raw_text)
                        score, reason, score_tokens = get_score(jd_text, resume_exp)
                        questions, question_tokens = get_questions(jd_text, resume_exp)
                        tokens_used = score_tokens + question_tokens

                    results.append({
                        "Filename": file.name,
                        "Score": score,
                        "Reason": reason,
                        "Suggested Interview Questions": questions
                    })
                    total_tokens += tokens_used

            df = pd.DataFrame(results)
            df_sorted = df.sort_values(by="Score", ascending=False)
            st.success("Analysis complete. Sorted results below:")
            st.dataframe(df_sorted, use_container_width=True)

            csv = df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results as CSV", data=csv, file_name="resume_scores.csv", mime="text/csv")

            cost_usd = total_tokens / 1000 * 0.0015
            st.caption(f"🧮 Estimated usage: {total_tokens} tokens | Estimated cost: ${cost_usd:.4f}")
    else:
        st.warning("Please provide both a Job Description and at least one resume.")
