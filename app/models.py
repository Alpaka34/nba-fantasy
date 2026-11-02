from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Yahoo'nun kullanıcıya verdiği kalıcı kimlik. Demo kullanıcıda boş.
    yahoo_guid: Mapped[str | None] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    is_demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    token: Mapped["YahooToken | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class YahooToken(Base):
    """Kullanıcının Yahoo izni. Tokenlar şifreli saklanır (bkz. crypto.py)."""

    __tablename__ = "yahoo_tokens"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship(back_populates="token")


class CacheEntry(Base):
    __tablename__ = "cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime]
