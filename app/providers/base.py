"""Veri kaynaklarının ortak arayüzü.

Sayfalar ve JSON API yalnızca bu arayüzü kullanır; böylece Yahoo, demo veri
veya ileride eklenecek başka bir kaynak birbirinin yerine takılabilir.
Tüm dönüş değerleri JSON'a çevrilebilir sade dict/list yapılarıdır
(önbellekte ve mobil uygulama API'sinde aynen kullanılır).

    LeagueSummary = {league_key, name, season, num_teams, scoring_type, current_week}
    Standing      = {rank, team_key, name, wins, losses, ties, pct, is_mine}
    Matchup       = {week, teams: [{team_key, name, points, is_mine}, ...]}
    RosterPlayer  = {name, team, selected_position, eligible_positions, status}

Ligden bağımsız NBA verisi (maçlar, oyuncu istatistikleri) app/nba/ altındadır.
"""
from typing import Protocol


class DataUnavailable(Exception):
    """Veri şu an alınamıyor (ör. Yahoo API erişimi henüz onaylanmadı)."""


class FantasyProvider(Protocol):
    source: str  # "yahoo" | "demo"

    def leagues(self) -> list[dict]: ...

    def league_detail(self, league_key: str) -> dict:
        """{league, standings, matchups, my_team} döner."""
        ...

    def my_roster(self, league_key: str) -> list[dict]: ...
