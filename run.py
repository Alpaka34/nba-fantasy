"""Siteyi kendi bilgisayarınızda https://localhost:8080 adresinde başlatır.

    python run.py

Kod değiştikçe sunucu otomatik yeniden başlar. Sunucuya taşırken bu dosya
kullanılmaz (bkz. README, Dockerfile).
"""
import uvicorn

from scripts.make_cert import CERT_FILE, KEY_FILE, make_cert

if __name__ == "__main__":
    if not CERT_FILE.exists():
        make_cert()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8080,
        ssl_keyfile=str(KEY_FILE),
        ssl_certfile=str(CERT_FILE),
        reload=True,
    )
