"""Yahoo OAuth 2.0 (authorization code) akışı ve kullanıcı başına token yönetimi."""
import base64
import json
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .crypto import decrypt, encrypt
from .db import utcnow
from .models import User, YahooToken

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
USERINFO_URL = "https://api.login.yahoo.com/openid/v1/userinfo"
FANTASY_ME_URL = "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1"

# Token süresi dolmadan bu kadar önce yenilenir
REFRESH_MARGIN = timedelta(minutes=2)


class YahooAuthError(Exception):
    pass


def authorization_url(state: str) -> str:
    params = {
        "client_id": settings.yahoo_client_id,
        "redirect_uri": settings.yahoo_redirect_uri,
        "response_type": "code",
        "state": state,
    }
    # Boşsa Yahoo, uygulamada tanımlı izinlerin hepsini verir
    if settings.yahoo_scope:
        params["scope"] = settings.yahoo_scope
    return f"{AUTH_URL}?{urlencode(params)}"


def _token_request(data: dict) -> dict:
    data = {**data, "redirect_uri": settings.yahoo_redirect_uri}
    try:
        resp = httpx.post(
            TOKEN_URL,
            data=data,
            auth=(settings.yahoo_client_id, settings.yahoo_client_secret),
            timeout=15,
        )
    except httpx.HTTPError as e:
        raise YahooAuthError(f"Yahoo'ya ulaşılamadı: {e}") from e
    if resp.status_code != 200:
        raise YahooAuthError(f"Yahoo token isteği başarısız ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def exchange_code(code: str) -> dict:
    """Yahoo'nun geri yönlendirmede verdiği kodu tokena çevirir.

    Cevapta kullanıcının kalıcı kimliği 'xoauth_yahoo_guid' olarak gelir.
    """
    return _token_request({"grant_type": "authorization_code", "code": code})


def save_token(db: Session, user: User, payload: dict) -> None:
    token = user.token or YahooToken(user=user)
    token.access_token_enc = encrypt(payload["access_token"])
    if payload.get("refresh_token"):
        token.refresh_token_enc = encrypt(payload["refresh_token"])
    token.expires_at = utcnow() + timedelta(seconds=int(payload.get("expires_in", 3600)))
    db.add(token)
    db.commit()


def get_access_token(db: Session, user: User) -> str:
    """Geçerli bir access token döndürür; süresi dolmak üzereyse yeniler."""
    token = user.token
    if token is None:
        raise YahooAuthError("Bu kullanıcı Yahoo hesabını bağlamamış.")

    if token.expires_at - REFRESH_MARGIN <= utcnow():
        payload = _token_request({
            "grant_type": "refresh_token",
            "refresh_token": decrypt(token.refresh_token_enc),
        })
        save_token(db, user, payload)

    return decrypt(token.access_token_enc)


def _id_token_subject(id_token: str) -> str | None:
    """OpenID id_token içindeki kullanıcı kimliğini (sub) okur.

    Token, Yahoo'nun token adresinden doğrudan TLS üzerinden alındığı için
    imza doğrulaması yerine sadece hedef kitlenin (aud) bizim uygulama
    olduğu kontrol ediliyor (OpenID Connect Core 3.1.3.7).
    """
    try:
        body = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (IndexError, ValueError):
        return None
    aud = claims.get("aud")
    if settings.yahoo_client_id not in (aud if isinstance(aud, list) else [aud]):
        return None
    return claims.get("sub")


def _find_key(obj, key):
    """İç içe dict/list yapısında verilen anahtarın ilk değerini bulur."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for item in obj:
            if (found := _find_key(item, key)) is not None:
                return found
    return None


def _user_id_from(payload: dict) -> str:
    """Yahoo kullanıcısının kalıcı kimliğini bulur.

    Yahoo artık token cevabına xoauth_yahoo_guid koymuyor. Kimlik ya OpenID
    ile (uygulamada OpenID izni varsa) ya da Fantasy API'nin "giriş yapan
    kullanıcı" kaydından gelir. Uygulamamızda OpenID izni yok ve sonradan
    eklenemiyor, bu yüzden pratikte Fantasy API yolu kullanılıyor.
    """
    if payload.get("xoauth_yahoo_guid"):
        return payload["xoauth_yahoo_guid"]
    if payload.get("id_token") and (sub := _id_token_subject(payload["id_token"])):
        return sub

    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    try:
        resp = httpx.get(USERINFO_URL, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.json().get("sub"):
            return resp.json()["sub"]

        resp = httpx.get(FANTASY_ME_URL, params={"format": "json"}, headers=headers, timeout=15)
    except httpx.HTTPError as e:
        raise YahooAuthError(f"Yahoo'ya ulaşılamadı: {e}") from e
    if resp.status_code == 200 and (guid := _find_key(resp.json(), "guid")):
        return guid
    if resp.status_code == 403:
        raise YahooAuthError(
            "Yahoo girişi başarılı, ancak Yahoo Fantasy API erişiminiz henüz onaylanmadığı "
            "için hesabınız tanınamıyor. Onay gelene kadar 'Demo ile dene' seçeneğini kullanabilirsiniz.")
    raise YahooAuthError(f"Yahoo kullanıcı kimliği alınamadı ({resp.status_code}).")


def upsert_user(db: Session, payload: dict) -> tuple[User, bool]:
    """Yahoo kimliğine göre kullanıcıyı bulur ya da oluşturur. (kullanıcı, yeni_mi) döner."""
    guid = _user_id_from(payload)

    user = db.query(User).filter_by(yahoo_guid=guid).one_or_none()
    is_new = user is None
    if is_new:
        user = User(yahoo_guid=guid)
        db.add(user)
        db.flush()
    save_token(db, user, payload)
    return user, is_new
