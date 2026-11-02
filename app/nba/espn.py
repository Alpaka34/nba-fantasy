"""ESPN'in herkese açık (resmi olmayan) NBA servisleri.

Anahtar gerektirmez, ama resmi bir API değildir: ESPN yapısını haber vermeden
değiştirebilir ve kullanım şartları ticari kullanıma izin vermeyebilir.
Geliştirme ve UAT için kullanılıyor; CANLI'da herkese açılmadan önce lisanslı
bir kaynağa geçilmeli (bkz. app/nba/source.py).

Bütün fonksiyonlar sade dict/list döndürür; ESPN'e özgü yapı bu dosyanın
dışına çıkmaz.
"""
from datetime import date, datetime

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
TIMEOUT = 20

_client = httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "nba-fantasy/1.0"})


class EspnError(Exception):
    pass


def _get(path: str, **params) -> dict:
    try:
        resp = _client.get(f"{BASE}/{path}", params=params)
    except httpx.HTTPError as e:
        raise EspnError(f"ESPN'e ulaşılamadı: {e}") from e
    if resp.status_code != 200:
        raise EspnError(f"ESPN cevap vermedi ({resp.status_code}).")
    return resp.json()


def headshot_url(player_id: str, width: int = 120) -> str:
    """Oyuncu fotoğrafı (ESPN resim sunucusu, istenen boyutta kırpılmış)."""
    height = round(width * 0.73)
    return ("https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/"
            f"{player_id}.png&w={width}&h={height}&scale=crop&cquality=60")


def team_logo_url(abbr: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{abbr.lower()}.png"


def _int(value) -> int:
    try:
        return int(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return 0


def _made_attempted(value) -> tuple[int, int]:
    made, _, att = str(value).partition("-")
    return _int(made), _int(att)


# --- Takımlar ve kadrolar ---------------------------------------------------

def fetch_team_ids() -> list[str]:
    data = _get("teams")
    return [t["team"]["id"] for t in data["sports"][0]["leagues"][0]["teams"]]


def fetch_roster(team_id: str) -> list[dict]:
    data = _get(f"teams/{team_id}/roster")
    team = data.get("team", {}).get("abbreviation", "")
    players = []
    for a in data.get("athletes", []):
        injuries = a.get("injuries") or []
        players.append({
            "id": str(a["id"]),
            "name": a.get("displayName", ""),
            "short_name": a.get("shortName", ""),
            "team": team,
            "position": (a.get("position") or {}).get("abbreviation", ""),
            "jersey": a.get("jersey", "") or "",
            "injury": injuries[0].get("status", "") if injuries else "",
        })
    return players


# --- Maçlar -----------------------------------------------------------------

def fetch_scoreboard(day: date) -> list[dict]:
    """Bir NBA günündeki (ABD Doğu saati) maçlar."""
    data = _get("scoreboard", dates=day.strftime("%Y%m%d"))
    games = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        status = e.get("status", {}).get("type", {})
        sides = {}
        for c in comp.get("competitors", []):
            team = c.get("team", {})
            records = c.get("records") or []
            sides[c["homeAway"]] = {
                "abbr": team.get("abbreviation", ""),
                "name": team.get("shortDisplayName") or team.get("displayName", ""),
                "logo": team.get("logo") or team_logo_url(team.get("abbreviation", "")),
                "score": _int(c["score"]) if c.get("score") not in (None, "") else None,
                "winner": bool(c.get("winner")),
                "record": records[0].get("summary", "") if records else "",
            }
        if "home" not in sides or "away" not in sides:
            continue
        games.append({
            "id": str(e["id"]),
            "start_utc": datetime.fromisoformat(e["date"].replace("Z", "+00:00")),
            "state": status.get("state", "pre"),
            "detail": status.get("shortDetail", ""),
            "home": sides["home"],
            "away": sides["away"],
        })
    return games


def fetch_box_score(game_id: str) -> list[dict]:
    """Maçta forma giyen oyuncuların istatistikleri. Oynamayanlar dahil edilmez."""
    data = _get("summary", event=game_id)
    lines = []
    for team_block in data.get("boxscore", {}).get("players", []):
        team = team_block.get("team", {}).get("abbreviation", "")
        for stat_block in team_block.get("statistics", []):
            keys = stat_block.get("keys", [])
            for row in stat_block.get("athletes", []):
                if row.get("didNotPlay") or not row.get("stats"):
                    continue
                s = dict(zip(keys, row["stats"]))
                athlete = row.get("athlete", {})
                fgm, fga = _made_attempted(s.get("fieldGoalsMade-fieldGoalsAttempted"))
                tpm, tpa = _made_attempted(s.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
                ftm, fta = _made_attempted(s.get("freeThrowsMade-freeThrowsAttempted"))
                lines.append({
                    "player_id": str(athlete.get("id")),
                    "name": athlete.get("displayName", ""),
                    "team": team,
                    "position": (athlete.get("position") or {}).get("abbreviation", ""),
                    "starter": bool(row.get("starter")),
                    "minutes": _int(s.get("minutes")),
                    "pts": _int(s.get("points")),
                    "reb": _int(s.get("rebounds")),
                    "ast": _int(s.get("assists")),
                    "stl": _int(s.get("steals")),
                    "blk": _int(s.get("blocks")),
                    "tov": _int(s.get("turnovers")),
                    "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta,
                })
    return lines
