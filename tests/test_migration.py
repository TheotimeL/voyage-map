"""_migrate_inline — drop legacy itinerary_days.photos column."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

import services.db as db_module
import server as server_module


def _table_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def test_drop_photos_column_runs_idempotently(tmp_path, monkeypatch):
    db_path = tmp_path / "voyage.db"
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    # Patch the engine in both db_module and server_module so _migrate_inline
    # operates on the fresh test DB (avoids module-reload / MetaData conflicts).
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(server_module, "engine", test_engine)

    # Create all tables using the patched engine.
    db_module.Base.metadata.create_all(bind=test_engine)

    # Manually re-add the legacy column to simulate a pre-migration DB.
    with test_engine.begin() as conn:
        conn.execute(text("ALTER TABLE itinerary_days ADD COLUMN photos TEXT"))
        assert "photos" in _table_columns(conn, "itinerary_days")

    # Run _migrate_inline — should drop the column.
    server_module._migrate_inline()

    with test_engine.begin() as conn:
        assert "photos" not in _table_columns(conn, "itinerary_days")

    # Second run — idempotent, no error.
    server_module._migrate_inline()
    with test_engine.begin() as conn:
        assert "photos" not in _table_columns(conn, "itinerary_days")
