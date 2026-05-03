"""_migrate_inline — schema patches for SQLite that create_all cannot apply."""

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


def test_add_sleep_location_runs_idempotently(tmp_path, monkeypatch):
    """Simulates an older DB lacking `sleep_location` and verifies migration
    backfills it (and a second run is a no-op)."""
    db_path = tmp_path / "voyage.db"
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(server_module, "engine", test_engine)

    # Build the schema manually without `sleep_location` so we can verify the
    # ALTER TABLE branch fires. (create_all() would already include the column.)
    with test_engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE maps (id INTEGER PRIMARY KEY, slug VARCHAR(16), title VARCHAR(120),"
            " center_lat FLOAT, center_lng FLOAT, radius_m FLOAT, created_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE itinerary_days (id INTEGER PRIMARY KEY, map_id INTEGER,"
            " date DATE, end_date DATE, label VARCHAR(200), lat FLOAT, lng FLOAT, notes TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE points (id INTEGER PRIMARY KEY, map_id INTEGER, lat FLOAT, lng FLOAT,"
            " title VARCHAR(120), comment TEXT, category VARCHAR(20), gpx_data TEXT,"
            " color VARCHAR(20), created_at DATETIME)"
        ))
        assert "sleep_location" not in _table_columns(conn, "itinerary_days")

    server_module._migrate_inline()
    with test_engine.begin() as conn:
        assert "sleep_location" in _table_columns(conn, "itinerary_days")

    # Idempotent — second run is a no-op.
    server_module._migrate_inline()
    with test_engine.begin() as conn:
        assert "sleep_location" in _table_columns(conn, "itinerary_days")


def test_sleep_location_round_trip(tmp_path, monkeypatch):
    """End-to-end: POST, PATCH, GET preserves `sleep_location`."""
    from fastapi.testclient import TestClient

    db_path = tmp_path / "voyage.db"
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(server_module, "engine", test_engine)
    db_module.Base.metadata.create_all(bind=test_engine)

    # Bind a fresh sessionmaker to the patched engine so the API uses it.
    from sqlalchemy.orm import sessionmaker
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session)

    client = TestClient(server_module.app)
    m = client.post(
        "/api/maps",
        json={"title": "t", "center_lat": 0, "center_lng": 0, "radius_m": 10000},
    ).json()
    slug = m["slug"]

    # Create with sleep_location
    created = client.post(
        f"/api/maps/{slug}/itinerary",
        json={"date": "2026-05-09", "label": "Vegas night 1", "sleep_location": "Walmart parking"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["sleep_location"] == "Walmart parking"

    # Patch the sleep_location
    patched = client.patch(
        f"/api/maps/{slug}/itinerary/{body['id']}",
        json={"sleep_location": "Red Rock BLM"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["sleep_location"] == "Red Rock BLM"

    # GET via map → sleep_location is in the row
    got = client.get(f"/api/maps/{slug}").json()
    iti = got["itinerary"][0]
    assert iti["sleep_location"] == "Red Rock BLM"

    # Patching to null clears it
    cleared = client.patch(
        f"/api/maps/{slug}/itinerary/{body['id']}",
        json={"sleep_location": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["sleep_location"] is None
