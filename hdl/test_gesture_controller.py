"""cocotb testbench for hdl/gesture_controller.v.

Run with:  python hdl/test_gesture_controller.py [simulator]
(default simulator is icarus)
"""

from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

CLK_PERIOD_NS = 10


def bit(signal) -> int:
    return int(signal.value)


async def wait_cycles(dut, n: int = 1) -> None:
    """Wait n rising edges, then settle 2 ns past the edge."""
    await ClockCycles(dut.clk, n)
    await Timer(2, unit="ns")


async def drive_halls(dut, hall_1: int, hall_2: int) -> None:
    """Change the hall sensor inputs 2 ns after an edge (safe sampling)."""
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    dut.hall_1.value = hall_1
    dut.hall_2.value = hall_2


async def pulse_rx(dut, byte: int, cycles: int = 1) -> None:
    """Present rx_data/rx_valid for exactly `cycles` rising edges."""
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    dut.rx_data.value = byte
    dut.rx_valid.value = 1
    await ClockCycles(dut.clk, cycles)
    await Timer(2, unit="ns")
    dut.rx_valid.value = 0


class TxMonitor:
    """Records every byte emitted while tx_valid is high."""

    def __init__(self, dut):
        self.bytes: list[int] = []
        self.task = cocotb.start_soon(self._run(dut))

    def clear(self) -> None:
        self.bytes.clear()

    async def _run(self, dut) -> None:
        while True:
            await RisingEdge(dut.clk)
            await Timer(2, unit="ns")
            if bit(dut.tx_valid):
                self.bytes.append(bit(dut.tx_data))


