"""Drive-time calibration on top of OSRM responses.

The public OSRM demo's `car` profile underestimates speeds on rural state
highways in the western US. On Vegas → Zion → Bryce → Page → Death Valley,
implied averages dropped to ~25–45 km/h on legs that Google Maps drives at
70–90 km/h, blowing inter-stop ETAs out by 2–3×.

We can't change the upstream profile, so we post-process: if a leg is long
enough that it's clearly inter-city *and* the implied average speed is below
a sane rural-highway floor, we recompute the duration from a calibrated
target speed for the chosen vehicle profile. Short urban legs are left alone
(OSRM is accurate when traffic + signals dominate).
"""

from __future__ import annotations

from dataclasses import dataclass


# Target rural-highway average speed (km/h) per vehicle profile. Picked to
# reproduce real-world Western-US trip times without overshooting traffic-bound
# urban legs (which are filtered out by MIN_LEG_KM below).
TARGET_SPEEDS_KMH: dict[str, float] = {
    "car": 80.0,
    "van": 70.0,
}
DEFAULT_VEHICLE = "car"

# Below this distance the leg is mostly urban / signal-bound; trust OSRM.
MIN_LEG_KM = 30.0

# Above this raw implied speed OSRM is already in the right ballpark — don't
# touch it (so we don't speed up legitimately slow mountain-pass routes that
# OSRM happens to estimate at 60+ km/h).
MIN_RAW_AVG_KMH = 70.0


@dataclass
class Calibration:
    minutes: float
    raw_minutes: float
    raw_avg_kmh: float
    applied: bool
    vehicle: str


def known_vehicles() -> list[str]:
    return list(TARGET_SPEEDS_KMH.keys())


def calibrate_duration(
    distance_km: float,
    raw_minutes: float,
    vehicle: str = DEFAULT_VEHICLE,
) -> Calibration:
    """Return a (possibly recalibrated) duration for an OSRM leg.

    Calibration only ever shortens the trip — we never make OSRM's duration
    longer, since that would worsen any leg where OSRM was already close.
    """
    vehicle = vehicle if vehicle in TARGET_SPEEDS_KMH else DEFAULT_VEHICLE

    if raw_minutes <= 0 or distance_km <= 0:
        return Calibration(raw_minutes, raw_minutes, 0.0, False, vehicle)

    raw_avg = distance_km / (raw_minutes / 60.0)

    if distance_km < MIN_LEG_KM or raw_avg >= MIN_RAW_AVG_KMH:
        return Calibration(raw_minutes, raw_minutes, raw_avg, False, vehicle)

    target = TARGET_SPEEDS_KMH[vehicle]
    calibrated = distance_km / target * 60.0
    if calibrated >= raw_minutes:
        return Calibration(raw_minutes, raw_minutes, raw_avg, False, vehicle)

    return Calibration(calibrated, raw_minutes, raw_avg, True, vehicle)
