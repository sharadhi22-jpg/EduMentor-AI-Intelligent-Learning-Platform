from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core import gemini
from app.db.session import get_db
from app.models.document import Document, DocumentChunk
from app.models.study import DifficultyLevel, Flashcard, Progress, Quiz, QuizAttempt
from app.models.subject import Subject
from app.models.user import User
from app.schemas.study import (
    FlashcardGenerateRequest,
    FlashcardOut,
    ProgressOut,
    QuizAttemptOut,
    QuizGenerateRequest,
    QuizOut,
    QuizSubmitRequest,
)

router = APIRouter(prefix="/study-tools", tags=["study-tools"])

# Cap how much source text we send to Gemini per generation request
MAX_CONTEXT_CHARS = 14000


def _get_owned_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or access denied.")
    return subject


def _gather_source_text(db: Session, subject_id: int, document_id: int | None) -> str:
    """Pull chunk text (in order) from a subject's completed documents, up to a
    character budget, to use as generation source material."""
    query = (
        db.query(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.subject_id == subject_id)
    )
    if document_id is not None:
        query = query.filter(Document.id == document_id)

    chunks = query.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()

    text_parts = []
    total_len = 0
    for chunk in chunks:
        if total_len >= MAX_CONTEXT_CHARS:
            break
        text_parts.append(chunk.content)
        total_len += len(chunk.content)

    return "\n\n".join(text_parts)


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------

