"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from pathlib import Path

from .models import Base

# Database configuration
DB_DIR = Path(__file__).parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_DIR}/garmin_planner.db"


class Database:
    """Database manager singleton"""
    _instance = None
    _engine = None
    _SessionLocal = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},  # Needed for SQLite
                echo=False  # Set to True for SQL debugging
            )
            self._SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._engine
            )

    def create_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=self._engine)

    def drop_tables(self):
        """Drop all tables in the database (use with caution!)"""
        Base.metadata.drop_all(bind=self._engine)

    def get_session(self) -> Session:
        """Get a new database session"""
        return self._SessionLocal()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global database instance
db = Database()


def get_db():
    """
    Dependency for FastAPI endpoints
    Usage: db: Session = Depends(get_db)
    """
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Initialize the database (create tables)"""
    db.create_tables()
    print(f"✅ Database initialized at {DATABASE_URL}")
