import streamlit as st
import openai
import pandas as pd
from resume_utils import extract_text_from_pdf, extract_text_from_docx
from io import StringIO
import docx
import pdfplumber

st.set_page_config(page_title="JD vs Resume Checker", layout="wide")
st.title("📄 JD vs Resume Relevance Checker (Batch Upload + Smart Questions)")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialize session state
if "resumes_cleared" not in st.session_state:
    st.session_state.resumes_cleared = False

# Upload or paste JD
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

# Resume uploader
st.subheader("Resume Upload")

# Clear resumes button
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

def get_candidate_score(jd, resume_exp):
    prompt = f"""
You are a resume screening assistant.

1. Rate how well this resume matches the job description (score 1–10).
2. Give a brief reason.
3. Suggest 3–5 specific interview questions to ask this candidate based on their resume and the JD.

Job Description:
{jd}

Resume Experience/Projects:
{resume_exp}

Format output like:
Score: X
Reason: ...
Interview Questions:
1. ...
2. ...
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    content = response.choices[0].message.content
    usage = response.usage.total_tokens if hasattr(response, "usage") else 0

    try:
        lines = content.splitlines()
        score_line = next(l for l in lines if "Score:" in l)
        reason_line = next(l for l in lines if "Reason:" in l)
        question_lines = [l for l in lines if l.strip().startswith(tuple("12345"))]

        score = float(score_line.split(":")[1].strip())
        reason = reason_line.split(":", 1)[1].strip()
        questions = "\n".join(question_lines)
    except:
        score, reason, questions = 0, "Could not parse", "N/A"

    return score, reason, questions, usage

if st.button("Check All Resumes"):
    st.session_state.resumes_cleared = False  # reset resume cleared state
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
                        score, reason, questions, tokens_used = get_candidate_score(jd_text, resume_exp)

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
