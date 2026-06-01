"""Drive controller simulation — pure Python, no pymodbus dependency."""

from __future__ import annotations

import random

SCALE = 10  # register value × SCALE = angle in degrees × 10


def to_reg(angle: float) -> int:
    """Encode angle (degrees) as a 16-bit two's-complement Modbus register."""
    return int(round(angle * SCALE)) & 0xFFFF


def from_reg(reg: int) -> float:
    """Decode a 16-bit two's-complement Modbus register to angle (degrees)."""
    signed = reg if reg < 32768 else reg - 65536
    return signed / SCALE


class DriveSimulator:
    """First-order lag encoder with configurable noise — models a real drive."""

    def __init__(self, lag: float = 0.15, noise_sigma: float = 0.05) -> None:
        self.encoder   = 0.0
        self._lag      = lag
        self._noise    = noise_sigma

    def step(self, setpoint: float, dt: float = 0.05) -> float:
        alpha         = dt / (self._lag + dt)
        self.encoder += alpha * (setpoint - self.encoder)
        self.encoder += random.gauss(0, self._noise)
        return self.encoder
