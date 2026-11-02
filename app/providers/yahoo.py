"""Gerçek Yahoo Fantasy verisi (kullanıcının kendi tokenıyla)."""
import json
import re
from pathlib import Path

import requests
import yahoo_fantasy_api as yfa
from sqlalchemy.orm import Session

from ..cache import cached
from ..config import settings
from ..models import User
from ..yahoo_auth import get_access_token
from .base import DataUnavailable

FIXTURES_DIR = Path("fixtures")


class RecordingSession(requests.Session):
    """Yahoo'dan gelen ham JSON cevapları fixtures/ klasörüne kaydeder.

    Bu kayıtlar ileride testlerde ve Yahoo'ya erişilemediğinde örnek veri
    olarak kullanılabilir.
    """

    def get(self, url, **kwargs):
        resp = super().get(url, **kwargs)
        if resp.ok:
            FIXTURES_DIR.mkdir(exist_ok=True)
            path = url.split("/fantasy/v2/", 1)[-1]
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", path)[:150]
            (FIXTURES_DIR / f"{name}.json").write_text(
                json.dumps(resp.json(), indent=2, ensure_ascii=False), encoding="utf-8")
        return resp


class _TokenSession:
    """yahoo_fantasy_api'nin beklediği 'sc' nesnesi: sadece .session gerekiyor.

    Token yenilemeyi kütüphaneye bırakmıyoruz; get_access_token() her istekten
    önce gerekirse yeniliyor.
    """

    def __init__(self, access_token: str):
        self.session = RecordingSession() if settings.record_fixtures else requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"


def _wrap_errors(fn):
    try:
        return fn()
    except RuntimeError as e:
        text = str(e)
        if "not authorized" in text:
            raise DataUnavailable(
                "Yahoo Fantasy API erişiminiz henüz onaylanmadı. Onay gelene kadar "
                "'Demo ile dene' seçeneğini kullanabilirsiniz.") from e
        raise DataUnavailable(f"Yahoo'dan veri alınamadı: {text[:300]}") from e


def _find_all(obj, key):
    """İç içe dict/list yapısında verilen anahtarın bütün değerlerini bulur."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from _find_all(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from _find_all(item, key)


def _parse_matchups(raw: dict, my_team_key: str | None) -> list[dict]:
    """Yahoo scoreboard cevabını sade bir listeye çevirir.

    Yahoo'nun JSON yapısı çok iç içe; gerçek cevaplarla doğrulanana kadar
    hata durumunda boş liste döner.
    """
    matchups = []
    for m in _find_all(raw, "matchup"):
        teams = []
        for t in _find_all(m.get("teams", {}), "team"):
            meta = {}
            for part in t[0] if t and isinstance(t[0], list) else []:
                if isinstance(part, dict):
                    meta.update(part)
            points = next(_find_all(t, "team_points"), {}) or {}
            teams.append({
                "team_key": meta.get("team_key"),
                "name": meta.get("name", "?"),
                "points": float(points.get("total") or 0),
                "is_mine": meta.get("team_key") == my_team_key,
            })
        if teams:
            matchups.append({"week": m.get("week"), "teams": teams})
    return matchups


class YahooProvider:
    source = "yahoo"

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _sc(self) -> _TokenSession:
        return _TokenSession(get_access_token(self.db, self.user))

    def _cached(self, name: str, fetch):
        key = f"yahoo:{self.user.id}:{name}"
        return cached(self.db, key, settings.cache_ttl_seconds, lambda: _wrap_errors(fetch))

    def leagues(self) -> list[dict]:
        def fetch():
            sc = self._sc()
            result = []
            for key in yfa.Game(sc, "nba").league_ids():
                s = yfa.League(sc, key).settings()
                result.append({
                    "league_key": key,
                    "name": s.get("name", key),
                    "season": s.get("season"),
                    "num_teams": s.get("num_teams"),
                    "scoring_type": s.get("scoring_type"),
                    "current_week": s.get("current_week"),
                })
            # En yeni sezon başta
            return sorted(result, key=lambda l: str(l["season"]), reverse=True)

        return self._cached("leagues", fetch)

    def league_detail(self, league_key: str) -> dict:
        def fetch():
            lg = yfa.League(self._sc(), league_key)
            s = lg.settings()
            teams = lg.teams()
            mine = next((t for t in teams.values() if t.get("is_owned_by_current_login")), None)
            my_key = mine["team_key"] if mine else None

            standings = []
            for t in lg.standings():
                totals = t.get("outcome_totals", {})
                standings.append({
                    "rank": t.get("rank"),
                    "team_key": t.get("team_key"),
                    "name": t.get("name"),
                    "wins": totals.get("wins"),
                    "losses": totals.get("losses"),
                    "ties": totals.get("ties"),
                    "pct": totals.get("percentage"),
                    "is_mine": t.get("team_key") == my_key,
                })

            try:
                matchups = _parse_matchups(lg.matchups(), my_key)
            except Exception:
                matchups = []

            return {
                "league": {
                    "league_key": league_key,
                    "name": s.get("name"),
                    "season": s.get("season"),
                    "num_teams": s.get("num_teams"),
                    "scoring_type": s.get("scoring_type"),
                    "current_week": s.get("current_week"),
                },
                "standings": standings,
                "matchups": matchups,
                "my_team": {"team_key": my_key, "name": mine.get("name")} if mine else None,
            }

        return self._cached(f"league:{league_key}", fetch)

    def my_roster(self, league_key: str) -> list[dict]:
        my_team = self.league_detail(league_key).get("my_team")
        if not my_team:
            return []

        def fetch():
            roster = yfa.Team(self._sc(), my_team["team_key"]).roster()
            return [{
                "name": p.get("name"),
                "team": p.get("editorial_team_abbr", ""),
                "selected_position": p.get("selected_position"),
                "eligible_positions": p.get("eligible_positions", []),
                "status": p.get("status", ""),
            } for p in roster]

        return self._cached(f"roster:{my_team['team_key']}", fetch)

    def weekly_top_players(self, limit: int = 25) -> dict:
        raise DataUnavailable("Ligden bağımsız oyuncu istatistikleri için veri kaynağı henüz bağlanmadı.")
