import streamlit as st
import openai
import pandas as pd
from resume_utils import extract_text_from_pdf, extract_text_from_docx

# Configure Streamlit page
st.set_page_config(page_title="JD vs Resume Checker", layout="wide")
st.title("📄 JD vs Resume Relevance Checker (Batch Upload)")

# Initialize OpenAI client
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Input: Job Description
jd = st.text_area("Paste Job Description", height=300)

# Input: Multiple Resume Files
resume_files = st.file_uploader(
    "Upload up to 20 Resumes (PDF or DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=True
)

# Function to extract experience/project sections
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

# Function to evaluate relevance using OpenAI
def get_relevance_score(jd, resume_exp):
    prompt = f"""
You are a smart resume screening assistant.

Compare the following job description and resume experience/projects only (ignore summary or objective).

1. Rate the resume's relevance to the job out of 10, with a brief explanation.
2. Return only: relevance score (as a number) and reasoning.

Job Description:
{jd}

Resume Experience/Projects:
{resume_exp}

Output format:
Score: X
Reason: <short reason>
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    content = response.choices[0].message.content

    try:
        score_line = next(line for line in content.splitlines() if "Score:" in line)
        reason_line = next(line for line in content.splitlines() if "Reason:" in line)
        score = float(score_line.split(":")[1].strip())
        reason = reason_line.split(":", 1)[1].strip()
    except:
        score = 0
        reason = "Could not parse response"

    return score, reason

# Main logic on button click
if st.button("Check All Resumes"):
    if jd and resume_files:
        if len(resume_files) > 20:
            st.warning("Please upload a maximum of 20 resumes.")
        else:
            results = []
            with st.spinner("Analyzing resumes..."):
                for file in resume_files:
                    if file.name.endswith(".pdf"):
                        raw_text = extract_text_from_pdf(file)
                    else:
                        raw_text = extract_text_from_docx(file)

                    resume_exp = extract_relevant_experience(raw_text)
                    score, reason = get_relevance_score(jd, resume_exp)

                    results.append({
                        "Filename": file.name,
                        "Score": score,
                        "Reason": reason
                    })

            # Show results
            df = pd.DataFrame(results)
            df_sorted = df.sort_values(by="Score", ascending=False)
            st.success("Analysis complete. Sorted results below:")
            st.dataframe(df_sorted, use_container_width=True)

            # Optional: download button
            csv = df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results as CSV", data=csv, file_name="resume_scores.csv", mime="text/csv")
    else:
        st.warning("Please provide both a Job Description and at least one resume.")