@router.post("/flashcards/generate", response_model=List[FlashcardOut], status_code=status.HTTP_201_CREATED)
def generate_flashcards(
    payload: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate flashcards from a subject's (or a single document's) uploaded content."""
    _get_owned_subject(db, payload.subject_id, current_user)

    if not gemini.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flashcard generation is not available: GEMINI_API_KEY is not configured on the server.",
        )

    source_text = _gather_source_text(db, payload.subject_id, payload.document_id)
    if not source_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed document content found for this subject. Upload documents first.",
        )

    prompt = (
        f"Generate exactly {payload.count} flashcards at {payload.difficulty.value} difficulty "
        f"from the following source material.\n\n"
        f"Respond with ONLY a JSON array of exactly {payload.count} objects, each with keys "
        f'"front" and "back" (both strings). No other text.\n\n'
        f"Source material:\n{source_text}"
    )

    try:
        result = gemini.generate_json(prompt, system_instruction=gemini.FLASHCARD_SYSTEM_PROMPT)
    except gemini.GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not isinstance(result, list):
        raise HTTPException(status_code=502, detail="Gemini returned an unexpected response format.")

    created = []
    for item in result:
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if not front or not back:
            continue
        card = Flashcard(
            subject_id=payload.subject_id,
            document_id=payload.document_id,
            front=front,
            back=back,
            difficulty=payload.difficulty,
        )
        db.add(card)
        created.append(card)

    if not created:
        raise HTTPException(status_code=502, detail="Gemini did not return any usable flashcards.")

    db.commit()
    for card in created:
        db.refresh(card)
    return created


@router.get("/flashcards", response_model=List[FlashcardOut])
def list_flashcards(
    subject_id: int,
    document_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_subject(db, subject_id, current_user)
    query = db.query(Flashcard).filter(Flashcard.subject_id == subject_id)
    if document_id is not None:
        query = query.filter(Flashcard.document_id == document_id)
    return query.order_by(Flashcard.created_at.desc()).all()


@router.delete("/flashcards/{flashcard_id}", status_code=status.HTTP_200_OK)
def delete_flashcard(
    flashcard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found.")
    _get_owned_subject(db, card.subject_id, current_user)  # ownership via subject
    db.delete(card)
    db.commit()
    return {"detail": "Flashcard deleted successfully."}


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

@router.post("/quizzes/generate", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a multiple-choice quiz from a subject's (or a single document's) content."""
    subject = _get_owned_subject(db, payload.subject_id, current_user)

    if not gemini.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quiz generation is not available: GEMINI_API_KEY is not configured on the server.",
        )

    source_text = _gather_source_text(db, payload.subject_id, payload.document_id)
    if not source_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed document content found for this subject. Upload documents first.",
        )

    prompt = (
        f"Generate exactly {payload.count} multiple-choice quiz questions at "
        f"{payload.difficulty.value} difficulty from the following source material.\n\n"
        f"Respond with ONLY a JSON array of exactly {payload.count} objects, each with keys: "
        f'"question" (string), "options" (array of exactly 4 strings), "correct_answer" '
        f'(string that exactly matches one of the options), "type" (always "MCQ"). No other text.\n\n'
        f"Source material:\n{source_text}"
    )

    try:
        questions = gemini.generate_json(prompt, system_instruction=gemini.QUIZ_SYSTEM_PROMPT)
    except gemini.GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not isinstance(questions, list) or not questions:
        raise HTTPException(status_code=502, detail="Gemini did not return any usable quiz questions.")

    # Basic validation/cleanup so malformed entries don't corrupt stored data
    valid_questions = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            continue
        if q.get("correct_answer") not in options:
            continue
        valid_questions.append(
            {
                "question": str(q.get("question", "")).strip(),
                "options": [str(o) for o in options],
                "correct_answer": str(q.get("correct_answer")),
                "type": "MCQ",
            }
        )

    if not valid_questions:
        raise HTTPException(status_code=502, detail="Gemini's quiz response failed validation.")

    doc_title = None
    if payload.document_id:
        doc = db.query(Document).filter(Document.id == payload.document_id).first()
        doc_title = doc.filename if doc else None

    quiz = Quiz(
        subject_id=payload.subject_id,
        document_id=payload.document_id,
        title=f"{doc_title or subject.name} Quiz ({payload.difficulty.value.title()})",
        difficulty=payload.difficulty,
        questions=valid_questions,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


@router.get("/quizzes", response_model=List[QuizOut])
def list_quizzes(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_subject(db, subject_id, current_user)
    return db.query(Quiz).filter(Quiz.subject_id == subject_id).order_by(Quiz.created_at.desc()).all()


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    _get_owned_subject(db, quiz.subject_id, current_user)
    return quiz


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizAttemptOut, status_code=status.HTTP_201_CREATED)
def submit_quiz(
    quiz_id: int,
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grade a quiz attempt, store it, and roll the result into subject progress."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    subject = _get_owned_subject(db, quiz.subject_id, current_user)

    graded_answers = []
    score = 0
    for index, question in enumerate(quiz.questions):
        selected = payload.answers.get(index)
        is_correct = selected is not None and selected == question.get("correct_answer")
        if is_correct:
            score += 1
        graded_answers.append(
            {
                "question_index": index,
                "selected": selected,
                "is_correct": is_correct,
            }
        )

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        score=score,
        total_questions=len(quiz.questions),
        answers=graded_answers,
    )
    db.add(attempt)

    # Roll this attempt into the subject's progress record
    progress = (
        db.query(Progress)
        .filter(Progress.user_id == current_user.id, Progress.subject_id == subject.id)
        .first()
    )
    if not progress:
        progress = Progress(user_id=current_user.id, subject_id=subject.id)
        db.add(progress)

    progress.completed_quizzes = (progress.completed_quizzes or 0) + 1

    pct = (score / len(quiz.questions)) * 100 if quiz.questions else 0
    weak = set(progress.weak_topics or [])
    strong = set(progress.strong_topics or [])
    if pct < 60:
        weak.add(quiz.title)
        strong.discard(quiz.title)
    else:
        strong.add(quiz.title)
        weak.discard(quiz.title)
    progress.weak_topics = list(weak)
    progress.strong_topics = list(strong)

    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/quizzes/{quiz_id}/attempts", response_model=List[QuizAttemptOut])
def list_quiz_attempts(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    _get_owned_subject(db, quiz.subject_id, current_user)
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
