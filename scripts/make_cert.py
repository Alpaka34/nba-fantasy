"""Yerel geliştirme için kendinden imzalı HTTPS sertifikası üretir (certs/).

Yahoo, Redirect URI'nin https olmasını istediği için localhost'ta da HTTPS
gerekiyor. Tarayıcı bu sertifikaya "güvenli değil" uyarısı verir; yerelde
"Gelişmiş > Devam et" diyerek geçilebilir. Sunucuda gerçek sertifika kullanılır.
"""
import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = Path(__file__).resolve().parent.parent / "certs"
KEY_FILE = CERT_DIR / "localhost-key.pem"
CERT_FILE = CERT_DIR / "localhost.pem"


def make_cert() -> None:
    CERT_DIR.mkdir(exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False)
        .sign(key, hashes.SHA256())
    )
    KEY_FILE.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Sertifika oluşturuldu: {CERT_FILE}")


if __name__ == "__main__":
    make_cert()
