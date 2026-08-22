import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document, DocumentChunk, UploadStatus
from app.models.subject import Subject
from app.models.user import User
from app.schemas.document import DocumentOut
from app.core import embeddings
from app.services.chunker import RecursiveCharacterChunker
from app.services.parser import extract_text_from_file

router = APIRouter(prefix="/documents", tags=["documents"])

# Secure local storage directory
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 20 MB size limit
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}


@router.post("/upload", response_model=List[DocumentOut], status_code=status.HTTP_201_CREATED)
def upload_documents(
    subject_id: int = Form(...),
    files: List[UploadFile] = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload multiple study documents (PDF, DOCX, PPTX, TXT) to a specific subject.
    Validates file sizes, extracts text, chunks them, and stores records in MySQL.
    """
    # 1. Validate subject ownership
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == current_user.id)
        .first()
    )
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found or access denied.",
        )

    uploaded_docs = []

    for file in files:
        # Get file extension
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()

        # Validate file type
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: '{file.filename}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # Create record in database as "pending"
        db_doc = Document(
            filename=file.filename,
            filepath="",  # will be set after saving file
            file_type=ext.replace(".", ""),
            size_bytes=0,  # will update after read
            upload_status=UploadStatus.pending,
            subject_id=subject_id,
            user_id=current_user.id,
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        try:
            # Create a unique local file path to prevent name collision
            file_name = f"doc_{db_doc.id}{ext}"
            file_path = os.path.join(UPLOAD_DIR, file_name)

            # Save the file to local disk, keeping track of size
            file_size = 0
            with open(file_path, "wb") as buffer:
                # Read chunks to verify size limit
                while chunk := file.file.read(8192):
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File {file.filename} exceeds the maximum size limit of 20MB.",
                        )
                    buffer.write(chunk)

            # Update document filepath and size
            db_doc.filepath = file_path
            db_doc.size_bytes = file_size
            db_doc.upload_status = UploadStatus.processing
            db.commit()

            # Extract raw text from the document
            raw_text = extract_text_from_file(file_path, db_doc.file_type)

            if not raw_text.strip():
                raise ValueError("Extracted text is empty. The file may be scanned or empty.")

            # Chunk the extracted text
            chunker = RecursiveCharacterChunker(chunk_size=800, chunk_overlap=150)
            text_chunks = chunker.chunk_text(raw_text)

            # Compute embeddings for every chunk in one batched call (falls back
            # to empty vectors if GEMINI_API_KEY isn't configured, so upload
            # never fails outright just because embeddings are unavailable)
            chunk_embeddings = embeddings.embed_documents(text_chunks)

            # Store the text chunks in the database
            for index, chunk_text in enumerate(text_chunks):
                db_chunk = DocumentChunk(
                    document_id=db_doc.id,
                    chunk_index=index,
                    content=chunk_text,
                    embedding=chunk_embeddings[index] if index < len(chunk_embeddings) else [],
                )
                db.add(db_chunk)

            # Update status to completed
            db_doc.upload_status = UploadStatus.completed
            db.commit()
            db.refresh(db_doc)
            uploaded_docs.append(db_doc)

        except Exception as e:
            # Mark document processing as failed
            db_doc.upload_status = UploadStatus.failed
            db.commit()
            db.refresh(db_doc)
            # Remove partial file if it exists
            if db_doc.filepath and os.path.exists(db_doc.filepath):
                try:
                    os.remove(db_doc.filepath)
                except OSError:
                    pass
            # Still append to list to show failure status
            uploaded_docs.append(db_doc)

    return uploaded_docs


@router.get("/subject/{subject_id}", response_model=List[DocumentOut])
def list_documents(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all uploaded documents associated with a subject.
    """
    # Verify subject belongs to user
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == current_user.id)
        .first()
    )
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found or access denied.",
        )

    return db.query(Document).filter(Document.subject_id == subject_id).all()


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document from the system.
    Removes the physical file from disk and deletes database records (cascading to chunks).
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    # 1. Remove physical file from disk
    if document.filepath and os.path.exists(document.filepath):
        try:
            os.remove(document.filepath)
        except OSError as e:
            # Log error but don't fail, we still want to clean database record
            print(f"Error removing file {document.filepath}: {e}")

    # 2. Delete database record (cascades to document_chunks)
    db.delete(document)
    db.commit()

    return {"detail": "Document and associated text chunks deleted successfully."}
