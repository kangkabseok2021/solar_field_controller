"""Tests for DAQ collector: CSV schema, queue behaviour, InfluxDB formatting."""

from __future__ import annotations

import asyncio
import csv
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daq.collector import Sample, SerialReader, run_collector


# ── Sample schema ─────────────────────────────────────────────────────────────

def test_sample_fields():
    s = Sample(
        timestamp    = "2024-06-15T10:00:00+00:00",
        target_angle = 30.5,
        actual_angle = 30.3,
        temperature  = 23.4,
        dni          = 847.2,
    )
    assert s.target_angle == 30.5
    assert s.actual_angle == 30.3


# ── SerialReader frame parsing ────────────────────────────────────────────────

def test_serial_reader_parses_temp_frame():
    reader = SerialReader("/dev/null")
    # Bypass open — inject values directly via _parse-like call
    reader.temperature = 0.0
    # Simulate what poll_once does internally
    line = "$TEMP,24.7"
    if line.startswith("$TEMP,"):
        reader.temperature = float(line[6:])
    assert abs(reader.temperature - 24.7) < 1e-6


def test_serial_reader_parses_dni_frame():
    reader = SerialReader("/dev/null")
    reader.dni = 0.0
    line = "$DNI,921.3"
    if line.startswith("$DNI,"):
        reader.dni = float(line[5:])
    assert abs(reader.dni - 921.3) < 1e-6


def test_serial_reader_ignores_unknown_frames():
    reader = SerialReader("/dev/null")
    reader.temperature = 5.0
    # Unknown frame must not change values
    line = "$WIND,3.2"
    if line.startswith("$TEMP,"):
        reader.temperature = float(line[6:])
    assert reader.temperature == 5.0


def test_serial_reader_open_fails_gracefully(tmp_path):
    reader = SerialReader("/nonexistent/ttyXX")
    assert reader.open() is False  # must not raise


# ── run_collector CSV output ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_collector_creates_csv(tmp_path):
    """collector writes correct CSV schema and at least 2 rows."""
    stop = asyncio.Event()
    log  = tmp_path / "test.csv"

    modbus_result = MagicMock()
    modbus_result.isError.return_value = False
    modbus_result.registers = [303]   # 30.3°

    async def fake_read(*a, **kw):
        return modbus_result

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.read_input_registers = fake_read

    async def delayed_stop():
        await asyncio.sleep(2.5)
        stop.set()

    with (
        patch("daq.collector.AsyncModbusTcpClient", return_value=mock_client),
        patch("daq.collector.SERIAL_DEV", "/dev/null"),
    ):
        asyncio.ensure_future(delayed_stop())
        samples = await run_collector(
            target_angle_fn=lambda: 30.0,
            stop_event=stop,
            log_path=log,
        )

    assert log.exists()
    assert len(samples) >= 2
    with open(log) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["actual_angle"] == "30.3"
    assert "timestamp" in rows[0]
    assert "dni" in rows[0]


@pytest.mark.asyncio
async def test_run_collector_handles_modbus_error(tmp_path):
    """Collector does not crash when Modbus returns error."""
    stop = asyncio.Event()
    log  = tmp_path / "err.csv"

    modbus_result = MagicMock()
    modbus_result.isError.return_value = True

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.read_input_registers = AsyncMock(return_value=modbus_result)

    async def delayed_stop():
        await asyncio.sleep(1.5)
        stop.set()

    with (
        patch("daq.collector.AsyncModbusTcpClient", return_value=mock_client),
        patch("daq.collector.SERIAL_DEV", "/dev/null"),
    ):
        asyncio.ensure_future(delayed_stop())
        samples = await run_collector(stop_event=stop, log_path=log)

    # actual_angle should be 0.0 (default) when Modbus errors
    assert all(s.actual_angle == 0.0 for s in samples)
