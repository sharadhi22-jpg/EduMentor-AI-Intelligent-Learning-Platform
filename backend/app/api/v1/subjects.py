from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.subject import Subject
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectOut

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("/", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new learning subject/course associated with the student's profile.
    semester: 1 to 8.
    """
    # Prevent duplicate subject names for the same user in the same semester
    existing = (
        db.query(Subject)
        .filter(
            Subject.name == payload.name,
            Subject.semester == payload.semester,
            Subject.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Subject '{payload.name}' already exists in Semester {payload.semester}",
        )

    subject = Subject(
        name=payload.name,
        code=payload.code,
        semester=payload.semester,
        user_id=current_user.id,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/", response_model=list[SubjectOut])
def get_subjects(
    semester: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists all subjects for the authenticated user, optionally filtered by semester.
    """
    query = db.query(Subject).filter(Subject.user_id == current_user.id)
    if semester is not None:
        query = query.filter(Subject.semester == semester)
    
    return query.all()


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject_detail(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific subject.
    """
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.user_id == current_user.id)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    return subject
