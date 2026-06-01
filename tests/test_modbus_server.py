"""Tests for the software Modbus drive-controller simulator."""

from __future__ import annotations

import asyncio
import pytest

from test_bench.drive_sim import DriveSimulator, from_reg as _from_reg, to_reg as _to_reg, SCALE


# ── register encoding ─────────────────────────────────────────────────────────

def test_to_reg_positive():
    assert _to_reg(30.0) == 300


def test_to_reg_negative_twos_complement():
    reg = _to_reg(-45.0)
    assert _from_reg(reg) == pytest.approx(-45.0, abs=0.01)


def test_to_from_reg_roundtrip():
    for angle in (-90.0, -45.0, 0.0, 45.0, 90.0):
        assert _from_reg(_to_reg(angle)) == pytest.approx(angle, abs=0.01)


# ── DriveSimulator ────────────────────────────────────────────────────────────

def test_drive_sim_converges_to_setpoint():
    sim = DriveSimulator(lag=0.1, noise_sigma=0.0)
    for _ in range(50):
        sim.step(45.0, dt=0.05)
    assert abs(sim.encoder - 45.0) < 0.5


def test_drive_sim_stays_near_zero_setpoint():
    sim = DriveSimulator(lag=0.1, noise_sigma=0.0)
    for _ in range(30):
        sim.step(0.0, dt=0.05)
    assert abs(sim.encoder) < 0.1


def test_drive_sim_noise_stays_bounded():
    sim = DriveSimulator(lag=0.5, noise_sigma=0.5)
    for _ in range(200):
        sim.step(0.0, dt=0.05)
    # Encoder should not drift unboundedly even with noise
    assert abs(sim.encoder) < 10.0
