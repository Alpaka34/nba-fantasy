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

## Kendi bilgisayarınızda çalıştırma

```bash
pip install -r requirements.txt
python scripts/setup_env.py   # .env'yi oluşturur (sadece ilk seferde)
python run.py                 # https://localhost:8080
```

Tarayıcı "bağlantınız gizli değil" uyarısı verir. Sebebi yerel sertifikanın
kendinden imzalı olması. "Gelişmiş > localhost'a devam et" ile geçin.

**Yahoo ile giriş için bir kez:** developer.yahoo.com/apps altındaki
uygulamanızda Redirect URI listesine `https://localhost:8080/auth/callback`
ekleyin.

Yahoo API erişimi onaylanana kadar "Demo ile dene" düğmesiyle örnek veri
üzerinde çalışabilirsiniz.

## Yapı

| Yer | Ne işe yarar |
|---|---|
| `app/main.py` | Sayfalar, giriş/çıkış ve `/api/...` JSON uç noktaları (mobil uygulama da bunları kullanacak) |
| `app/yahoo_auth.py` | Yahoo OAuth akışı, kullanıcı başına token saklama ve yenileme |
| `app/providers/` | Veri kaynakları: `yahoo.py` (gerçek), `demo.py` (örnek). Sayfalar sadece ortak arayüzü kullanır |
| `app/cache.py` | Yahoo cevaplarını veritabanında önbelleğe alır (`CACHE_TTL_SECONDS`) |
| `app/scoring.py` | Ligden bağımsız sayfalardaki standart fantasy puanlaması |
| `app/templates/`, `app/static/` | HTML şablonları ve stil |
| `.env` | Tüm ayarlar ve gizli anahtarlar. **Asla paylaşmayın.** |

Yahoo'dan gelen ham cevapları örnek veri olarak saklamak için `.env` içinde
`RECORD_FIXTURES=true` yapın; cevaplar `fixtures/` klasörüne yazılır.

## UAT (test) ortamı: Render

`uat` dalına gönderilen her değişiklik, Render'daki `nba-fantasy-uat` servisine
otomatik yüklenir (ayarlar `render.yaml` içinde). Site demo modunda çalışır.
Ücretsiz planda 15 dakika kullanılmazsa uyur, ilk açılış biraz sürer. Her
yüklemede veritabanı sıfırlanır.

```bash
git push origin uat
```

Onaylanan sürüm `main` dalına alınır; canlı site ileride `main`'den yayınlanacak.

## Alan adı alınca sunucuya taşıma

Kodda değişiklik gerekmez, sadece ayarlar değişir:

1. Sunucuya kodu kopyalayın (`.env`, `certs/`, `data/` hariç).
2. Sunucuda yeni bir `.env` oluşturun (`python scripts/setup_env.py`) ve şunları ayarlayın:
   - `BASE_URL=https://alanadiniz.com`
   - `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET`: yeni başvurudan gelen anahtarlar
   - `DEMO_MODE=false` (isterseniz)
   - Kullanıcı sayısı artınca `DATABASE_URL` ile PostgreSQL'e geçin
3. Yahoo uygulamasına Redirect URI olarak `https://alanadiniz.com/auth/callback` ekleyin.
4. Docker ile çalıştırın; HTTPS sertifikasını Caddy gibi bir ters vekil otomatik alır:
   ```bash
   docker build -t nba-fantasy .
   docker run -d --env-file .env -v nba-data:/data -p 8000:8000 nba-fantasy
   ```

Yayına çıkmadan önce: Yahoo'ya kapsamı genişletilmiş başvuru, gizlilik politikası
sayfası ve Yahoo logolu "Fantasy data provided by Yahoo Fantasy" ibaresi
(gerçek veri gösterilirken altbilgide zaten var; logoyu Yahoo'nun verdiği
haliyle eklemek gerekiyor).
