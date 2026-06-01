"""
Virtual serial pair simulator for pyrometer / PT100 sensors.

Starts socat to create two linked PTYs, then writes realistic
$TEMP,xx.x and $DNI,xxx.x frames to one end.

Usage (standalone):
    python serial_sim.py              # writes to /tmp/ttyS1, read from /tmp/ttyS0
    socat PTY,link=/tmp/ttyS0,rawer PTY,link=/tmp/ttyS1,rawer &
    # then connect SerialSensorReader to /tmp/ttyS0
"""

from __future__ import annotations

import asyncio
import math
import os
import subprocess
import time
from pathlib import Path


MASTER_PTY = "/tmp/solar_master"
SLAVE_PTY  = "/tmp/solar_slave"


def start_socat() -> subprocess.Popen:
    return subprocess.Popen(
        [
            "socat",
            f"PTY,link={MASTER_PTY},rawer",
            f"PTY,link={SLAVE_PTY},rawer",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def write_frames(stop_event: asyncio.Event | None = None,
                       interval_s: float = 1.0,
                       base_temp: float = 22.0,
                       base_dni: float = 750.0) -> None:
    """Write sensor frames to MASTER_PTY at `interval_s` Hz."""
    # Wait for socat to create the PTYs
    for _ in range(20):
        if Path(MASTER_PTY).exists():
            break
        await asyncio.sleep(0.1)

    fd = os.open(MASTER_PTY, os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
    t0 = time.monotonic()

    try:
        while stop_event is None or not stop_event.is_set():
            elapsed = time.monotonic() - t0
            # Slowly rising temperature, sinusoidal DNI
            temp = base_temp + elapsed * 0.02
            dni  = max(0.0, base_dni * math.sin(math.pi * elapsed / 60.0))
            frame = f"$TEMP,{temp:.1f}\r\n$DNI,{dni:.1f}\r\n"
            try:
                os.write(fd, frame.encode())
            except OSError:
                pass
            await asyncio.sleep(interval_s)
    finally:
        os.close(fd)
