from datetime import datetime

from datetime import date

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Yahoo'nun kullanıcıya verdiği kalıcı kimlik. Demo kullanıcıda boş.
    yahoo_guid: Mapped[str | None] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    is_demo: Mapped[bool] = mapped_column(default=False)
    # Yahoo'ya bağlanmadan oyuncu seçen ziyaretçi (tarayıcı çerezine bağlı)
    is_guest: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    token: Mapped["YahooToken | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    picks: Mapped[list["Pick"]] = relationship(cascade="all, delete-orphan")


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


# --- NBA verisi (kaynak: app/nba/, şimdilik ESPN) -------------------------

class NbaPlayer(Base):
    """Takım kadrolarından gelen oyuncu bilgisi (arama, pozisyon, sakatlık)."""

    __tablename__ = "nba_players"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # kaynaktaki oyuncu kimliği
    name: Mapped[str] = mapped_column(String(80))
    short_name: Mapped[str] = mapped_column(String(60), default="")
    team: Mapped[str] = mapped_column(String(8), default="")
    position: Mapped[str] = mapped_column(String(8), default="")
    jersey: Mapped[str] = mapped_column(String(4), default="")
    injury: Mapped[str] = mapped_column(String(40), default="")
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class NbaGame(Base):
    __tablename__ = "nba_games"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    game_date: Mapped[date] = mapped_column(index=True)  # NBA'in kendi günü (ABD Doğu saati)
    start_utc: Mapped[datetime]
    state: Mapped[str] = mapped_column(String(8))  # pre | in | post
    detail: Mapped[str] = mapped_column(String(60), default="")
    home_team: Mapped[str] = mapped_column(String(8))
    away_team: Mapped[str] = mapped_column(String(8))
    home_score: Mapped[int | None]
    away_score: Mapped[int | None]
    # Takım adı, logo, galibiyet-mağlubiyet gibi sadece gösterim amaçlı bilgiler (JSON)
    extra: Mapped[str] = mapped_column(Text, default="{}")
    box_synced_at: Mapped[datetime | None]
    # Kutu skor maç bittikten sonra çekildiyse bir daha çekilmez
    box_final: Mapped[bool] = mapped_column(default=False)


class PlayerGameLine(Base):
    """Bir oyuncunun bir maçtaki istatistikleri (kutu skordan)."""

    __tablename__ = "nba_player_lines"
    __table_args__ = (UniqueConstraint("game_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.id"), index=True)
    game_date: Mapped[date] = mapped_column(index=True)
    player_id: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(8))
    position: Mapped[str] = mapped_column(String(8), default="")
    starter: Mapped[bool] = mapped_column(default=False)
    minutes: Mapped[int] = mapped_column(default=0)
    pts: Mapped[int] = mapped_column(default=0)
    reb: Mapped[int] = mapped_column(default=0)
    ast: Mapped[int] = mapped_column(default=0)
    stl: Mapped[int] = mapped_column(default=0)
    blk: Mapped[int] = mapped_column(default=0)
    tov: Mapped[int] = mapped_column(default=0)
    fgm: Mapped[int] = mapped_column(default=0)
    fga: Mapped[int] = mapped_column(default=0)
    tpm: Mapped[int] = mapped_column(default=0)
    tpa: Mapped[int] = mapped_column(default=0)
    ftm: Mapped[int] = mapped_column(default=0)
    fta: Mapped[int] = mapped_column(default=0)


class Pick(Base):
    """Kullanıcının (veya misafirin) takip ettiği oyuncu."""

    __tablename__ = "picks"
    __table_args__ = (UniqueConstraint("user_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