async def start_tb(dut) -> TxMonitor:
    """Start a clock and TX monitor, then reset the DUT.

    cocotb tears down background tasks when a test ends, so every test
    starts its own clock/monitor.
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    monitor = TxMonitor(dut)

    dut.rst.value = 1
    dut.hall_1.value = 0
    dut.hall_2.value = 0
    dut.rx_valid.value = 0
    dut.rx_data.value = 0
    await wait_cycles(dut, 2)
    dut.rst.value = 0
    monitor.clear()
    await wait_cycles(dut, 1)
    return monitor


async def expect_tx(dut, monitor: TxMonitor, timeout: int = 10) -> list[int]:
    """Wait for new transmitted bytes and return them."""
    already = len(monitor.bytes)
    for _ in range(timeout):
        if len(monitor.bytes) > already:
            break
        await wait_cycles(dut, 1)
    await wait_cycles(dut, 2)  # drain: catch a strobe that repeats too often
    return monitor.bytes[already:]


async def expect_no_tx(dut, monitor: TxMonitor, cycles: int) -> None:
    seen = len(monitor.bytes)
    await wait_cycles(dut, cycles)
    assert len(monitor.bytes) == seen, (
        f"unexpected transmission(s) {monitor.bytes[seen:]} while state held"
    )


@cocotb.test()
async def test_reset_idle(dut):
    """After reset the LED is off and nothing is transmitted while both
    hall sensors sit at their (LOW,LOW) power-on state."""
    monitor = await start_tb(dut)
    assert bit(dut.led) == 0
    await expect_no_tx(dut, monitor, cycles=10)


@cocotb.test()
async def test_hall_state_bytes(dut):
    """Each hall sensor combination transmits the documented byte:
    (LOW,LOW)=1 (HIGH,LOW)=2 (LOW,HIGH)=3 (HIGH,HIGH)=4."""
    monitor = await start_tb(dut)

    # (LOW,LOW) -> (HIGH,LOW): byte 2
    await drive_halls(dut, 1, 0)
    assert await expect_tx(dut, monitor) == [2]

    # (HIGH,LOW) -> (HIGH,HIGH): byte 4
    await drive_halls(dut, 1, 1)
    assert await expect_tx(dut, monitor) == [4]

    # (HIGH,HIGH) -> (LOW,HIGH): byte 3
    await drive_halls(dut, 0, 1)
    assert await expect_tx(dut, monitor) == [3]

    # (LOW,HIGH) -> (LOW,LOW): byte 1
    await drive_halls(dut, 0, 0)
    assert await expect_tx(dut, monitor) == [1]


@cocotb.test()
async def test_simultaneous_change_emits_once(dut):
    """Both sensors changing together still sends exactly one byte."""
    monitor = await start_tb(dut)
    await drive_halls(dut, 1, 1)
    assert await expect_tx(dut, monitor) == [4]


@cocotb.test()
async def test_no_repeat_while_held(dut):
    """While the combination is unchanged nothing is re-sent; a later
    change sends exactly one strobe."""
    monitor = await start_tb(dut)
    await drive_halls(dut, 0, 1)
    assert await expect_tx(dut, monitor) == [3]
    await expect_no_tx(dut, monitor, cycles=20)
    await drive_halls(dut, 0, 0)
    assert await expect_tx(dut, monitor) == [1]
    await expect_no_tx(dut, monitor, cycles=20)


@cocotb.test()
async def test_led_toggle(dut):
    """'y' turns the LED on, 'n' turns it off."""
    await start_tb(dut)

    await pulse_rx(dut, ord("y"))
    await wait_cycles(dut, 2)
    assert bit(dut.led) == 1, "LED should be on after 'y'"

    await pulse_rx(dut, ord("n"))
    await wait_cycles(dut, 2)
    assert bit(dut.led) == 0, "LED should be off after 'n'"

    await pulse_rx(dut, ord("y"))
    await wait_cycles(dut, 2)
    assert bit(dut.led) == 1, "LED should be on again after a second 'y'"


@cocotb.test()
async def test_unknown_rx_byte_ignored(dut):
    """Bytes other than 'y'/'n' leave the LED unchanged."""
    await start_tb(dut)

    await pulse_rx(dut, ord("y"))
    await wait_cycles(dut, 2)
    await pulse_rx(dut, ord("x"))
    await wait_cycles(dut, 2)
    assert bit(dut.led) == 1, "'x' must not disturb an LED that is on"

    await pulse_rx(dut, ord("n"))
    await wait_cycles(dut, 2)
    await pulse_rx(dut, 0x00)
    await wait_cycles(dut, 2)
    assert bit(dut.led) == 0, "0x00 must not disturb an LED that is off"


@cocotb.test()
async def test_interleaved_tx_rx(dut):
    """A gesture change and a Bluetooth command in the same window are
    handled independently: the byte is still sent and the LED still set."""
    monitor = await start_tb(dut)

    # Change hall state and deliver 'y' around the same time. The byte may
    # be recorded before we get back, so remember the monitor position first.
    mark = len(monitor.bytes)
    await drive_halls(dut, 1, 0)
    await pulse_rx(dut, ord("y"))
    await wait_cycles(dut, 3)
    tx = monitor.bytes[mark:]

    assert tx == [2], f"expected byte 2, got {tx}"
    assert bit(dut.led) == 1, "LED should be on after interleaved 'y'"


if __name__ == "__main__":
    from cocotb_tools.check_results import get_results
    from cocotb_tools.runner import get_runner

    here = Path(__file__).resolve().parent
    sim = sys.argv[1] if len(sys.argv) > 1 else "icarus"

    runner = get_runner(sim)
    runner.build(
        sources=[here / "gesture_controller.v"],
        hdl_toplevel="gesture_controller",
        build_dir=here / "sim_build",
        timescale=("1ns", "1ps"),
    )
    results = runner.test(
        hdl_toplevel="gesture_controller",
        test_module="test_gesture_controller",
        build_dir=here / "sim_build",
        test_dir=here,
    )
    num_tests, num_failed = get_results(results)
    print(f"HDL: {num_tests - num_failed}/{num_tests} tests passed")
    sys.exit(1 if (num_failed or num_tests == 0) else 0)
