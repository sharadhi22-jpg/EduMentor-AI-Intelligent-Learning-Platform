from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.study import Progress, Quiz, QuizAttempt, Flashcard
from app.models.subject import Subject
from app.models.user import User
from app.schemas.study import ProgressOut, StudyTimeLogRequest

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_owned_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or access denied.")
    return subject


def _get_or_create_progress(db: Session, user: User, subject_id: int) -> Progress:
    progress = (
        db.query(Progress)
        .filter(Progress.user_id == user.id, Progress.subject_id == subject_id)
        .first()
    )
    if not progress:
        progress = Progress(user_id=user.id, subject_id=subject_id)
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


@router.get("/progress/{subject_id}", response_model=ProgressOut)
def get_subject_progress(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get (or lazily create) the progress record for a subject."""
    _get_owned_subject(db, subject_id, current_user)
    return _get_or_create_progress(db, current_user, subject_id)


@router.get("/progress", response_model=List[ProgressOut])
def list_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List progress records for every subject the user has studied."""
    return db.query(Progress).filter(Progress.user_id == current_user.id).all()


@router.post("/progress/study-time", response_model=ProgressOut)
def log_study_time(
    payload: StudyTimeLogRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add study hours to a subject's progress (manual self-reported tracker)."""
    _get_owned_subject(db, payload.subject_id, current_user)
    progress = _get_or_create_progress(db, current_user, payload.subject_id)
    progress.study_hours = (progress.study_hours or 0.0) + payload.hours
    db.commit()
    db.refresh(progress)
    return progress


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregate overview across every subject: totals, average quiz score,
    and combined weak/strong topics — the data a home-screen dashboard needs.
    """
    subjects = db.query(Subject).filter(Subject.user_id == current_user.id).all()
    subject_ids = [s.id for s in subjects]

    total_documents = (
        db.query(Document).filter(Document.subject_id.in_(subject_ids)).count() if subject_ids else 0
    )
    total_flashcards = (
        db.query(Flashcard).filter(Flashcard.subject_id.in_(subject_ids)).count() if subject_ids else 0
    )
    attempts = (
        db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    )
    total_quiz_attempts = len(attempts)
    average_score_pct = (
        round(
            sum((a.score / a.total_questions) * 100 for a in attempts if a.total_questions) / len(attempts),
            1,
        )
        if attempts
        else None
    )

    progress_records = db.query(Progress).filter(Progress.user_id == current_user.id).all()
    total_study_hours = round(sum(p.study_hours or 0.0 for p in progress_records), 2)

    weak_topics = sorted({t for p in progress_records for t in (p.weak_topics or [])})
    strong_topics = sorted({t for p in progress_records for t in (p.strong_topics or [])})

    subject_summaries = []
    for subject in subjects:
        prog = next((p for p in progress_records if p.subject_id == subject.id), None)
        subject_summaries.append(
            {
                "subject_id": subject.id,
                "name": subject.name,
                "semester": subject.semester,
                "study_hours": prog.study_hours if prog else 0.0,
                "completed_quizzes": prog.completed_quizzes if prog else 0,
            }
        )

    return {
        "total_subjects": len(subjects),
        "total_documents": total_documents,
        "total_flashcards": total_flashcards,
        "total_quiz_attempts": total_quiz_attempts,
        "average_score_pct": average_score_pct,
        "total_study_hours": total_study_hours,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "subjects": subject_summaries,
    }
