from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

load_dotenv(BACKEND_DIR / ".env")


def _resolve_database_url(url: str) -> str:
    if url.startswith("sqlite:///./"):
        db_file = url.replace("sqlite:///./", "", 1)
        return f"sqlite:///{(BACKEND_DIR / db_file).resolve().as_posix()}"
    return url


SQLALCHEMY_DATABASE_URL = _resolve_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./cloud_risk.db")
)

# SQLite requires check_same_thread=False; PostgreSQL does not accept it
_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
