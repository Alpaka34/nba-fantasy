"""Yahoo Fantasy API bağlantı testi.

İlk çalıştırmada tarayıcıda Yahoo onay sayfası açılır; çıkan kodu terminale
yapıştırın. Token oauth2.json'a kaydedilir, sonraki çalıştırmalarda sorulmaz.
"""
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

sc = OAuth2(None, None, from_file="oauth2.json")
if not sc.token_is_valid():
    sc.refresh_access_token()

gm = yfa.Game(sc, "nba")
league_ids = gm.league_ids()
print("NBA lig ID'leriniz:", league_ids)

if not league_ids:
    print("Bu hesapta NBA ligi bulunamadı.")
    raise SystemExit

# En son sezonun ligi listenin sonundadır
lg = gm.to_league(league_ids[-1])
settings = lg.settings()
print(f"\nLig: {settings['name']} ({league_ids[-1]})")

print("\nPuan durumu:")
for i, team in enumerate(lg.standings(), 1):
    totals = team.get("outcome_totals", {})
    print(f"  {i:2}. {team['name']:<30} "
          f"{totals.get('wins', '-')}-{totals.get('losses', '-')}-{totals.get('ties', '-')}")

print("\nKadronuz:")
for p in lg.to_team(lg.team_key()).roster():
    print(f"  {p['selected_position']:<5} {p['name']:<25} {'/'.join(p['eligible_positions'])}")
