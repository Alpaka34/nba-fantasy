from sqlalchemy.orm import Session

from ..models import User
from .base import DataUnavailable, FantasyProvider
from .demo import DemoProvider
from .yahoo import YahooProvider


def provider_for(db: Session, user: User) -> FantasyProvider:
    """Kullanıcının lig verisini hangi kaynaktan alacağımızı seçer."""
    if user.is_demo:
        return DemoProvider()
    return YahooProvider(db, user)


def general_provider() -> FantasyProvider:
    """Ligden bağımsız genel veriler (haftanın oyuncuları vb.) için kaynak.

    Şimdilik örnek veri. İleride lisanslı bir NBA veri sağlayıcısı buraya bağlanacak.
    """
    return DemoProvider()


__all__ = ["DataUnavailable", "FantasyProvider", "provider_for", "general_provider"]
