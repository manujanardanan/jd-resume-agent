
import pdfplumber
import docx

def extract_text_from_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            return "\n".join([page.extract_text() or "" for page in pdf.pages])
    except:
        return ""

def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except:
        return ""

def extract_relevant_experience(text):
    sections = ["experience", "work history", "projects", "employment", "roles", "professional experience"]
    lines = text.splitlines()
    capture = False
    keep = []
    for line in lines:
        line_lower = line.lower()
        if any(section in line_lower for section in sections):
            capture = True
        if capture:
            keep.append(line)
        # stop if a new unrelated section starts
        if capture and (line_lower.strip().endswith(":") and not any(section in line_lower for section in sections)):
            break
    return "\n".join(keep).strip() if keep else text.strip()
