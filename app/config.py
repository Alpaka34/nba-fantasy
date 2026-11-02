import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tüm ayarlar .env dosyasından (veya ortam değişkenlerinden) okunur."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NBA Fantasy"
    # Render'da BASE_URL verilmezse servisin kendi adresi kullanılır
    base_url: str = Field(default_factory=lambda: os.environ.get("RENDER_EXTERNAL_URL", "https://localhost:8080"))
    secret_key: str
    token_encryption_key: str
    database_url: str = "sqlite:///./data/app.db"

    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_callback_path: str = "/auth/callback"
    # Boş: uygulamada tanımlı izinlerin hepsi. Uygulamada OpenID izni varsa "openid fspt-r".
    yahoo_scope: str = ""

    demo_mode: bool = True
    cache_ttl_seconds: int = 600
    record_fixtures: bool = False

    @property
    def yahoo_redirect_uri(self) -> str:
        return self.base_url.rstrip("/") + self.yahoo_callback_path

    @property
    def yahoo_configured(self) -> bool:
        return bool(self.yahoo_client_id and self.yahoo_client_secret)

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


settings = Settings()
