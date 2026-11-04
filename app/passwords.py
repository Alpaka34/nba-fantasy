"""Şifre özeti (hash). Şifrenin kendisi hiçbir yerde saklanmaz.

scrypt bilerek yavaş ve bellek isteyen bir yöntemdir: veritabanı sızsa bile
şifreleri toplu tahminle bulmak pratikte mümkün olmaz. Her şifreye rastgele bir
tuz eklenir; aynı şifreyi kullanan iki kişinin kaydı bile farklı görünür.

Saklanan biçim: scrypt$n$r$p$tuz$özet (tuz ve özet base64). Ayarlar kayıtta
durduğu için ileride güçlendirilirse eski şifreler yine doğrulanır.
"""
import base64
import hashlib
import hmac
import os

N, R, P = 2**14, 8, 1
SALT_BYTES = 16
KEY_BYTES = 64


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    key = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=KEY_BYTES)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, key = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Olmayan bir kullanıcı adıyla denendiğinde de aynı süre harcansın diye
# (yoksa cevap süresinden hangi adların kayıtlı olduğu anlaşılabilir).
DUMMY_HASH = hash_password(os.urandom(16).hex())
