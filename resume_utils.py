
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

def extract_relevant_experience(full_text):
    lines = full_text.splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    sections = [
        "experience", "work history", "projects", "employment",
        "roles", "professional experience"
    ]
    exclude_sections = ["summary", "career summary", "objective", "profile"]

    capture = False
    block = []
    for line in lines:
        lower = line.lower()
        if any(s in lower for s in sections):
            capture = True
            block = []
        elif any(x in lower for x in exclude_sections):
            capture = False
        elif capture:
            block.append(line)
    return "\n".join(block) if block else full_text
