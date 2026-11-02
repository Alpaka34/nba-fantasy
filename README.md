# NBA Fantasy

A personal, read-only analysis tool for my own Yahoo Fantasy Basketball league
(standings, rosters, player stats, free agents, matchups) to support weekly
lineup and waiver decisions. Single league, personal use; data is not
redistributed.

Fantasy data provided by [Yahoo Fantasy](https://sports.yahoo.com/fantasy/).

## Setup

```bash
pip install -r requirements.txt
```

Create `oauth2.json` (ignored by git) with your Yahoo app credentials:

```json
{
  "consumer_key": "YOUR_CLIENT_ID",
  "consumer_secret": "YOUR_CLIENT_SECRET"
}
```

Then run the connection test. On first run, approve the app in the browser
and paste the verifier code:

```bash
python test_baglanti.py
```
