import base64
import hashlib

from cryptography.fernet import Fernet

from .config import settings

# Ayardaki metin ne biçimde olursa olsun (Render'ın ürettiği rastgele değer
# dahil) ondan geçerli bir Fernet anahtarı türetilir.
_key = base64.urlsafe_b64encode(hashlib.sha256(settings.token_encryption_key.encode()).digest())
_fernet = Fernet(_key)


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()
