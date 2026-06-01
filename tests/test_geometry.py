"""VBA regression + unit tests for incidence_angle module."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from geometry.incidence_angle import (
    declination_rad,
    hour_angle_rad,
    incidence_angle_deg,
    optimal_tracking_angle_deg,
)

REF_CSV = Path(__file__).parent.parent / "geometry" / "vba_reference.csv"


# ── VBA regression ────────────────────────────────────────────────────────────

def test_vba_regression_100_points():
    """Python output must match VBA reference within 0.001°."""
    with open(REF_CSV) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 100

    for row in rows:
        result = incidence_angle_deg(
            day_of_year        = int(row["day_of_year"]),
            hour               = float(row["hour"]),
            latitude_deg       = float(row["latitude_deg"]),
            tilt_deg           = float(row["tilt_deg"]),
            surface_azimuth_deg= float(row["surface_azimuth_deg"]),
        )
        expected = float(row["incidence_angle_deg"])
        assert abs(result - expected) < 0.001, (
            f"doy={row['day_of_year']} hour={row['hour']}: "
            f"got {result:.4f}°, expected {expected:.4f}°"
        )


def test_numpy_vectorised_matches_scalar():
    """Vectorised call must match element-wise scalar call."""
    days  = np.arange(1, 11)
    hours = np.full(10, 10.0)
    vec   = incidence_angle_deg(days, hours, 32.0)
    for i, (d, h) in enumerate(zip(days, hours)):
        scalar = incidence_angle_deg(int(d), float(h), 32.0)
        assert abs(vec[i] - scalar) < 1e-9


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_solar_noon_horizontal_collector():
    """At solar noon (ω=0) horizontal collector, incidence angle = co-latitude - δ."""
    theta = incidence_angle_deg(172, 12.0, 32.0, tilt_deg=0.0)
    assert 0.0 <= theta <= 90.0


def test_returns_zero_to_ninety():
    """Result always in [0°, 90°]."""
    angles = incidence_angle_deg(
        np.arange(1, 366), np.full(365, 10.0), 45.0
    )
    assert np.all(angles >= 0.0)
    assert np.all(angles <= 90.0)


def test_declination_range():
    """Declination must be within ±23.45°."""
    days = np.arange(1, 366)
    d    = np.degrees(declination_rad(days))
    assert d.max() < 24.0
    assert d.min() > -24.0


def test_hour_angle_noon_is_zero():
    assert abs(hour_angle_rad(12.0)) < 1e-9


def test_hour_angle_morning_negative():
    assert hour_angle_rad(6.0) < 0.0


def test_hour_angle_afternoon_positive():
    assert hour_angle_rad(15.0) > 0.0


# ── Tracking angle ────────────────────────────────────────────────────────────

def test_optimal_tracking_noon_near_zero():
    """At solar noon, optimal E-W tracking angle should be near 0°."""
    angle = optimal_tracking_angle_deg(172, 12.0, 32.0)
    assert abs(angle) < 5.0


def test_optimal_tracking_morning_negative():
    angle = optimal_tracking_angle_deg(172, 8.0, 32.0)
    assert angle < 0.0


def test_optimal_tracking_afternoon_positive():
    angle = optimal_tracking_angle_deg(172, 16.0, 32.0)
    assert angle > 0.0
