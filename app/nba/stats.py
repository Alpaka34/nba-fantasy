"""Sayfaların ve JSON API'nin kullandığı NBA sorguları. Hepsi sade dict döndürür."""
import json
import unicodedata
from datetime import date, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import NbaGame, NbaPlayer, Pick, PlayerGameLine, User
from ..scoring import fantasy_points
from . import source
from .sync import date_range, ensure_days, ensure_players, nba_today

LOCAL_TZ = ZoneInfo("Europe/Istanbul")
STAT_FIELDS = ("minutes", "pts", "reb", "ast", "stl", "blk", "tov",
               "fgm", "fga", "tpm", "tpa", "ftm", "fta")
PERIODS = (7, 14)


def default_day(db: Session) -> date:
    """Gösterilecek varsayılan gün: bugün maç başladıysa bugün, yoksa dün."""
    today = nba_today()
    ensure_days(db, [today])
    started = db.query(NbaGame).filter(NbaGame.game_date == today, NbaGame.state != "pre").count()
    return today if started else today - timedelta(days=1)


def _with_extras(line: dict) -> dict:
    line["fpts"] = fantasy_points(line)
    line["headshot"] = source.headshot_url(line["player_id"])
    return line


def _game_dict(g: NbaGame) -> dict:
    extra = json.loads(g.extra or "{}")
    start_local = g.start_utc.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    return {
        "id": g.id,
        "date": g.game_date.isoformat(),
        "state": g.state,
        "detail": g.detail,
        "start_local": start_local.strftime("%H:%M"),
        "start_local_date": start_local.strftime("%d.%m"),
        "home": extra.get("home", {"abbr": g.home_team, "score": g.home_score}),
        "away": extra.get("away", {"abbr": g.away_team, "score": g.away_score}),
    }


def games_on(db: Session, day: date) -> list[dict]:
    ensure_days(db, [day])
    games = db.query(NbaGame).filter_by(game_date=day).order_by(NbaGame.start_utc).all()
    return [_game_dict(g) for g in games]


def game_detail(db: Session, game_id: str) -> dict | None:
    game = db.get(NbaGame, game_id)
    if game is None:
        return None
    ensure_days(db, [game.game_date])
    db.refresh(game)

    lines = (db.query(PlayerGameLine).filter_by(game_id=game_id)
             .order_by(PlayerGameLine.starter.desc(), PlayerGameLine.minutes.desc()).all())
    detail = _game_dict(game)
    for side in ("away", "home"):
        abbr = detail[side]["abbr"]
        detail[side]["players"] = [_with_extras(_line_dict(l)) for l in lines if l.team == abbr]
    return detail


def _line_dict(l: PlayerGameLine) -> dict:
    d = {f: getattr(l, f) for f in STAT_FIELDS}
    d.update(player_id=l.player_id, name=l.name, team=l.team, position=l.position,
             starter=l.starter, game_id=l.game_id, date=l.game_date.isoformat())
    return d


def period_bounds(db: Session, days: int) -> tuple[date, date]:
    days = days if days in PERIODS else PERIODS[0]
    end = default_day(db)
    return end - timedelta(days=days - 1), end


def _aggregate(db: Session, start: date, end: date, player_ids: list[str] | None = None,
               limit: int | None = None) -> list[dict]:
    """Oyuncu başına dönem toplamları, fantasy puanına göre sıralı."""
    ensure_days(db, date_range(end, (end - start).days + 1))

    q = db.query(
        PlayerGameLine.player_id,
        func.max(PlayerGameLine.name),
        func.max(PlayerGameLine.team),
        func.max(PlayerGameLine.position),
        func.count(PlayerGameLine.id),
        *[func.sum(getattr(PlayerGameLine, f)) for f in STAT_FIELDS],
    ).filter(PlayerGameLine.game_date.between(start, end)).group_by(PlayerGameLine.player_id)
    if player_ids is not None:
        q = q.filter(PlayerGameLine.player_id.in_(player_ids))

    rows = []
    for pid, name, team, pos, games, *sums in q:
        row = {"player_id": pid, "name": name, "team": team, "position": pos, "games": games,
               **{f: int(v or 0) for f, v in zip(STAT_FIELDS, sums)}}
        _with_extras(row)
        row["fpts_avg"] = round(row["fpts"] / games, 1) if games else 0
        rows.append(row)
    rows.sort(key=lambda r: r["fpts"], reverse=True)
    return rows[:limit] if limit else rows


