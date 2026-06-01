# Parabolic-Trough Solar Field Controller

A complete software stack for a parabolic-trough solar thermal tracking system: a **C++17 real-time tracking daemon** with PI controller and safety FSM communicates axis drive positions over **Modbus/TCP** (libmodbus) and reads pyrometer temperatures via **serial RS-485** (pyserial). A Python sun-position engine feeds target angles via POSIX shared memory. A Python DAQ tool polls both interfaces, logs to CSV, and plots tracking accuracy and DNI efficiency curves. A legacy **VBA incidence-angle calculator** is ported to vectorised NumPy and regression-tested against 100 reference values. The test bench runs entirely in software, enabling full CI without hardware.

---

## Architecture

```
Sun Position Engine (Python)
  lat/lon/datetime → target_angle → /solar_target (POSIX shm)
           │
C++17 Tracking Daemon  (timerfd 100 ms, SCHED_FIFO)
  FieldController FSM:  INIT → TRACKING → WIND_STOW → FAULT
  PI controller:  Kp=0.8  Ki=0.05  deadband ±0.1°  anti-windup
           │ Modbus/TCP (libmodbus)          │ Serial RS-485 (pyserial)
  Drive register map:                  Pyrometer / PT100 ASCII frames:
    40001: setpoint ×10 (write)          "$TEMP,23.4\r\n"
    30001: encoder  ×10 (read)           "$DNI,847.2\r\n"
           │                                       │
Python DAQ Tool (pymodbus + pyserial, 1 Hz asyncio)
  → timestamped CSV  →  matplotlib tracking accuracy + efficiency plots

Test Bench (no hardware needed):
  DriveSimulator (first-order lag + Gaussian noise) — pure Python
  test_bench/serial_sim.py  — socat virtual serial pair + frame writer
```

---

## C++20 Features Used

| Feature | Where |
|---|---|
| `inline constexpr` | `src/PIController.h` — Kp, Ki, deadband, limits |
| `std::lock_guard<std::mutex>` | `src/FieldController.h` — thread-safe state reads |
| Scoped enums `FieldState` | `src/FieldController.h` — INIT/TRACKING/WIND_STOW/FAULT |
| `[[nodiscard]]` | `PIController::update()` |

---

## Control Design

### PI Tracking Controller

```
output = Kp × e + Ki × ∫e dt
  Kp = 0.8  (proportional gain)
  Ki = 0.05 (integral gain, 100 ms sample time)
  Deadband ±0.1° — suppresses chatter at setpoint
  Anti-windup: integral clamped to ±50 when output saturates
```

### Safety FSM

| State | Entry condition | Exit condition |
|---|---|---|
| `INIT` | startup | encoder within ±0.5° for 3 consecutive ticks |
| `TRACKING` | homing complete | wind > 12 m/s → WIND_STOW; comm loss → FAULT |
| `WIND_STOW` | wind > 12 m/s | wind < 9.6 m/s (20% hysteresis) |
| `FAULT` | encoder timeout (500 ms) | external reset required |

---

## VBA → Python Migration

`geometry/incidence_angle.py` ports the legacy `IncidenceAngle.bas` macro.

**Incidence angle formula (Duffie & Beckman):**

```
cos θ_i = cos(δ)·cos(ω)·cos(Σ) − sin(φ)·sin(δ)·sin(Σ) + cos(φ)·sin(δ)·cos(Σ)·cos(γ_s)

δ = solar declination (Spencer formula)
ω = hour angle (15° per solar hour from noon)
Σ = collector tilt
φ = site latitude
γ_s = surface azimuth
```

`geometry/vba_reference.csv` — 100 pre-computed reference values; `tests/test_geometry.py` validates Python output matches within 0.001°.

---

## Quick Start

```bash
# C++ build + 10 GoogleTests
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
ctest --test-dir build --output-on-failure -V

# Python 24 pytest (geometry + DAQ + simulator)
uv sync && uv run pytest tests/ -v

# Run DAQ analysis on a sample CSV
uv run python -m daq.analysis logs/field_sample.csv --headless
```

---

## Testing

### C++ — 10 GoogleTests

| Suite | n | What it validates |
|---|---|---|
| `PIController` | 4 | Step response convergence, anti-windup, deadband, reset |
| `FSM` | 6 | All state transitions: INIT→TRACKING, wind stow, fault on encoder timeout, hysteresis exit |

### Python — 24 pytest

| Module | n | What it validates |
|---|---|---|
| `test_geometry` | 11 | 100-pt VBA regression, numpy vectorisation, edge cases, tracking angle |
| `test_collector` | 7 | CSV schema, serial frame parsing, Modbus error handling, async collector |
| `test_modbus_server` | 6 | Register encoding, DriveSimulator convergence + noise bounds |
