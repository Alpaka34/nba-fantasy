from sqlalchemy.orm import Session

from ..models import User
from .base import DataUnavailable, FantasyProvider
from .demo import DemoProvider
from .yahoo import YahooProvider


def provider_for(db: Session, user: User) -> FantasyProvider | None:
    """Kullanıcının lig verisini hangi kaynaktan alacağımızı seçer.

    Yahoo'ya bağlı olmayan kullanıcının fantasy ligi yoktur (None); onun
    kendi oluşturduğu ligler veritabanındadır (MyLeague). Ligden bağımsız
    NBA verisi (maçlar, oyuncular) app/nba/ altındadır.
    """
    if user.is_demo:
        return DemoProvider()
    if user.token is None:
        return None
    return YahooProvider(db, user)


__all__ = ["DataUnavailable", "FantasyProvider", "provider_for"]
