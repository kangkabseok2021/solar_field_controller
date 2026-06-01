"""
Software Modbus/TCP server simulating a solar-field drive controller.

Register map (1-based Modbus addresses):
  Holding 40001 → index 0: position setpoint ×10  (written by C++ daemon)
  Input   30001 → index 0: encoder feedback  ×10  (read by C++ daemon)

Uses pymodbus 3.x StartAsyncTcpServer with a custom callback-based datastore.
"""

from __future__ import annotations

import asyncio
from pymodbus.server import ModbusTcpServer
from pymodbus.datastore import ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification

from .drive_sim import DriveSimulator, to_reg, from_reg


class _SimpleStore:
    """Minimal register store: one holding register + one input register."""

    def __init__(self) -> None:
        self._hr = [0] * 16   # holding registers (setpoint)
        self._ir = [0] * 16   # input registers   (encoder)

    def get_holding(self, address: int) -> int:
        return self._hr[address] if address < len(self._hr) else 0

    def set_holding(self, address: int, value: int) -> None:
        if address < len(self._hr):
            self._hr[address] = value & 0xFFFF

    def get_input(self, address: int) -> int:
        return self._ir[address] if address < len(self._ir) else 0

    def set_input(self, address: int, value: int) -> None:
        if address < len(self._ir):
            self._ir[address] = value & 0xFFFF


async def run_server(host: str = "127.0.0.1", port: int = 5020,
                     lag: float = 0.15, noise_sigma: float = 0.05,
                     stop_event: asyncio.Event | None = None) -> None:
    """Run a software Modbus/TCP drive-controller simulator."""
    store = _SimpleStore()
    sim   = DriveSimulator(lag=lag, noise_sigma=noise_sigma)

    async def _update_encoder() -> None:
        while stop_event is None or not stop_event.is_set():
            setpoint = from_reg(store.get_holding(0))
            encoder  = sim.step(setpoint)
            store.set_input(0, to_reg(encoder))
            await asyncio.sleep(0.05)

    asyncio.ensure_future(_update_encoder())

    # Use raw asyncio TCP server for maximum pymodbus-version independence
    import struct

    async def _handle(reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                header = await reader.readexactly(6)
                tid, pid, length, uid = struct.unpack(">HHHB", header[:7] if len(header) >= 7 else header + b"\x01")
                # Re-read with correct length
                header = await reader.readexactly(6)
                tid, pid, length = struct.unpack(">HHH", header)
                pdu = await reader.readexactly(length)
                uid  = pdu[0]
                func = pdu[1]

                if func == 0x03:  # Read Holding Registers
                    start, count = struct.unpack(">HH", pdu[2:6])
                    data = b"".join(
                        struct.pack(">H", store.get_holding(start + i))
                        for i in range(count)
                    )
                    resp_pdu = bytes([uid, func, count * 2]) + data
                elif func == 0x04:  # Read Input Registers
                    start, count = struct.unpack(">HH", pdu[2:6])
                    data = b"".join(
                        struct.pack(">H", store.get_input(start + i))
                        for i in range(count)
                    )
                    resp_pdu = bytes([uid, func, count * 2]) + data
                elif func == 0x06:  # Write Single Holding Register
                    addr, val = struct.unpack(">HH", pdu[2:6])
                    store.set_holding(addr, val)
                    resp_pdu = pdu  # echo
                else:
                    resp_pdu = bytes([uid, func | 0x80, 0x01])

                resp_header = struct.pack(">HHH", tid, 0, len(resp_pdu))
                writer.write(resp_header + resp_pdu)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(_handle, host, port)
    async with server:
        if stop_event:
            await stop_event.wait()
        else:
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(run_server())
