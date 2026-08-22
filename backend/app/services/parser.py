import os
from pypdf import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation


def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pypdf."""
    text_content = []
    try:
        reader = PdfReader(file_path)
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF file: {str(e)}")
    
    return "\n\n".join(text_content)


def parse_docx(file_path: str) -> str:
    """Extract text from a Word document using python-docx."""
    text_content = []
    try:
        doc = DocxDocument(file_path)
        # Extract paragraph text
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)
        
        # Extract table text
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        text_content.append(cell_text)
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX file: {str(e)}")
    
    return "\n".join(text_content)


def parse_pptx(file_path: str) -> str:
    """Extract text from a PowerPoint presentation using python-pptx."""
    text_content = []
    try:
        prs = Presentation(file_path)
        for slide_idx, slide in enumerate(prs.slides):
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text.strip())
            if slide_text:
                text_content.append(f"--- Slide {slide_idx + 1} ---\n" + "\n".join(slide_text))
    except Exception as e:
        raise ValueError(f"Failed to parse PPTX file: {str(e)}")
        
    return "\n\n".join(text_content)


def parse_txt(file_path: str) -> str:
    """Extract text from a plain text file, trying multiple encodings."""
    encodings = ["utf-8", "latin-1", "utf-16", "cp1252"]
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError("Failed to parse TXT file: Unrecognized text encoding")


def extract_text_from_file(file_path: str, file_type: str) -> str:
    """
    Unified entry point to extract text based on file format.
    file_type: pdf, docx, pptx, txt
    """
    ftype = file_type.lower().strip(".")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    if ftype == "pdf":
        return parse_pdf(file_path)
    elif ftype in ("docx", "doc"):
        return parse_docx(file_path)
    elif ftype in ("pptx", "ppt"):
        return parse_pptx(file_path)
    elif ftype == "txt":
        return parse_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
