import streamlit as st
import openai, zipfile, io, tempfile, pathlib
import pandas as pd
from resume_utils import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_relevant_experience,
)
import docx, pdfplumber
from io import StringIO

# ─────────────────────────  Streamlit UI  ─────────────────────────
st.set_page_config(page_title="Resume Scorer (Batch)", layout="wide")
st.title("📊 JD ⇄ Resume Scoring • Batch Mode")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ───────────────────────  Session State  ─────────────────────────
st.session_state.setdefault("resume_data", [])
st.session_state.setdefault("total_tokens", 0)
st.session_state.setdefault("jd_text", "")

# ─────────────────────  JD UPLOAD / PASTE  ───────────────────────
st.subheader("Step 1 • Job Description")
jd_file = st.file_uploader("Upload JD (TXT / PDF / DOCX)", ["txt", "pdf", "docx"])
if jd_file:
    if jd_file.name.lower().endswith(".pdf"):
        with pdfplumber.open(jd_file) as pdf:
            st.session_state.jd_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    elif jd_file.name.lower().endswith(".docx"):
        st.session_state.jd_text = "\n".join(p.text for p in docx.Document(jd_file).paragraphs)
    else:
        st.session_state.jd_text = StringIO(jd_file.getvalue().decode()).read()
else:
    st.session_state.jd_text = st.text_area("…or paste JD here", height=220)

# ─────────────────────  SCORING FUNCTION  ────────────────────────
def get_score(jd: str, resume_exp: str, temp: float = 0.3):
    prompt = (
        "Compare the following resume experience against the job description and rate the relevance from 1 to 10.\n"
        "Return only:\n\n"
        "Score: X\n"
        "Reason: …\n\n"
        f"Job Description:\n{jd}\n\nResume:\n{resume_exp}"
    )
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
    )
    content = resp.choices[0].message.content
    usage = resp.usage.total_tokens if hasattr(resp, "usage") else 0
    try:
        score_line = next(l for l in content.splitlines() if "Score:" in l)
        reason_line = next(l for l in content.splitlines() if "Reason:" in l)
        score = float(score_line.split(":", 1)[1].strip())
        reason = reason_line.split(":", 1)[1].strip()
    except Exception:
        score, reason = 0, "Parse error"
    return score, reason, usage, content

# ─────────────────────  RESUME BATCH UPLOAD  ─────────────────────
st.divider()
st.subheader("Step 2 • Upload Resumes or ZIP Batches")
uploads = st.file_uploader(
    "Upload multiple PDFs / DOCXs or ZIP files (each ZIP may contain many resumes)",
    type=["pdf", "docx", "zip"],
    accept_multiple_files=True,
)

run = st.button("▶️ Run Scoring")
clear = st.button("🗑️ Clear Results")

if clear:
    st.session_state.resume_data.clear()
    st.session_state.total_tokens = 0
    st.rerun()

def stream_all_resumes(files):
    """Yield (filename, bytes) for every resume inside uploaded files/ZIPs."""
    for up in files:
        suffix = pathlib.Path(up.name).suffix.lower()
        if suffix in {".pdf", ".docx"}:
            yield up.name, up.read()
        elif suffix == ".zip":
            z = zipfile.ZipFile(io.BytesIO(up.read()))
            for info in z.infolist():
                if pathlib.Path(info.filename).suffix.lower() in {".pdf", ".docx"}:
                    yield info.filename, z.read(info.filename)

if run and st.session_state.jd_text and uploads:
    all_items = list(stream_all_resumes(uploads))
    total = len(all_items)
    prog_bar = st.progress(0.0, text="Scoring resumes…")
    results, total_tokens = [], 0

    for idx, (fname, data) in enumerate(all_items, start=1):
        ext = pathlib.Path(fname).suffix.lower()
        raw_text = ""
        try:
            if ext == ".pdf":
                raw_text = extract_text_from_pdf(io.BytesIO(data))
            else:
                raw_text = extract_text_from_docx(io.BytesIO(data))
        except Exception:
            pass

        if raw_text.strip():
            resume_exp = extract_relevant_experience(raw_text)
            score, reason, tokens, _ = get_score(st.session_state.jd_text, resume_exp)
        else:
            score, reason, tokens, resume_exp = 0, "Unreadable file", 0, ""

        results.append(
            dict(
                Filename=fname,
                Score=score,
                Reason=reason,
                UsedBlock=resume_exp,
            )
        )
        total_tokens += tokens
        prog_bar.progress(idx / total, text=f"Processed {idx}/{total}")

    st.session_state.resume_data = results
    st.session_state.total_tokens = total_tokens
    prog_bar.empty()

# ─────────────────────  SHOW RESULTS / DOWNLOAD  ─────────────────
if st.session_state.resume_data:
    df = pd.DataFrame(st.session_state.resume_data).sort_values("Score", ascending=False)
    st.dataframe(df[["Filename", "Score", "Reason"]], use_container_width=True)

    csv = df.to_csv(index=False).encode()
    st.download_button("💾 Download CSV", csv, "resume_scores.csv", "text/csv")

    st.caption(
        f"Total tokens: {st.session_state.total_tokens}  • "
        f"Approx cost (~$0.0015 / 1K tokens): "
        f"${st.session_state.total_tokens / 1000 * 0.0015:.4f}"
    )
