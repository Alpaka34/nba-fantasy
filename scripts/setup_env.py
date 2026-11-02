"""Gizli anahtarları üretip .env dosyasını oluşturur.

Mevcut .env'deki değerlere dokunmaz, sadece boş olanları doldurur.
Yahoo anahtarları oauth2.json'da varsa oradan alınır.
"""
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def main():
    source = ENV if ENV.exists() else EXAMPLE
    lines = source.read_text(encoding="utf-8").splitlines()

    defaults = {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }
    oauth_file = ROOT / "oauth2.json"
    if oauth_file.exists():
        creds = json.loads(oauth_file.read_text(encoding="utf-8"))
        defaults["YAHOO_CLIENT_ID"] = creds.get("consumer_key", "")
        defaults["YAHOO_CLIENT_SECRET"] = creds.get("consumer_secret", "")

    filled = []
    out = []
    for line in lines:
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and not line.lstrip().startswith("#") and not value.strip() and defaults.get(key):
            line = f"{key}={defaults[key]}"
            filled.append(key)
        out.append(line)

    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f".env hazır. Doldurulan alanlar: {', '.join(filled) or 'yok'}")


if __name__ == "__main__":
    main()
