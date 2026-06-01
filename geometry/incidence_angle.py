"""
Incidence-angle calculator for parabolic-trough collectors.

Ported from legacy VBA macro IncidenceAngle.bas.

Formula (east–west horizontal axis collector):
    cos θ_i = sqrt(cos²(δ)·cos²(ω) + sin²(δ))   ... simplified for E-W tracking

Full tilted-surface formula (ASHRAE / Duffie & Beckman):
    cos θ_i = cos(δ)·cos(ω)·cos(Σ)
            - sin(φ)·sin(δ)·sin(Σ)
            + cos(φ)·sin(δ)·cos(Σ)·cos(γ_s)

where:
    δ  = solar declination (rad)
    ω  = hour angle (rad); ω = 0 at solar noon, negative in morning
    Σ  = collector tilt (rad); 0 = horizontal
    φ  = latitude (rad)
    γ_s = surface azimuth (rad); 0 = south, π = north
"""

from __future__ import annotations

import math
import numpy as np


def declination_rad(day_of_year: int | np.ndarray) -> float | np.ndarray:
    """Solar declination δ (radians) via Spencer formula."""
    B = 2 * np.pi * (day_of_year - 1) / 365
    return (
        0.006918
        - 0.399912 * np.cos(B)
        + 0.070257 * np.sin(B)
        - 0.006758 * np.cos(2 * B)
        + 0.000907 * np.sin(2 * B)
        - 0.002697 * np.cos(3 * B)
        + 0.00148  * np.sin(3 * B)
    )


def hour_angle_rad(hour: float | np.ndarray) -> float | np.ndarray:
    """Hour angle ω (radians). solar noon = 0, morning < 0."""
    return np.radians((hour - 12.0) * 15.0)


def incidence_angle_deg(
    day_of_year: int | np.ndarray,
    hour: float | np.ndarray,
    latitude_deg: float,
    tilt_deg: float = 0.0,
    surface_azimuth_deg: float = 0.0,
) -> float | np.ndarray:
    """
    Incidence angle θ_i (degrees) of direct solar radiation on a tilted surface.

    Parameters
    ----------
    day_of_year         : 1-365
    hour                : solar time (0-24)
    latitude_deg        : site latitude (degrees, N positive)
    tilt_deg            : collector tilt from horizontal (0 = horizontal tracking)
    surface_azimuth_deg : surface azimuth (0 = south)

    Returns
    -------
    Incidence angle in degrees [0, 90].
    """
    delta = declination_rad(day_of_year)
    omega = hour_angle_rad(hour)
    phi   = np.radians(latitude_deg)
    sigma = np.radians(tilt_deg)
    gamma = np.radians(surface_azimuth_deg)

    cos_theta = (
        np.cos(delta) * np.cos(omega) * np.cos(sigma)
        - np.sin(phi) * np.sin(delta) * np.sin(sigma)
        + np.cos(phi) * np.sin(delta) * np.cos(sigma) * np.cos(gamma)
    )
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))


def optimal_tracking_angle_deg(
    day_of_year: int | np.ndarray,
    hour: float | np.ndarray,
    latitude_deg: float,
) -> float | np.ndarray:
    """
    Optimal E-W axis tracking angle (degrees from horizontal) that minimises
    the incidence angle on a parabolic-trough collector.
    """
    delta = declination_rad(day_of_year)
    omega = hour_angle_rad(hour)
    # For E-W horizontal axis: tan(θ_track) = cos(δ)·sin(ω) / sin(alt)
    # altitude = arcsin(cos(φ)cos(δ)cos(ω) + sin(φ)sin(δ))
    phi   = np.radians(latitude_deg)
    sin_alt = np.cos(phi) * np.cos(delta) * np.cos(omega) + np.sin(phi) * np.sin(delta)
    sin_alt = np.clip(sin_alt, 1e-6, 1.0)
    tan_track = np.cos(delta) * np.sin(omega) / sin_alt
    return np.degrees(np.arctan(tan_track))
