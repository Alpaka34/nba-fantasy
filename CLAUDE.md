# Claude için proje kuralları

Bu projede bütün geliştirmeyi Claude yapar; proje sahibi inceler ve onaylar.
Proje sahibiyle Türkçe konuşulur. Komutları ona tarif etmek yerine,
yapılabiliyorsa Claude kendisi çalıştırır.

## Ortamlar ve dallar (zorunlu)

Ayrıntılar: [docs/SURUM_SURECI.md](docs/SURUM_SURECI.md)

- UAT: https://nba-fantasy-uat.onrender.com (Render servisi `nba-fantasy-uat`)
- CANLI: Render servisi `nba-fantasy`. İlk onaya kadar `main`'de site kodu
  olmadığı için deploy'u "failed" görünür; bu beklenen bir durum.

- Bütün işler `uat` dalında yapılır. **`main`'e doğrudan commit atılmaz.**
- İş bitince: test et → `CHANGELOG.md` içindeki "UAT'de bekleyenler"e ekle →
  commit → `git push origin uat`. Ardından proje sahibine UAT'de neye
  bakacağını söyle.
- **CANLI'ya alış sadece proje sahibi açıkça "uygundur" ya da "CANLI'ya al"
  dediğinde yapılır.** Önceki bir onay sonraki değişiklikleri kapsamaz.
  Belirsizse sor.
- CANLI'ya alış adımları (sürüm artırma, CHANGELOG, `merge --ff-only`, etiket)
  SURUM_SURECI.md'deki sırayla yapılır. Sonra CANLI `/healthz` adresinden
  yeni sürüm doğrulanır.

## Kod

- Python 3.11, FastAPI + Jinja şablonları, SQLAlchemy. Node yok.
- Fantasy lig sayfaları veriyi sadece `app/providers/` arayüzünden alır. Yahoo'ya
  özel kod `providers/yahoo.py` ve `yahoo_auth.py` dışına taşmaz.
- Ligden bağımsız NBA verisi `app/nba/` altında; şu an ESPN'in resmi olmayan
  servisi (`espn.py`). ESPN'e özgü yapı `espn.py` dışına çıkmaz; kaynak
  `source.py`'den değiştirilir. CANLI'da herkese açılmadan önce lisanslı
  kaynağa geçilmesi gerektiği proje sahibine söylendi.
- Oyuncu seçimleri (`Pick`) Yahoo kullanıcısına ya da çereze bağlı misafir
  kaydına (`User.is_guest`) aittir; demo hesabı ortak olduğu için demo
  kullanıcısının seçimleri de misafir kaydına yazılır.
- Şema değişikliği: migration aracı yok; `create_all` sadece yeni tablo
  oluşturur. Var olan tabloya sütun eklenecekse önce Alembic kurulmalı
  (Neon'daki veri kalıcı).
- Ayarlar `app/config.py` üzerinden, `.env` veya ortam değişkenlerinden gelir.
  Ortama göre davranış `settings.app_env` (`local` / `uat` / `canli`) ile ayrılır.
- Gizli bilgiler (`.env`, `oauth2.json`, `certs/`) asla commit edilmez.
  Commit'ten önce `git diff --cached` kontrol edilir.
- README'nin en üstündeki İngilizce bölüm Yahoo başvurusu için yazıldı;
  korunur.

## Yerel çalıştırma ve test

- `python run.py` → https://localhost:8080 (kendinden imzalı sertifika).
- Tarayıcı paneli bu sertifikayı kabul etmez. Görsel kontrol için ikinci bir
  örnek açılır:
  `BASE_URL=http://localhost:8081 python -m uvicorn app.main:app --port 8081`
- Hızlı kontrol için `fastapi.testclient.TestClient` ile bütün sayfalar
  demo girişiyle gezilir.

## Yahoo durumu

Yahoo Fantasy API erişimi başvurusu onay bekliyor (kişisel kullanım). Onay
gelene kadar her Yahoo isteği 403 döner ve kullanıcı kimliği de alınamaz;
bu beklenen bir durumdur. Uygulamada OpenID izni yok ve sonradan eklenemiyor,
kimlik Fantasy API'nin `users;use_login=1` cevabından alınır.
