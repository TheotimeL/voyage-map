"""Drive-time calibration covers the four legs that surfaced the
rural-highway speed bug on a Vegas → SF trip. Each leg's `raw` minutes are
what the public OSRM demo returned; `target` minutes are Google Maps'
quoted drive time. ±50% is loose, but it cleanly separates the broken
state (where some legs were ~3× too long) from the calibrated output."""

from __future__ import annotations

import pytest

from services.routing import (
    DEFAULT_VEHICLE,
    TARGET_SPEEDS_KMH,
    calibrate_duration,
    known_vehicles,
)


WESTERN_US_LEGS = [
    # name, distance_km, raw_osrm_minutes, google_minutes
    ("vegas_to_zion",       260.0, 212.0, 165.0),
    ("zion_to_bryce",       115.0, 294.0, 105.0),
    ("bryce_to_page",       240.0, 335.0, 120.0),
    ("page_to_death_valley", 700.0, 633.0, 420.0),
]


@pytest.mark.parametrize("name,km,raw,google", WESTERN_US_LEGS)
def test_calibrated_duration_within_tolerance(name, km, raw, google):
    cal = calibrate_duration(km, raw, "car")
    tolerance = 0.5
    low = google * (1 - tolerance)
    high = google * (1 + tolerance)
    assert low <= cal.minutes <= high, (
        f"{name}: calibrated {cal.minutes:.0f}min outside ±50% of Google {google}min "
        f"(raw OSRM was {raw}min; raw avg {cal.raw_avg_kmh:.0f} km/h)"
    )


def test_short_urban_leg_is_left_alone():
    # 12 km city leg @ 30 min is realistic urban traffic (24 km/h).
    cal = calibrate_duration(12.0, 30.0, "car")
    assert cal.minutes == 30.0
    assert cal.applied is False


def test_fast_freeway_leg_is_left_alone():
    # Tahoe → SF: ~320 km in 257 min → 75 km/h. OSRM was already accurate.
    cal = calibrate_duration(320.0, 257.0, "car")
    assert cal.minutes == 257.0
    assert cal.applied is False


def test_calibration_never_increases_duration():
    # If the calibrated estimate would be slower than OSRM's raw, fall back
    # to raw — calibration only ever shortens broken legs.
    cal = calibrate_duration(50.0, 30.0, "car")  # 100 km/h raw
    assert cal.minutes == 30.0
    assert cal.applied is False


def test_van_profile_is_slower_than_car():
    # Same broken raw, different vehicle: van should produce a slightly
    # longer calibrated duration than car (lower target speed).
    car = calibrate_duration(240.0, 335.0, "car")
    van = calibrate_duration(240.0, 335.0, "van")
    assert car.applied and van.applied
    assert van.minutes > car.minutes


def test_unknown_vehicle_falls_back_to_default():
    cal = calibrate_duration(240.0, 335.0, "tractor")
    expected = calibrate_duration(240.0, 335.0, DEFAULT_VEHICLE)
    assert cal.minutes == expected.minutes
    assert cal.vehicle == DEFAULT_VEHICLE


def test_zero_inputs_are_safe():
    cal = calibrate_duration(0.0, 0.0, "car")
    assert cal.minutes == 0.0
    assert cal.applied is False


def test_known_vehicles_covers_target_table():
    assert set(known_vehicles()) == set(TARGET_SPEEDS_KMH)
