# Veritabanı tablo sürümleri (Alembic)

UAT ve CANLI veritabanı Neon'da (PostgreSQL) ve verisi kalıcı. Tablolarda
yapılan her değişiklik burada bir sürüm dosyası olarak tutulur. Uygulama
açılırken (`app/db.py` → `init_db`) veritabanı kendiliğinden son sürüme
getirilir, elle bir komut çalıştırmak gerekmez.

## Tablo değiştirmek

1. `app/models.py` içinde değişikliği yap.
2. Boş bir SQLite ile yeni sürüm dosyasını üret:

   ```bash
   DATABASE_URL=sqlite:///./data/bos.db python -m alembic upgrade head
   DATABASE_URL=sqlite:///./data/bos.db python -m alembic revision --autogenerate --rev-id 0002 -m "kisa aciklama"
   ```

3. `migrations/versions/` altındaki yeni dosyayı oku ve düzelt. Otomatik
   üretim her şeyi doğru yakalamaz (ör. sütun adı değişikliği silme + ekleme
   sanılır, var olan satırlar için varsayılan değer gerekir).
4. Yerelde ve UAT'de dene. UAT'de veri kalıcı olduğu için geri alma
   (`downgrade`) gerekirse elle yapılır; dikkatli ol.

`--rev-id` sırayla artar: 0002, 0003, ...
