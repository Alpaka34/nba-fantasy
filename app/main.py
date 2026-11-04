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
from .db import engine, get_db, init_db
from .i18n import COOKIE as LANG_COOKIE, LANGUAGES, get_lang, translator
from .models import MyLeague, User
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


MAX_OWN_LEAGUES = 20


def list_owner(request: Request, db: Session, user: User | None, create: bool = False) -> User | None:
    """Kendi liglerinin (elle seçilen oyuncular) sahibi.

    Giriş yapmamış ziyaretçinin ve Yahoo'ya bağlı kullanıcının kendi ligi olmaz;
    Yahoo'ya bağlı kullanıcının oyuncuları Yahoo kadrosundan gelir. Demo hesabı
    ortak olduğu için demoya giren her tarayıcı çereze bağlı ayrı bir kayıt kullanır.
    """
    if user is None or user.token is not None:
        return None
    if not user.is_demo:
        return user
    guest_id = request.session.get("guest_id")
    guest = db.get(User, guest_id) if guest_id else None
    if guest is None and create:
        guest = User(is_guest=True)
        db.add(guest)
        db.commit()
        request.session["guest_id"] = guest.id
    return guest


def own_league(db: Session, owner: User | None, league_id: int | None) -> MyLeague | None:
    league = db.get(MyLeague, league_id) if owner and league_id else None
    return league if league and league.user_id == owner.id else None


def active_league(request: Request, db: Session, owner: User | None) -> MyLeague | None:
    """☆ ile eklenen oyuncuların gideceği lig: Oyuncularım'da en son açılan kendi ligi."""
    if owner is None:
        return None
    league = own_league(db, owner, request.session.get("active_league"))
    return league or (owner.my_leagues[0] if owner.my_leagues else None)


def create_league(db: Session, owner: User, name: str) -> MyLeague:
    league = MyLeague(user_id=owner.id, name=name.strip()[:60] or f"Ligim {len(owner.my_leagues) + 1}")
    db.add(league)
    db.commit()
    db.refresh(owner)
    return league


def pick_context(request: Request, db: Session, user: User | None) -> dict:
    """Oyuncu listelerindeki ☆ düğmesinin davranışı.

    login: giriş sayfasına götürür · off: gösterilmez (Yahoo kadrosu kullanılır) ·
    pick: etkin kendi ligine ekler/çıkarır (lig yoksa ilk ekleyişte oluşturulur).
    """
    if user is None:
        return {"mode": "login"}
    if user.token is not None:
        return {"mode": "off"}
    league = active_league(request, db, list_owner(request, db, user))
    return {"mode": "pick", "league": league, "picked": nba.picked_ids(league)}


def login_url(next_url: str) -> str:
    return "/login?" + urlencode({"next": next_url})


def current_url(request: Request) -> str:
    return request.url.path + ("?" + request.url.query if request.url.query else "")


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
        raise HTTPException(status_code=303, headers={"Location": login_url(current_url(request))})
    return user


def home_with_error(message: str) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode({"error": message}), status_code=303)


def render(request: Request, name: str, user: User | None, **ctx):
    lang = get_lang(request)
    return templates.TemplateResponse(request, name, {
        "user": user, "lang": lang, "languages": LANGUAGES, "_": translator(lang),
        "here": current_url(request), **ctx,
    })


# --- Sayfalar -------------------------------------------------------------

@app.get("/")
def index(request: Request, tab: str = "games", date: str | None = None, days: int = 7,
          user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    """Ana sayfa: Maçlar ve Oyuncular sekmeleri aynı kutuda."""
    ctx = {}
    if tab == "players":
        ctx.update(data=nba.leaders(db, days, limit=10), periods=nba.PERIODS,
                   pick=pick_context(request, db, user))
    else:
        tab = "games"
        day = parse_day(date, db)
        ctx.update(day=day, games=nba.games_on(db, day),
                   prev_day=day - timedelta(days=1), next_day=day + timedelta(days=1))
    return render(request, "index.html", user, tab=tab, source="nba",
                  error=request.query_params.get("error"), **ctx)


@app.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    provider = provider_for(db, user)
    if provider is None:
        return render(request, "dashboard.html", user, leagues=[], error=None, source=None)
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
    if provider is None:
        return RedirectResponse("/dashboard", status_code=303)
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
                  pick=pick_context(request, db, user), source="nba")


