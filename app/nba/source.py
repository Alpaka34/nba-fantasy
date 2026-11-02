"""Kullanılan NBA veri kaynağı.

Kaynak değiştirilecekse (ör. lisanslı bir servise geçiş) yeni modül aynı
fonksiyonları sağlamalı ve buradaki içe aktarma değiştirilmeli:

    fetch_team_ids() -> [team_id]
    fetch_roster(team_id) -> [{id, name, short_name, team, position, jersey, injury}]
    fetch_scoreboard(day) -> [{id, start_utc, state, detail, home: {...}, away: {...}}]
    fetch_box_score(game_id) -> [{player_id, name, team, position, starter, minutes, pts, ...}]
    headshot_url(player_id, width) -> str
    team_logo_url(abbr) -> str
"""
from .espn import (  # noqa: F401
    EspnError as SourceError,
    fetch_box_score,
    fetch_roster,
    fetch_scoreboard,
    fetch_team_ids,
    headshot_url,
    team_logo_url,
)

NAME = "ESPN"
