import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def configure_session_factory(database_engine):
    """Rebind database sessions, primarily for isolated tests."""
    SessionLocal.configure(bind=database_engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()