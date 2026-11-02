# Değişiklik geçmişi

Süreç için bkz. [docs/SURUM_SURECI.md](docs/SURUM_SURECI.md).

## UAT'de bekleyenler

Henüz CANLI'ya alınmamış, onay bekleyen değişiklikler.

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

<!-- CANLI'ya alınan sürümler bu satırın altına eklenir, en yenisi üstte:

## v0.2.0 – 2026-11-10
- ...
-->
