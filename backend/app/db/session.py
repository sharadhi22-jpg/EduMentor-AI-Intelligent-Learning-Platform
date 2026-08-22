from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Pool pre-ping ensures stale connections are recycled (very useful with MySQL)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding a db session per request.
    Ensures the session is closed when the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
