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


ROOT = Path(__file__).resolve().parent.parent


def init_db():
    """Veritabanını en son tablo sürümüne getirir (Alembic, migrations/).

    Alembic'ten önce create_all ile kurulmuş bir veritabanında eksik tablolar
    oluşturulur ve son sürüm olarak işaretlenir; sonraki değişiklikler normal
    sürüm adımlarıyla uygulanır.
    """
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from . import models  # noqa: F401  (tabloların kaydı için)

    cfg = Config(str(ROOT / "alembic.ini"))
    tables = inspect(engine).get_table_names()
    if tables and "alembic_version" not in tables:
        Base.metadata.create_all(engine)
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
