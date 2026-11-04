# Sürüm süreci: UAT → CANLI

Bu projede iki ortam var. Hiçbir değişiklik UAT'de görülüp onaylanmadan
CANLI'ya geçmez.

| Ortam | Git dalı | Render servisi | Ne için |
|---|---|---|---|
| **Yerel** | (çalışma kopyası) | yok | Geliştirme, `python run.py` ile https://localhost:8080 |
| **UAT** | `uat` | `nba-fantasy-uat` | Onay öncesi test. Sayfanın üstünde mor "UAT test ortamı" şeridi görünür |
| **CANLI** | `main` | `nba-fantasy` | Kullanıcıların gördüğü site. Sadece onaylanan sürümler |

Her iki servis de `render.yaml` ile tanımlıdır ve kendi dalına push gelince
otomatik yüklenir.

## Akış

```
geliştirme ──push──▶ uat ──(Render)──▶ UAT sitesi ──▶ inceleme
                                                         │
                                         "uygundur" ─────┘
                                              │
                        uat ──merge──▶ main ──(Render)──▶ CANLI sitesi
```

1. **Geliştirme:** Bütün değişiklikler `uat` dalında yapılır. `main` dalına
   doğrudan commit atılmaz.
2. **UAT'ye gönderim:** Değişiklik commit edilip `git push origin uat` ile
   gönderilir. Render birkaç dakika içinde UAT sitesini günceller.
   `CHANGELOG.md` içindeki "UAT'de bekleyenler" bölümüne ne değiştiği yazılır.
3. **İnceleme:** Proje sahibi UAT sitesinde değişikliği kontrol eder.
   Sayfanın altındaki sürüm numarası (`v0.1.0` gibi) hangi sürüme bakıldığını gösterir.
4. **Onay:** Proje sahibi açıkça **"uygundur"** (ya da "CANLI'ya al") demeden
   CANLI'ya geçilmez. Başka bir ifade, sessizlik veya testlerin geçmesi onay sayılmaz.
5. **CANLI'ya alış:**
   1. `app/__init__.py` içindeki `__version__` artırılır (aşağıdaki kurala göre).
   2. `CHANGELOG.md` içinde "UAT'de bekleyenler" yeni sürüm başlığının altına taşınır.
   3. Bu iki değişiklik `uat`'a commit edilip gönderilir.
   4. `main`, `uat`'ın aynısı yapılır ve etiketlenir:
      ```bash
      git switch main
      git merge --ff-only uat
      git tag -a v0.2.0 -m "v0.2.0"
      git push origin main --tags
      git switch uat
      ```
   5. Render CANLI sitesini günceller. `https://nba-fantasy-y4ey.onrender.com/healthz` cevabındaki
      `version` alanı yeni sürümü göstermelidir.

`--ff-only` sayesinde `main`'e UAT'de görülmemiş hiçbir şey giremez. Bu komut
hata verirse `main`'e doğrudan bir değişiklik girmiş demektir; düzeltilmeden
devam edilmez.

## Sürüm numarası

`MAJOR.MINOR.PATCH` (ör. `0.3.1`):

- **PATCH**: Hata düzeltmesi, metin veya görünüm düzeltmesi
- **MINOR**: Yeni sayfa veya özellik
- **MAJOR**: Kullanıcıları etkileyen büyük değişiklik. İlk herkese açık yayında `1.0.0`

## Geri alma

- **Hızlı:** Render panelinde CANLI servisinin "Deploys" sekmesinden önceki
  sürümü seçip **Rollback**. Kod değişmez, sadece eski sürüm çalışır.
- **Kalıcı:** Sorunlu değişiklik `uat`'ta `git revert` ile geri alınır, UAT'de
  kontrol edilir ve normal akışla CANLI'ya alınır.

## Ortam ayarları

Gizli anahtarlar GitHub'a girmez. Render'da her servisin "Environment"
sekmesinden ayrı ayrı girilir. `SECRET_KEY` ve `TOKEN_ENCRYPTION_KEY` Render
tarafından otomatik üretilir ve iki ortamda farklıdır.

| Ayar | UAT | CANLI |
|---|---|---|
| `APP_ENV` | `uat` | `canli` |
| `DEMO_MODE` | `true` | Yahoo onayı gelene kadar `true` |
| `BASE_URL` | Render adresi (otomatik) | Alan adı alınınca `https://alanadiniz.com` |
| `YAHOO_CLIENT_ID` / `SECRET` | Yahoo onayından sonra | Kapsamı genişletilmiş başvurudan sonra |
| `DATABASE_URL` | Neon `uat` dalı (panelden girilir) | Neon ana dal (panelden girilir) |

Veritabanı tabloları değiştiyse (`migrations/versions/` altında yeni dosya)
uygulama açılırken veritabanını kendiliğinden günceller. CANLI'ya alışta bu
değişiklik CANLI'nın kalıcı verisine de uygulanır; önce UAT'de denenmiş olmalı.

Yahoo girişi açılırken her ortamın adresi Yahoo uygulamasına Redirect URI
olarak eklenmelidir: `https://<ortam-adresi>/auth/callback`.
