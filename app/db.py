from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

def _normalize_url(url: str) -> str:
    """Neon/Render'ın verdiği postgres:// adresini SQLAlchemy'nin psycopg sürücüsüne çevirir."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


_url = _normalize_url(settings.database_url)
_is_sqlite = _url.startswith("sqlite")
if _is_sqlite:
    Path("data").mkdir(exist_ok=True)

engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Saat dilimsiz UTC (SQLite saat dilimini saklamadığı için)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (tabloların kaydı için)

    Base.metadata.create_all(engine)
