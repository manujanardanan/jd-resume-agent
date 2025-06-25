
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

    start_sections = [
        "experience", "work history", "projects", "employment",
        "roles", "professional experience"
    ]
    end_sections = [
        "education", "certifications", "skills", "summary", "career summary",
        "objective", "languages", "interests", "profile"
    ]

    capture = False
    block = []
    for line in lines:
        lower = line.lower()
        if any(s in lower for s in start_sections):
            capture = True
            block = []
            continue
        if any(e in lower for e in end_sections):
            if capture:
                break
        if capture:
            block.append(line)

    return "\n".join(block) if block else full_text
