"""Async 1 Hz DAQ: polls Modbus encoder + serial sensors → timestamped CSV."""

from __future__ import annotations

import asyncio
import csv
import os
import time
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from pymodbus.client import AsyncModbusTcpClient
import serial


MODBUS_HOST  = os.getenv("MODBUS_HOST",  "127.0.0.1")
MODBUS_PORT  = int(os.getenv("MODBUS_PORT", "5020"))
SERIAL_DEV   = os.getenv("SERIAL_DEV",  "/dev/ttyRS485")
LOG_DIR      = Path(os.getenv("LOG_DIR", "logs"))
SCALE        = 10  # register value ÷ 10 = degrees


@dataclass
class Sample:
    timestamp:    str
    target_angle: float
    actual_angle: float
    temperature:  float
    dni:          float


class SerialReader:
    """Blocking serial reader run in a thread executor."""

    def __init__(self, device: str, baud: int = 9600) -> None:
        self._device = device
        self._baud   = baud
        self._port: serial.Serial | None = None
        self.temperature = 0.0
        self.dni         = 0.0

    def open(self) -> bool:
        try:
            self._port = serial.Serial(self._device, self._baud, timeout=0.1)
            return True
        except serial.SerialException:
            return False

    def poll_once(self) -> None:
        if not self._port:
            return
        while self._port.in_waiting:
            try:
                line = self._port.readline().decode(errors="ignore").strip()
            except serial.SerialException:
                break
            if line.startswith("$TEMP,"):
                try:
                    self.temperature = float(line[6:])
                except ValueError:
                    pass
            elif line.startswith("$DNI,"):
                try:
                    self.dni = float(line[5:])
                except ValueError:
                    pass


async def run_collector(
    target_angle_fn=None,   # callable → float (from shm reader); None → 0.0
    stop_event: asyncio.Event | None = None,
    log_path: Path | None = None,
) -> list[Sample]:
    LOG_DIR.mkdir(exist_ok=True)
    if log_path is None:
        date_str  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path  = LOG_DIR / f"field_{date_str}.csv"

    serial_reader = SerialReader(SERIAL_DEV)
    loop          = asyncio.get_running_loop()
    await loop.run_in_executor(None, serial_reader.open)

    samples: list[Sample] = []
    fieldnames = [f.name for f in fields(Sample)]

    with open(log_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        async with AsyncModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT) as client:
            while stop_event is None or not stop_event.is_set():
                t0 = time.monotonic()

                # Read encoder from Modbus (input register 30001, 0-based index 0)
                actual_angle = 0.0
                try:
                    result = await client.read_input_registers(0, count=1)
                    if not result.isError():
                        raw = result.registers[0]
                        actual_angle = (
                            (raw if raw < 32768 else raw - 65536) / SCALE
                        )
                except Exception:
                    pass

                # Read serial sensors in executor
                await loop.run_in_executor(None, serial_reader.poll_once)

                target = target_angle_fn() if target_angle_fn else 0.0
                s = Sample(
                    timestamp    = datetime.now(timezone.utc).isoformat(),
                    target_angle = round(target, 2),
                    actual_angle = round(actual_angle, 2),
                    temperature  = round(serial_reader.temperature, 1),
                    dni          = round(serial_reader.dni, 1),
                )
                writer.writerow(s.__dict__)
                fh.flush()
                samples.append(s)

                elapsed = time.monotonic() - t0
                await asyncio.sleep(max(0.0, 1.0 - elapsed))

    return samples
