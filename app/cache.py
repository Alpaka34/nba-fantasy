import json
from datetime import timedelta
from typing import Any, Callable

from sqlalchemy.orm import Session

from .db import utcnow
from .models import CacheEntry


def cached(db: Session, key: str, ttl_seconds: int, fetch: Callable[[], Any]) -> Any:
    """Değeri önbellekten döndürür; yoksa veya süresi geçmişse fetch() ile çekip saklar.

    Yahoo aşırı kullanımı kısıtladığı için aynı veriyi her sayfa açılışında
    yeniden istememek gerekir. Değerler JSON'a çevrilebilir olmalı.
    """
    entry = db.get(CacheEntry, key)
    if entry and entry.expires_at > utcnow():
        return json.loads(entry.value)

    value = fetch()
    db.merge(CacheEntry(
        key=key,
        value=json.dumps(value),
        expires_at=utcnow() + timedelta(seconds=ttl_seconds),
    ))
    db.commit()
    return value


def clear_prefix(db: Session, prefix: str) -> None:
    db.query(CacheEntry).filter(CacheEntry.key.startswith(prefix)).delete(synchronize_session=False)
    db.commit()
