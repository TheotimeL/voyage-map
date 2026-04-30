"""One-shot: convert each row in `tracks` into a Point with category='trail'.

Idempotent: safe to re-run. Tracks that have already been migrated (i.e., a
trail-point with the same gpx_data already exists for the same map) are
skipped. After a successful run, the `tracks` table is left in place — it is
dropped in a later task once the frontend no longer reads from it.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from sqlalchemy import select

from services.db import SessionLocal
from services.models import Map, Point, Track


def first_coord(gpx_data: str) -> tuple[float, float] | None:
    """Return (lat, lng) of the first trkpt/rtept/wpt, or None if empty."""
    try:
        root = ET.fromstring(gpx_data)
    except ET.ParseError:
        return None
    # GPX namespace is variable; match local-name only.
    for tag in ("trkpt", "rtept", "wpt"):
        for el in root.iter():
            if el.tag.split("}", 1)[-1] == tag:
                lat = el.attrib.get("lat")
                lng = el.attrib.get("lon")
                if lat is not None and lng is not None:
                    try:
                        return float(lat), float(lng)
                    except ValueError:
                        pass
    return None


def migrate() -> int:
    db = SessionLocal()
    migrated = 0
    skipped = 0
    failed: list[int] = []
    try:
        tracks = db.scalars(select(Track)).all()
        for t in tracks:
            coord = first_coord(t.gpx_data)
            if coord is None:
                failed.append(t.id)
                continue
            lat, lng = coord
            existing = db.scalars(
                select(Point).where(
                    Point.map_id == t.map_id,
                    Point.gpx_data == t.gpx_data,
                )
            ).first()
            if existing is not None:
                skipped += 1
                continue
            p = Point(
                map_id=t.map_id,
                lat=lat,
                lng=lng,
                title=t.name,
                comment=None,
                category="trail",
                gpx_data=t.gpx_data,
                color=t.color,
            )
            db.add(p)
            migrated += 1
        db.commit()
    finally:
        db.close()

    print(f"migrated={migrated} skipped={skipped} failed={failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(migrate())