def leaders(db: Session, days: int = 7, limit: int = 50) -> dict:
    start, end = period_bounds(db, days)
    return {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1,
            "players": _aggregate(db, start, end, limit=limit)}


def _fold(text: str) -> str:
    """Aksan ve Türkçe karakterleri sadeleştirir: "Şengün" → "sengun", "Dončić" → "doncic"."""
    text = text.replace("ı", "i").replace("İ", "I")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def search_players(db: Session, query: str, days: int = 7, limit: int = 30) -> dict:
    """İsme göre arama; dönemde oynamamış oyuncular da sıfır istatistikle listelenir."""
    ensure_players(db)
    start, end = period_bounds(db, days)
    needle = _fold(query.strip())
    # ~550 oyuncu var; karakter sadeleştirme SQL'de yapılamadığı için Python'da süzülüyor
    found = [p for p in db.query(NbaPlayer).order_by(NbaPlayer.name) if needle in _fold(p.name)][:limit]
    stats = {r["player_id"]: r for r in _aggregate(db, start, end, [p.id for p in found])}
    players = []
    for p in found:
        row = stats.get(p.id) or _with_extras({"player_id": p.id, "games": 0, "fpts_avg": 0,
                                               **{f: 0 for f in STAT_FIELDS}})
        row.update(name=p.name, team=p.team, position=p.position, injury=p.injury)
        players.append(row)
    players.sort(key=lambda r: r["fpts"], reverse=True)
    return {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1,
            "players": players}


# --- Kullanıcının seçtiği oyuncular -------------------------------------------

def picked_ids(db: Session, user: User | None) -> set[str]:
    if user is None:
        return set()
    return {p.player_id for p in db.query(Pick).filter_by(user_id=user.id)}


def my_players(db: Session, user: User, days: int = 7) -> dict:
    ensure_players(db)
    start, end = period_bounds(db, days)
    ids = [p.player_id for p in db.query(Pick).filter_by(user_id=user.id).order_by(Pick.created_at)]
    stats = {r["player_id"]: r for r in _aggregate(db, start, end, ids)}
    info = {p.id: p for p in db.query(NbaPlayer).filter(NbaPlayer.id.in_(ids))}

    players = []
    for pid in ids:
        row = stats.get(pid) or _with_extras({"player_id": pid, "games": 0, "fpts_avg": 0,
                                              **{f: 0 for f in STAT_FIELDS}})
        p = info.get(pid)
        row.update(name=p.name if p else row.get("name", pid),
                   team=p.team if p else row.get("team", ""),
                   position=p.position if p else row.get("position", ""),
                   injury=p.injury if p else "")
        last = (db.query(PlayerGameLine).filter_by(player_id=pid)
                .order_by(PlayerGameLine.game_date.desc()).first())
        row["last_game"] = _with_extras(_line_dict(last)) if last else None
        players.append(row)

    totals = {f: sum(p[f] for p in players) for f in STAT_FIELDS}
    return {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1,
            "players": players, "total_fpts": round(sum(p["fpts"] for p in players), 1),
            "totals": totals}


def add_pick(db: Session, user: User, player_id: str) -> None:
    if not db.query(Pick).filter_by(user_id=user.id, player_id=player_id).first():
        db.add(Pick(user_id=user.id, player_id=player_id))
        db.commit()


def remove_pick(db: Session, user: User, player_id: str) -> None:
    db.query(Pick).filter_by(user_id=user.id, player_id=player_id).delete()
    db.commit()


def move_picks(db: Session, from_user: User, to_user: User) -> None:
    """Misafirin seçtiği oyuncuları (ör. Yahoo'ya bağlanınca) hesabına taşır."""
    existing = picked_ids(db, to_user)
    for pick in list(from_user.picks):
        if pick.player_id not in existing:
            db.add(Pick(user_id=to_user.id, player_id=pick.player_id))
    db.commit()
