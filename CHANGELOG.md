# Değişiklik geçmişi

Süreç için bkz. [docs/SURUM_SURECI.md](docs/SURUM_SURECI.md).

## UAT'de bekleyenler

Henüz CANLI'ya alınmamış, onay bekleyen değişiklikler.

- **Ana sayfa:** Maçlar ve Oyuncular sekmeli tek kutu. Maçlar sekmesinde günün
  maçları (gün değiştirilebilir), Oyuncular sekmesinde son 7 / 14 günün en iyi 10'u
- **Üst menü:** yeni tasarım; sağ üstte dil seçimi (TR / EN) ve "Giriş yap"
  düğmesi, giriş yapınca hesap menüsü. EN seçilse de metinler şimdilik Türkçe;
  İngilizce çeviri altyapısı hazır (`app/i18n.py`)
- **Giriş sayfası** (`/login`): Yahoo ile giriş ve demo hesabı; girişten sonra
  kullanıcı kaldığı sayfaya döner
- **Oyuncularım** yeni adresi `/myplayers` (eski `/my` yönlendirilir). Her lig
  bir sekme: Yahoo (veya demo) liglerinin kadrosu otomatik gelir; Yahoo'ya bağlı
  olmayan kullanıcı kendi liglerini oluşturur, adını değiştirir, siler ve her
  lige ayrı oyuncu seçer
- Oyuncu seçmek artık giriş gerektiriyor; giriş yapmamış ziyaretçi Oyuncularım'da
  bilgilendirme ve giriş bağlantısı görür, ☆ giriş sayfasına götürür
- JSON API: `/api/my/players` yerine `/api/my/leagues` (lig bazlı)
- **Kalıcı veritabanı:** Neon (PostgreSQL) desteği ve Alembic ile tablo
  sürümleri; uygulama açılışta veritabanını kendiliğinden günceller.
  `/healthz` cevabında kullanılan veritabanı (`db`) görünür

<!-- CANLI'ya alınan sürümler bu satırın altına eklenir, en yenisi üstte. -->

## v0.2.0 – 2026-11-04

İlk CANLI sürümü.

- Web sitesi iskeleti: giriş sayfası, Liglerim, lig sayfası (puan durumu,
  eşleşmeler, kadro), Haftanın oyuncuları, Profil
- Kullanıcı başına Yahoo girişi (şifreli token saklama ve otomatik yenileme)
- Yahoo erişimi onaylanana kadar demo verisi
- Mobil uygulama için JSON API (`/api/...`)
- UAT ve CANLI ortamları (Render), ortam şeridi ve sürüm numarası
- **Maçlar:** günlük NBA sonuçları, canlı skor, takım logoları; her maç için
  oyuncu fotoğraflı kutu skor ve fantasy puanı (veri: ESPN)
- **Oyuncular:** son 7 / 14 günün fantasy puanına göre en iyileri, Türkçe
  karakterden bağımsız isim arama
- **Oyuncularım:** Yahoo'ya bağlanmadan ☆ ile oyuncu seçme, seçilenlerin dönem
  toplamları, fantasy puanı ve son maçı. Seçimler tarayıcı çerezine bağlı;
  Yahoo ile bağlanınca hesaba taşınır
- Telefonda alt menü çubuğu
- PostgreSQL desteği (`DATABASE_URL`, ör. Neon)
