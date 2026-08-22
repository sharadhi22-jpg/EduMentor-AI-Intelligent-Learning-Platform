import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core import embeddings, gemini
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.document import Document, DocumentChunk
from app.models.subject import Subject
from app.models.user import User
from app.schemas.chat import MessageCreate, MessageOut, SessionCreate, SessionOut
from app.services.vector_store import top_k_chunks
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_owned_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or access denied.")
    return subject


def _get_owned_session(db: Session, session_id: str, user: User) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found or access denied.")
    return session


def _retrieve_context(db: Session, subject_id: int, query: str, k: int = None):
    """Embed the query and return the top-k most relevant chunks across all
    completed documents in the subject."""
    k = k or settings.RAG_TOP_K
    query_vector = embeddings.embed_query(query)
    if not query_vector:
        return []

    chunks = (
        db.query(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.subject_id == subject_id)
        .all()
    )

    # Self-healing: if any chunks lack embeddings, generate them on the fly
    empty_chunks = [c for c in chunks if not c.embedding]
    if empty_chunks and gemini.is_configured():
        try:
            texts_to_embed = [c.content for c in empty_chunks]
            new_embeddings = embeddings.embed_documents(texts_to_embed)
            for chunk, emb in zip(empty_chunks, new_embeddings):
                if emb:
                    chunk.embedding = emb
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Self-healing embeddings update failed: %s", e)

    return top_k_chunks(query_vector, chunks, k=k)


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new chat session scoped to a subject."""
    _get_owned_subject(db, payload.subject_id, current_user)

    session = ChatSession(
        id=str(uuid.uuid4()),
        title=payload.title or "New Chat",
        user_id=current_user.id,
        subject_id=payload.subject_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(
    subject_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the user's chat sessions, optionally filtered by subject."""
    query = db.query(ChatSession).filter(ChatSession.user_id == current_user.id)
    if subject_id is not None:
        query = query.filter(ChatSession.subject_id == subject_id)
    return query.order_by(ChatSession.created_at.desc()).all()


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
def list_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all messages in a chat session, oldest first."""
    _get_owned_session(db, session_id, current_user)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.post("/sessions/{session_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    session_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a user message and get back the assistant's RAG-grounded reply.
    Retrieves the most relevant chunks from the subject's documents, asks
    Gemini to answer using only that context, and stores both messages.
    """
    session = _get_owned_session(db, session_id, current_user)

    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    # 1. Persist the user's message
    user_message = ChatMessage(
        session_id=session.id,
        role=ChatRole.user,
        content=payload.content,
    )
    db.add(user_message)
    db.commit()

    # 2. Retrieve relevant context from the subject's documents
    if not gemini.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI chat is not available: GEMINI_API_KEY is not configured on the server.",
        )

    scored_chunks = _retrieve_context(db, session.subject_id, payload.content)

    if not scored_chunks:
        assistant_text = (
            "I couldn't find anything relevant in your uploaded documents for this subject "
            "yet. Try uploading course material first, or rephrase your question."
        )
        citations = []
    else:
        context_blocks = []
        citations = []
        for chunk, score in scored_chunks:
            doc = db.query(Document).filter(Document.id == chunk.document_id).first()
            filename = doc.filename if doc else "unknown"
            context_blocks.append(
                f"[Source: {filename}, chunk {chunk.chunk_index}]\n{chunk.content}"
            )
            citations.append(
                {
                    "document_id": chunk.document_id,
                    "filename": filename,
                    "chunk_index": chunk.chunk_index,
                    "relevance": round(score, 3),
                }
            )

        # Include recent conversation history for continuity
        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )
        history.reverse()
        history_text = "\n".join(f"{m.role.value.capitalize()}: {m.content}" for m in history)

        prompt = (
            f"Context excerpts from the student's course documents:\n\n"
            f"{chr(10).join(context_blocks)}\n\n"
            f"Recent conversation:\n{history_text}\n\n"
            f"Answer the student's latest message using only the context above."
        )

        try:
            assistant_text = gemini.generate_text(prompt, system_instruction=gemini.CHAT_SYSTEM_PROMPT)
        except gemini.GeminiError as e:
            raise HTTPException(status_code=502, detail=str(e))

    # 3. Persist the assistant's reply
    assistant_message = ChatMessage(
        session_id=session.id,
        role=ChatRole.assistant,
        content=assistant_text,
        citations=citations or None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return assistant_message


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all of its messages."""
    session = _get_owned_session(db, session_id, current_user)
    db.delete(session)
    db.commit()
    return {"detail": "Chat session deleted successfully."}
