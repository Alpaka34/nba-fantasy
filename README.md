# NBA Fantasy

A personal, read-only analysis tool for my own Yahoo Fantasy Basketball league
(standings, rosters, player stats, free agents, matchups) to support weekly
lineup and waiver decisions. Single league, personal use; data is not
redistributed.

Fantasy data provided by [Yahoo Fantasy](https://sports.yahoo.com/fantasy/).

## Connection test

Create `oauth2.json` (ignored by git) with your Yahoo app credentials:

```json
{
  "consumer_key": "YOUR_CLIENT_ID",
  "consumer_secret": "YOUR_CLIENT_SECRET"
}
```

Then run the connection test. On first run, approve the app in the browser
and paste the verifier code:

```bash
python test_baglanti.py
```

---

## Web sitesi (geliştirme notları)

Yahoo hesabını bağlayıp lig istatistiklerini gösteren web sitesi. Ligden
bağımsız "haftanın oyuncuları" sayfası da var. Yahoo erişimi onaylanana kadar
demo verisiyle çalışır.

## Ortamlar

| Ortam | Git dalı | Adres | Ne için |
|---|---|---|---|
| Yerel | çalışma kopyası | https://localhost:8080 | Geliştirme |
| **UAT** | `uat` | https://nba-fantasy-uat.onrender.com | Onay öncesi test |
| **CANLI** | `main` | Render: `nba-fantasy` (ilk onaydan sonra; ileride kendi alan adı) | Yayındaki site |

Bütün geliştirme `uat` dalında yapılır ve oraya gönderilince UAT sitesi
otomatik güncellenir. UAT'de incelenip **"uygundur"** onayı verilen sürüm
`main`'e alınır ve CANLI site güncellenir. `main`'e doğrudan değişiklik
yapılmaz.

- Süreç, sürüm numaraları ve geri alma: [docs/SURUM_SURECI.md](docs/SURUM_SURECI.md)
- Onay bekleyen ve yayına alınan değişiklikler: [CHANGELOG.md](CHANGELOG.md)
- Render servis ayarları: [render.yaml](render.yaml)

UAT sitesinde sayfanın üstünde mor bir "UAT test ortamı" şeridi, her ortamda
sayfanın altında sürüm numarası görünür. Bir ortamın sürümü `/healthz`
adresinden de görülebilir.

## Kendi bilgisayarınızda çalıştırma

```bash
pip install -r requirements.txt
python scripts/setup_env.py   # .env'yi oluşturur (sadece ilk seferde)
python run.py                 # https://localhost:8080
```

Tarayıcı "bağlantınız gizli değil" uyarısı verir. Sebebi yerel sertifikanın
kendinden imzalı olması. "Gelişmiş > localhost'a devam et" ile geçin.

Yahoo ile giriş için Yahoo uygulamasındaki Redirect URI listesinde
`https://localhost:8080/auth/callback` olmalı. Yahoo API erişimi onaylanana
kadar "Demo ile dene" düğmesiyle örnek veri üzerinde çalışılır.

## Klasör yapısı

| Yer | Ne işe yarar |
|---|---|
| `app/main.py` | Sayfalar, giriş/çıkış ve `/api/...` JSON uç noktaları (mobil uygulama da bunları kullanacak) |
| `app/config.py` | Bütün ayarlar (`.env` veya ortam değişkenleri), ortam bilgisi (`APP_ENV`) |
| `app/__init__.py` | Sürüm numarası (`__version__`) |
| `app/yahoo_auth.py` | Yahoo OAuth akışı, kullanıcı başına token saklama ve yenileme |
| `app/providers/` | Veri kaynakları: `yahoo.py` (gerçek), `demo.py` (örnek). Sayfalar sadece ortak arayüzü kullanır |
| `app/cache.py` | Yahoo cevaplarını veritabanında önbelleğe alır (`CACHE_TTL_SECONDS`) |
| `app/scoring.py` | Ligden bağımsız sayfalardaki standart fantasy puanlaması |
| `app/templates/`, `app/static/` | HTML şablonları ve stil |
| `scripts/` | `setup_env.py` (.env oluşturur), `make_cert.py` (yerel HTTPS sertifikası) |
| `docs/` | Süreç belgeleri |
| `render.yaml` | UAT ve CANLI servislerinin Render ayarları |
| `CLAUDE.md` | Geliştirmeyi yapan Claude için proje kuralları |
| `test_baglanti.py` | Yahoo bağlantı testi (siteden bağımsız) |
| `.env` | Yerel ayarlar ve gizli anahtarlar. **Asla paylaşılmaz, commit edilmez.** |

Yahoo'dan gelen ham cevapları örnek veri olarak saklamak için `.env` içinde
`RECORD_FIXTURES=true` yapın; cevaplar `fixtures/` klasörüne yazılır.

## Render notları

- Ücretsiz planda servis 15 dakika kullanılmazsa uyur; ilk açılış 30-60 saniye sürebilir.
- Ücretsiz planda disk kalıcı değil: SQLite veritabanı her yüklemede sıfırlanır.
  CANLI'da gerçek kullanıcı verisi saklanmaya başlamadan önce Render PostgreSQL'e
  geçilip `DATABASE_URL` ayarlanmalı.
- Alan adı alınca CANLI servisinin "Settings > Custom Domains" bölümünden
  eklenir, `BASE_URL` güncellenir ve Yahoo uygulamasına yeni Redirect URI eklenir.

## Yayına çıkmadan önce

- Yahoo'ya kapsamı genişletilmiş (çok kullanıcılı) API başvurusu
- Gizlilik politikası sayfası
- Yahoo'nun verdiği haliyle Yahoo Fantasy logosu ve "Fantasy data provided by
  Yahoo Fantasy" ibaresi (ibare gerçek veri gösterilirken altbilgide var)
- CANLI'da PostgreSQL ve `DEMO_MODE=false`
