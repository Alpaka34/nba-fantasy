"""Site hesapları: e-postasız, kullanıcı adı + şifre ile kayıt ve giriş."""
import re
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from sqlalchemy.orm import Session

from .db import utcnow
from .models import SiteAccount, User
from .passwords import DUMMY_HASH, hash_password, verify_password

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128
MAX_FAILED_LOGINS = 5
LOCK_FOR = timedelta(minutes=15)
SIGNUPS_PER_HOUR = 5


class AccountError(Exception):
    """Kullanıcıya gösterilecek açıklamayla birlikte."""


def normalize(username: str) -> str:
    return username.strip().lower()


def _check_password(password: str, password2: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AccountError(f"Şifre en az {MIN_PASSWORD} karakter olmalı.")
    if len(password) > MAX_PASSWORD:
        raise AccountError(f"Şifre en fazla {MAX_PASSWORD} karakter olabilir.")
    if password != password2:
        raise AccountError("Şifreler birbirini tutmuyor.")


def create_account(db: Session, username: str, password: str, password2: str) -> User:
    name = normalize(username)
    if not USERNAME_RE.match(name):
        raise AccountError("Kullanıcı adı 3-30 karakter olmalı; sadece harf (a-z), rakam, "
                           "nokta, tire ve alt çizgi kullanılabilir.")
    _check_password(password, password2)
    if db.query(SiteAccount).filter_by(username=name).first():
        raise AccountError("Bu kullanıcı adı alınmış.")

    user = User(display_name=username.strip()[:80])
    user.account = SiteAccount(username=name, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, username: str, password: str) -> User:
    account = db.query(SiteAccount).filter_by(username=normalize(username)).first()
    if account is None:
        verify_password(password, DUMMY_HASH)
        raise AccountError("Kullanıcı adı veya şifre hatalı.")

    now = utcnow()
    if account.locked_until and account.locked_until > now:
        minutes = max(1, round((account.locked_until - now).total_seconds() / 60))
        raise AccountError(f"Çok fazla hatalı deneme. {minutes} dakika sonra tekrar deneyin.")

    if not verify_password(password, account.password_hash):
        account.failed_logins += 1
        if account.failed_logins >= MAX_FAILED_LOGINS:
            account.failed_logins = 0
            account.locked_until = now + LOCK_FOR
        db.commit()
        raise AccountError("Kullanıcı adı veya şifre hatalı.")

    account.failed_logins = 0
    account.locked_until = None
    db.commit()
    return account.user


def change_password(db: Session, account: SiteAccount, current: str, new: str, new2: str) -> None:
    if not verify_password(current, account.password_hash):
        raise AccountError("Mevcut şifre hatalı.")
    _check_password(new, new2)
    account.password_hash = hash_password(new)
    db.commit()


# Aynı adresten kısa sürede çok sayıda hesap açılmasın (otomatik kayıtlara karşı).
# Bellekte tutulur; sunucu yeniden başlayınca sıfırlanır, bu yeterli.
_signups: dict[str, deque] = defaultdict(deque)
_signups_lock = threading.Lock()


def signup_allowed(client_ip: str) -> bool:
    """Bu adresten son bir saatte açılan hesap sayısı sınırın altında mı?
    Hatalı doldurulan formlar sayılmaz, sadece açılan hesaplar (record_signup)."""
    now = time.monotonic()
    with _signups_lock:
        recent = _signups[client_ip]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        return len(recent) < SIGNUPS_PER_HOUR


def record_signup(client_ip: str) -> None:
    with _signups_lock:
        _signups[client_ip].append(time.monotonic())
