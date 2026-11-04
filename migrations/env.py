"""Alembic, uygulamanın kendi veritabanı bağlantısını ve tablo tanımlarını kullanır."""
from alembic import context

from app import models  # noqa: F401  (tabloların kaydı için)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite ALTER TABLE'ı sınırlı destekler; tabloyu yeniden kurarak değiştirir
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Çevrimdışı mod kullanılmıyor.")
run_migrations_online()
