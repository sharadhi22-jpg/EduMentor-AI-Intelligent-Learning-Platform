# Import all the models so that Base.metadata has them registered.
# This is required for SQLAlchemy to automatically create database tables on startup.
from app.db.session import Base  # noqa
from app.models.user import User  # noqa
from app.models.subject import Subject  # noqa
from app.models.document import Document, DocumentChunk  # noqa
from app.models.chat import ChatSession, ChatMessage  # noqa
from app.models.study import Flashcard, Quiz, QuizAttempt, Progress  # noqa
