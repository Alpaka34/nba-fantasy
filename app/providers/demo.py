"""Yahoo erişimi olmadan arayüzü geliştirmek için örnek veri. Gerçek değildir."""
import random

DEMO_LEAGUE_KEY = "demo.l.1"

TEAMS = [
    "Boğaziçi Ballers", "Kadıköy Kings", "Anadolu Ankles", "Galata Guards",
    "Moda Mambas", "Üsküdar Untouchables", "Beşiktaş Bricks", "Karaköy Clutch",
    "Maçka Monstars", "Sarıyer Splash",
]

PLAYERS = [
    ("Nikola Jokić", "DEN", "C"), ("Shai Gilgeous-Alexander", "OKC", "PG,SG"),
    ("Giannis Antetokounmpo", "MIL", "PF,C"), ("Luka Dončić", "LAL", "PG,SG"),
    ("Victor Wembanyama", "SAS", "C"), ("Anthony Edwards", "MIN", "SG,SF"),
    ("Jayson Tatum", "BOS", "SF,PF"), ("Tyrese Haliburton", "IND", "PG"),
    ("Domantas Sabonis", "SAC", "C"), ("Alperen Şengün", "HOU", "C"),
    ("Anthony Davis", "DAL", "PF,C"), ("Cade Cunningham", "DET", "PG"),
    ("Trae Young", "ATL", "PG"), ("LaMelo Ball", "CHA", "PG"),
    ("Jalen Brunson", "NYK", "PG"), ("Karl-Anthony Towns", "NYK", "PF,C"),
    ("Devin Booker", "PHX", "SG"), ("Kevin Durant", "HOU", "SF,PF"),
    ("Stephen Curry", "GSW", "PG"), ("Bam Adebayo", "MIA", "C"),
    ("Paolo Banchero", "ORL", "PF"), ("Scottie Barnes", "TOR", "SF,PF"),
    ("Jalen Williams", "OKC", "SG,SF"), ("Evan Mobley", "CLE", "PF,C"),
    ("Donovan Mitchell", "CLE", "PG,SG"), ("Ja Morant", "MEM", "PG"),
    ("Chet Holmgren", "OKC", "PF,C"), ("De'Aaron Fox", "SAS", "PG"),
    ("James Harden", "LAC", "PG"), ("LeBron James", "LAL", "SF,PF"),
]

SLOTS = ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "Util", "Util", "BN", "BN", "BN"]


class DemoProvider:
    source = "demo"

    def leagues(self) -> list[dict]:
        return [{
            "league_key": DEMO_LEAGUE_KEY,
            "name": "Demo Ligi",
            "season": "2026",
            "num_teams": len(TEAMS),
            "scoring_type": "head",
            "current_week": 3,
        }]

    def league_detail(self, league_key: str) -> dict:
        rng = random.Random(f"{league_key}-standings")
        my_key = f"{DEMO_LEAGUE_KEY}.t.1"

        rows = []
        for i, name in enumerate(TEAMS, 1):
            wins = rng.randint(4, 22)
            losses = rng.randint(4, 22)
            ties = rng.randint(0, 3)
            rows.append({"team_key": f"{DEMO_LEAGUE_KEY}.t.{i}", "name": name,
                         "wins": wins, "losses": losses, "ties": ties,
                         "pct": f"{wins / (wins + losses + ties):.3f}",
                         "is_mine": f"{DEMO_LEAGUE_KEY}.t.{i}" == my_key})
        rows.sort(key=lambda r: float(r["pct"]), reverse=True)
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank

        order = rows[:]
        rng.shuffle(order)
        matchups = []
        for a, b in zip(order[::2], order[1::2]):
            matchups.append({"week": 3, "teams": [
                {"team_key": t["team_key"], "name": t["name"],
                 "points": round(rng.uniform(850, 1250), 1), "is_mine": t["is_mine"]}
                for t in (a, b)
            ]})

        return {
            "league": self.leagues()[0],
            "standings": rows,
            "matchups": matchups,
            "my_team": {"team_key": my_key, "name": TEAMS[0]},
        }

    def my_roster(self, league_key: str) -> list[dict]:
        rng = random.Random(f"{league_key}-roster")
        picks = rng.sample(PLAYERS, len(SLOTS))
        statuses = ["", "", "", "", "", "", "DTD", "INJ"]
        return [{"name": name, "team": team, "selected_position": slot,
                 "eligible_positions": pos.split(","), "status": rng.choice(statuses)}
                for slot, (name, team, pos) in zip(SLOTS, picks)]
