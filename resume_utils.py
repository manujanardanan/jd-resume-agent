
import pdfplumber
import docx
import re

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

    # Defined to match full-line section headers only
    start_sections = [
        "experience", "work history", "projects", "employment",
        "roles", "professional experience"
    ]
    end_sections = [
        "education", "certifications", "skills", "summary", "career summary",
        "objective", "languages", "interests", "profile"
    ]

    start_pattern = re.compile(r"^\s*(" + "|".join(start_sections) + r")\s*$", re.IGNORECASE)
    end_pattern = re.compile(r"^\s*(" + "|".join(end_sections) + r")\s*$", re.IGNORECASE)

    capture = False
    block = []
    for line in lines:
        if start_pattern.match(line):
            capture = True
            block = []
            continue
        if end_pattern.match(line):
            if capture:
                break
        if capture:
            block.append(line)

    return "\n".join(block) if block else full_text
