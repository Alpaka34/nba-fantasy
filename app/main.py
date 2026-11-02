import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .cache import clear_prefix
from .config import settings
from .db import get_db, init_db
from .models import User
from .nba import source as nba_source
from .nba import stats as nba
from .providers import DataUnavailable, provider_for
from .yahoo_auth import YahooAuthError, authorization_url, exchange_code, upsert_user


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.secure_cookies,
    same_site="lax",
    # Misafirin seçtiği oyuncular bu çereze bağlı, uzun tutuluyor
    max_age=60 * 60 * 24 * 365,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["settings"] = settings
templates.env.globals["version"] = __version__
templates.env.globals["nba_source"] = nba_source.NAME
templates.env.globals["team_logo"] = nba_source.team_logo_url


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Giriş yapmış kullanıcı (Yahoo veya demo). Misafir kayıtları giriş sayılmaz."""
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    return None if user is None or user.is_guest else user


def picker(request: Request, db: Session, user: User | None, create: bool = False) -> User | None:
    """Oyuncu seçimlerinin sahibi.

    Yahoo ile bağlanan kullanıcı kendi hesabını kullanır. Diğer herkes (demo
    dahil, çünkü demo hesabı ortak) çereze bağlı bir misafir kaydı kullanır.
    """
    if user and not user.is_demo:
        return user
    guest_id = request.session.get("guest_id")
    guest = db.get(User, guest_id) if guest_id else None
    if guest is None and create:
        guest = User(is_guest=True)
        db.add(guest)
        db.commit()
        request.session["guest_id"] = guest.id
    return guest


def safe_next(url: str, default: str) -> str:
    return url if url.startswith("/") and not url.startswith("//") else default


def parse_day(value: str | None, db: Session) -> date:
    try:
        return date.fromisoformat(value) if value else nba.default_day(db)
    except ValueError:
        return nba.default_day(db)


def require_user(request: Request, user: User | None = Depends(current_user)) -> User:
    if user is None:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=401, detail="Giriş yapılmamış.")
        raise HTTPException(status_code=303, headers={"Location": "/"})
    return user


def home_with_error(message: str) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode({"error": message}), status_code=303)


def render(request: Request, name: str, user: User | None, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx})


# --- Sayfalar -------------------------------------------------------------

@app.get("/")
def index(request: Request, user: User | None = Depends(current_user)):
    if user and not user.is_demo:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "index.html", user, error=request.query_params.get("error"))


@app.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    provider = provider_for(db, user)
    try:
        leagues, error = provider.leagues(), None
    except DataUnavailable as e:
        leagues, error = [], str(e)
    return render(request, "dashboard.html", user, leagues=leagues, error=error,
                  source=provider.source)


@app.get("/league/{league_key}")
def league(league_key: str, request: Request, user: User = Depends(require_user),
           db: Session = Depends(get_db)):
    provider = provider_for(db, user)
    try:
        detail = provider.league_detail(league_key)
        roster = provider.my_roster(league_key)
    except DataUnavailable as e:
        return render(request, "league.html", user, error=str(e), source=provider.source)
    return render(request, "league.html", user, detail=detail, roster=roster,
                  source=provider.source, error=None)


@app.get("/weekly")
def weekly():
    return RedirectResponse("/players", status_code=301)


# --- NBA: maçlar ve oyuncular (Yahoo'dan bağımsız) -------------------------

@app.get("/games")
def games(request: Request, date: str | None = None, user: User | None = Depends(current_user),
          db: Session = Depends(get_db)):
    day = parse_day(date, db)
    return render(request, "games.html", user, day=day, games=nba.games_on(db, day),
                  prev_day=day - timedelta(days=1), next_day=day + timedelta(days=1),
                  source="nba")


@app.get("/games/{game_id}")
def game(game_id: str, request: Request, user: User | None = Depends(current_user),
         db: Session = Depends(get_db)):
    detail = nba.game_detail(db, game_id)
    if detail is None:
        raise HTTPException(404, "Maç bulunamadı.")
    return render(request, "game.html", user, game=detail,
                  picked=nba.picked_ids(db, picker(request, db, user)), source="nba")


@app.get("/players")
def players(request: Request, days: int = 7, q: str = "", user: User | None = Depends(current_user),
            db: Session = Depends(get_db)):
    data = nba.search_players(db, q, days) if q.strip() else nba.leaders(db, days)
    return render(request, "players.html", user, data=data, q=q.strip(), periods=nba.PERIODS,
                  picked=nba.picked_ids(db, picker(request, db, user)), source="nba")


@app.get("/my")
def my_players(request: Request, days: int = 7, user: User | None = Depends(current_user),
               db: Session = Depends(get_db)):
    owner = picker(request, db, user)
    data = nba.my_players(db, owner, days) if owner else None
    return render(request, "my_players.html", user, data=data, periods=nba.PERIODS,
                  days=days, source="nba")


@app.post("/my/add")
def my_add(request: Request, player_id: str = Form(...), next: str = Form("/my"),
           user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    nba.add_pick(db, picker(request, db, user, create=True), player_id)
    return RedirectResponse(safe_next(next, "/my"), status_code=303)


@app.post("/my/remove")
def my_remove(request: Request, player_id: str = Form(...), next: str = Form("/my"),
              user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    owner = picker(request, db, user)
    if owner:
        nba.remove_pick(db, owner, player_id)
    return RedirectResponse(safe_next(next, "/my"), status_code=303)


@app.get("/profile")
def profile(request: Request, user: User = Depends(require_user)):
    return render(request, "profile.html", user, saved=request.query_params.get("saved"))


@app.post("/profile")
def profile_save(display_name: str = Form(""), user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    user.display_name = display_name.strip()[:80]
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)


@app.post("/profile/disconnect")
def profile_disconnect(request: Request, user: User = Depends(require_user),
                       db: Session = Depends(get_db)):
    """Yahoo iznini sistemden siler. Kullanıcı Yahoo hesabından da iznini kaldırabilir."""
    if user.token:
        db.delete(user.token)
    clear_prefix(db, f"yahoo:{user.id}:")
    db.commit()
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.post("/profile/delete")
def profile_delete(request: Request, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    clear_prefix(db, f"yahoo:{user.id}:")
    if not user.is_demo:
        db.delete(user)
        db.commit()
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# --- Giriş / çıkış ----------------------------------------------------------

@app.get("/auth/yahoo")
def auth_yahoo(request: Request):
    if not settings.yahoo_configured:
        return home_with_error("Yahoo girişi bu ortamda henüz açık değil (Yahoo anahtarları tanımlı değil).")
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    return RedirectResponse(authorization_url(state), status_code=303)


@app.get(settings.yahoo_callback_path)
def auth_callback(request: Request, db: Session = Depends(get_db),
                  code: str | None = None, state: str | None = None, error: str | None = None):
    expected = request.session.pop("oauth_state", None)
    if error:
        return home_with_error(f"Yahoo izni verilmedi ({error}).")
    if not code or not state or state != expected:
        return home_with_error("Giriş isteği doğrulanamadı, lütfen tekrar deneyin.")
    try:
        user, is_new = upsert_user(db, exchange_code(code))
    except YahooAuthError as e:
        return home_with_error(str(e))

    # Bağlanmadan önce misafir olarak seçtiği oyuncular hesabına geçer
    guest_id = request.session.pop("guest_id", None)
    guest = db.get(User, guest_id) if guest_id else None
    if guest and guest.is_guest:
        nba.move_picks(db, guest, user)
        db.delete(guest)
        db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse("/profile" if is_new else "/dashboard", status_code=303)


@app.get("/auth/demo")
def auth_demo(request: Request, db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(404)
    user = db.query(User).filter_by(is_demo=True).first()
    if user is None:
        user = User(is_demo=True, display_name="Demo Kullanıcı")
        db.add(user)
        db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    # Misafir oyuncu listesi (guest_id) çıkışta kaybolmasın
    request.session.pop("user_id", None)
    return RedirectResponse("/", status_code=303)


# --- JSON API (ileride mobil uygulama da bunu kullanacak) ------------------

def _api(fn):
    try:
        return fn()
    except DataUnavailable as e:
        return JSONResponse({"error": str(e)}, status_code=503)


@app.get("/api/me")
def api_me(user: User = Depends(require_user)):
    return {"id": user.id, "display_name": user.display_name, "is_demo": user.is_demo,
            "yahoo_connected": user.token is not None}


@app.get("/api/leagues")
def api_leagues(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return _api(lambda: provider_for(db, user).leagues())


@app.get("/api/leagues/{league_key}")
def api_league(league_key: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = provider_for(db, user)
    return _api(lambda: {**p.league_detail(league_key), "roster": p.my_roster(league_key)})


@app.get("/api/nba/games")
def api_games(date: str | None = None, db: Session = Depends(get_db)):
    day = parse_day(date, db)
    return {"date": day.isoformat(), "games": nba.games_on(db, day)}


@app.get("/api/nba/games/{game_id}")
def api_game(game_id: str, db: Session = Depends(get_db)):
    detail = nba.game_detail(db, game_id)
    if detail is None:
        raise HTTPException(404, "Maç bulunamadı.")
    return detail


@app.get("/api/nba/players")
def api_players(days: int = 7, q: str = "", db: Session = Depends(get_db)):
    return nba.search_players(db, q, days) if q.strip() else nba.leaders(db, days)


@app.get("/api/my/players")
def api_my_players(request: Request, days: int = 7, user: User | None = Depends(current_user),
                   db: Session = Depends(get_db)):
    owner = picker(request, db, user)
    return nba.my_players(db, owner, days) if owner else {"players": []}


@app.post("/api/my/players/{player_id}")
def api_my_add(player_id: str, request: Request, user: User | None = Depends(current_user),
               db: Session = Depends(get_db)):
    nba.add_pick(db, picker(request, db, user, create=True), player_id)
    return {"ok": True}


@app.delete("/api/my/players/{player_id}")
def api_my_remove(player_id: str, request: Request, user: User | None = Depends(current_user),
                  db: Session = Depends(get_db)):
    owner = picker(request, db, user)
    if owner:
        nba.remove_pick(db, owner, player_id)
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True, "env": settings.app_env, "version": __version__}