@app.get("/players")
def players(request: Request, days: int = 7, q: str = "", user: User | None = Depends(current_user),
            db: Session = Depends(get_db)):
    data = nba.search_players(db, q, days) if q.strip() else nba.leaders(db, days)
    return render(request, "players.html", user, data=data, q=q.strip(), periods=nba.PERIODS,
                  pick=pick_context(request, db, user), source="nba")


@app.get("/my")
def my_players_old(request: Request):
    """Eski adres."""
    return RedirectResponse("/myplayers" + ("?" + request.url.query if request.url.query else ""),
                            status_code=301)


@app.get("/myplayers")
def my_players(request: Request, league: str = "", days: int = 7, q: str = "",
               user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    """Oyuncularım: her lig bir sekme. Yahoo (veya demo) liglerinin kadrosu otomatik gelir;
    Yahoo'ya bağlı olmayan kullanıcı kendi liglerini oluşturup oyuncu seçer."""
    if user is None:
        return render(request, "my_players.html", user, tabs=[], source="nba")

    tabs, error = [], None
    provider = provider_for(db, user)
    if provider is not None:
        try:
            tabs += [{"key": lg["league_key"], "name": lg["name"], "kind": provider.source}
                     for lg in provider.leagues()]
        except DataUnavailable as e:
            error = str(e)
    owner = list_owner(request, db, user)
    own = {f"my-{lg.id}": lg for lg in (owner.my_leagues if owner else [])}
    tabs += [{"key": key, "name": lg.name, "kind": "own", "id": lg.id} for key, lg in own.items()]

    keys = [t["key"] for t in tabs]
    active = active_league(request, db, owner)
    key = league if league in keys else (
        f"my-{active.id}" if active and not league else (keys[0] if keys else ""))
    current = next((t for t in tabs if t["key"] == key), None)

    data, search, pick = None, None, {"mode": "off"}
    if current and current["kind"] == "own":
        my = own[key]
        request.session["active_league"] = my.id
        data = nba.players_report(db, [{"player_id": p.player_id} for p in my.picks], days)
        pick = {"mode": "pick", "league": my, "picked": nba.picked_ids(my)}
        if q.strip():
            search = nba.search_players(db, q, days, limit=10)
    elif current:
        try:
            data = nba.players_report(db, nba.match_roster(db, provider.my_roster(key)), days)
        except DataUnavailable as e:
            error = str(e)

    return render(request, "my_players.html", user, tabs=tabs, current=current, data=data,
                  search=search, pick=pick, q=q.strip(), error=error, days=days,
                  periods=nba.PERIODS, can_own=user.token is None,
                  max_leagues=MAX_OWN_LEAGUES, source="nba")


def _back(next_url: str) -> RedirectResponse:
    return RedirectResponse(safe_next(next_url, "/myplayers"), status_code=303)


@app.post("/myplayers/add")
def my_add(request: Request, player_id: str = Form(...), league_id: int | None = Form(None),
           next: str = Form("/myplayers"), user: User | None = Depends(current_user),
           db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse(login_url(safe_next(next, "/myplayers")), status_code=303)
    owner = list_owner(request, db, user, create=True)
    if owner is None:
        return _back(next)
    league = own_league(db, owner, league_id) or active_league(request, db, owner)
    if league is None:
        league = create_league(db, owner, "")
    request.session["active_league"] = league.id
    nba.add_pick(db, league, player_id)
    return _back(next)


@app.post("/myplayers/remove")
def my_remove(request: Request, player_id: str = Form(...), league_id: int | None = Form(None),
              next: str = Form("/myplayers"), user: User | None = Depends(current_user),
              db: Session = Depends(get_db)):
    owner = list_owner(request, db, user)
    league = own_league(db, owner, league_id) or active_league(request, db, owner)
    if league:
        nba.remove_pick(db, league, player_id)
    return _back(next)


@app.post("/myplayers/leagues")
def my_league_create(request: Request, name: str = Form(""), user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    owner = list_owner(request, db, user, create=True)
    if owner is None or len(owner.my_leagues) >= MAX_OWN_LEAGUES:
        return _back("/myplayers")
    league = create_league(db, owner, name)
    request.session["active_league"] = league.id
    return _back(f"/myplayers?league=my-{league.id}")


@app.post("/myplayers/leagues/{league_id}/rename")
def my_league_rename(league_id: int, request: Request, name: str = Form(""),
                     user: User = Depends(require_user), db: Session = Depends(get_db)):
    league = own_league(db, list_owner(request, db, user), league_id)
    if league and name.strip():
        league.name = name.strip()[:60]
        db.commit()
    return _back(f"/myplayers?league=my-{league_id}")


@app.post("/myplayers/leagues/{league_id}/delete")
def my_league_delete(league_id: int, request: Request, user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    league = own_league(db, list_owner(request, db, user), league_id)
    if league:
        db.delete(league)
        db.commit()
        request.session.pop("active_league", None)
    return _back("/myplayers")


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

@app.get("/login")
def login(request: Request, next: str = "/", user: User | None = Depends(current_user)):
    next_url = safe_next(next, "/")
    if user:
        return RedirectResponse(next_url, status_code=303)
    return render(request, "login.html", user, next=next_url,
                  error=request.query_params.get("error"))


def _after_login(request: Request) -> RedirectResponse:
    return RedirectResponse(safe_next(request.session.pop("next", "/"), "/"), status_code=303)


@app.get("/auth/yahoo")
def auth_yahoo(request: Request, next: str = "/"):
    if not settings.yahoo_configured:
        return RedirectResponse(login_url(next) + "&" + urlencode(
            {"error": "Yahoo girişi bu ortamda henüz açık değil (Yahoo anahtarları tanımlı değil)."}),
            status_code=303)
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    request.session["next"] = safe_next(next, "/")
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

    request.session["user_id"] = user.id
    if is_new:
        request.session.pop("next", None)
        return RedirectResponse("/profile", status_code=303)
    return _after_login(request)


@app.get("/auth/demo")
def auth_demo(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(404)
    user = db.query(User).filter_by(is_demo=True).first()
    if user is None:
        user = User(is_demo=True, display_name="Demo Kullanıcı")
        db.add(user)
        db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse(safe_next(next, "/"), status_code=303)


@app.get("/logout")
def logout(request: Request):
    # Demoda oluşturulan kendi ligleri (guest_id) çıkışta kaybolmasın
    request.session.pop("user_id", None)
    request.session.pop("active_league", None)
    return RedirectResponse("/", status_code=303)


@app.get("/lang/{code}")
def set_lang(code: str, next: str = "/"):
    response = RedirectResponse(safe_next(next, "/"), status_code=303)
    if code in LANGUAGES:
        response.set_cookie(LANG_COOKIE, code, max_age=60 * 60 * 24 * 365, samesite="lax",
                            secure=settings.secure_cookies)
    return response


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
    p = provider_for(db, user)
    return _api(p.leagues) if p else []


@app.get("/api/leagues/{league_key}")
def api_league(league_key: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = provider_for(db, user)
    if p is None:
        raise HTTPException(404, "Yahoo hesabı bağlı değil.")
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


@app.get("/api/my/leagues")
def api_my_leagues(request: Request, days: int = 7, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    """Kullanıcının kendi ligleri ve oyuncuları (Yahoo ligleri için /api/leagues)."""
    owner = list_owner(request, db, user)
    return {"leagues": [
        {"id": lg.id, "name": lg.name,
         **nba.players_report(db, [{"player_id": p.player_id} for p in lg.picks], days)}
        for lg in (owner.my_leagues if owner else [])
    ]}


def _api_league(request: Request, db: Session, user: User, league_id: int) -> MyLeague:
    league = own_league(db, list_owner(request, db, user), league_id)
    if league is None:
        raise HTTPException(404, "Lig bulunamadı.")
    return league


@app.post("/api/my/leagues/{league_id}/players/{player_id}")
def api_my_add(league_id: int, player_id: str, request: Request,
               user: User = Depends(require_user), db: Session = Depends(get_db)):
    nba.add_pick(db, _api_league(request, db, user, league_id), player_id)
    return {"ok": True}


@app.delete("/api/my/leagues/{league_id}/players/{player_id}")
def api_my_remove(league_id: int, player_id: str, request: Request,
                  user: User = Depends(require_user), db: Session = Depends(get_db)):
    nba.remove_pick(db, _api_league(request, db, user, league_id), player_id)
    return {"ok": True}


@app.get("/healthz")
def healthz():
    # "db": sqlite ise kalıcı veritabanı bağlı değil demektir
    return {"ok": True, "env": settings.app_env, "version": __version__, "db": engine.dialect.name}
