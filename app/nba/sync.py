"""NBA verisini kaynaktan çekip veritabanına yazar.

Ayrı bir zamanlanmış görev yok: bir sayfa belirli günlerin verisine ihtiyaç
duyduğunda eksik veya bayat olanlar çekilir. Biten maçların kutu skorları
bir kez çekilir ve bir daha istenmez; devam eden maçlar birkaç dakikada bir
yenilenir.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import CacheEntry, NbaGame, NbaPlayer, PlayerGameLine
from . import source

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
LIVE_TTL = timedelta(minutes=2)
UPCOMING_TTL = timedelta(minutes=30)
FINISHED_DAY_TTL = timedelta(days=30)
ROSTER_TTL = timedelta(hours=12)
WORKERS = 8

# Aynı anda gelen iki istek aynı veriyi iki kez yazmasın
_lock = threading.Lock()


def nba_today() -> date:
    """NBA'in günü ABD Doğu saatine göre değişir."""
    return datetime.now(ET).date()


def _is_fresh(db: Session, key: str) -> bool:
    entry = db.get(CacheEntry, key)
    return bool(entry and entry.expires_at > utcnow())


def _mark_fresh(db: Session, key: str, ttl: timedelta) -> None:
    db.merge(CacheEntry(key=key, value="1", expires_at=utcnow() + ttl))


def _fetch_all(fn, args: list) -> list:
    """fn'i paralel çağırır; hata veren çağrılar None döner (sayfa eldeki veriyle açılır)."""
    def safe(arg):
        try:
            return fn(arg)
        except source.SourceError as e:
            log.warning("NBA verisi alınamadı (%s): %s", arg, e)
            return None

    if not args:
        return []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(safe, args))


def ensure_players(db: Session) -> None:
    """Takım kadrolarını (isim, pozisyon, sakatlık) günde iki kez yeniler."""
    with _lock:
        if _is_fresh(db, "nba:rosters"):
            return
        try:
            team_ids = source.fetch_team_ids()
        except source.SourceError as e:
            log.warning("Takım listesi alınamadı: %s", e)
            return
        now = utcnow()
        for roster in _fetch_all(source.fetch_roster, team_ids):
            for p in roster or []:
                db.merge(NbaPlayer(updated_at=now, **p))
        _mark_fresh(db, "nba:rosters", ROSTER_TTL)
        db.commit()


def _store_scoreboard(db: Session, day: date, games: list[dict]) -> None:
    for g in games:
        game = db.get(NbaGame, g["id"]) or NbaGame(id=g["id"])
        game.game_date = day
        game.start_utc = g["start_utc"].replace(tzinfo=None)
        game.state = g["state"]
        game.detail = g["detail"]
        game.home_team = g["home"]["abbr"]
        game.away_team = g["away"]["abbr"]
        game.home_score = g["home"]["score"]
        game.away_score = g["away"]["score"]
        game.extra = json.dumps({"home": g["home"], "away": g["away"]})
        db.add(game)

    if day > nba_today():
        ttl = UPCOMING_TTL
    elif games and all(g["state"] == "post" for g in games) and day < nba_today():
        ttl = FINISHED_DAY_TTL
    elif not games and day < nba_today():
        ttl = FINISHED_DAY_TTL
    else:
        ttl = LIVE_TTL
    _mark_fresh(db, f"nba:scoreboard:{day.isoformat()}", ttl)


def _needs_box(game: NbaGame) -> bool:
    if game.state == "post":
        return not game.box_final
    if game.state == "in":
        return game.box_synced_at is None or game.box_synced_at < utcnow() - LIVE_TTL
    return False


def ensure_days(db: Session, days: list[date]) -> None:
    """Verilen günlerin maçlarını ve oynanmış maçların kutu skorlarını günceller."""
    with _lock:
        stale = [d for d in days if not _is_fresh(db, f"nba:scoreboard:{d.isoformat()}")]
        for day, games in zip(stale, _fetch_all(source.fetch_scoreboard, stale)):
            if games is not None:
                _store_scoreboard(db, day, games)
        db.commit()

        pending = [g for g in db.query(NbaGame).filter(NbaGame.game_date.in_(days)) if _needs_box(g)]
        boxes = _fetch_all(source.fetch_box_score, [g.id for g in pending])
        now = utcnow()
        for game, lines in zip(pending, boxes):
            if lines is None:
                continue
            db.query(PlayerGameLine).filter_by(game_id=game.id).delete()
            for line in lines:
                db.add(PlayerGameLine(game_id=game.id, game_date=game.game_date, **line))
            game.box_synced_at = now
            game.box_final = game.state == "post"
        db.commit()


def date_range(end: date, days: int) -> list[date]:
    return [end - timedelta(days=i) for i in range(days - 1, -1, -1)]
