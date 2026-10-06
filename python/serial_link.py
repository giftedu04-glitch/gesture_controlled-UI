"""Bluetooth serial link between the desktop app and the Arduino.

The Arduino sends a single byte whenever the hall-sensor combination changes:

    1 -> key1 = True,  key2 = True
    2 -> key1 = False, key2 = True
    3 -> key1 = True,  key2 = False
    4 -> key1 = False, key2 = False

The app replies with b'y' / b'n' to switch the Arduino LED on / off.
"""

import time

import serial
from serial.tools import list_ports

STATE_MAP = {
    1: (True, True),
    2: (False, True),
    3: (True, False),
    4: (False, False),
}


class BluetoothLink:
    def __init__(self, port=None, baudrate=9600, timeout=0.05):
        self.port_name = port or self.auto_port()
        self._serial = None
        self.key1 = False
        self.key2 = False
        self._led_sent = None

        if not self.port_name:
            print("[serial] no serial port selected - running without hardware")
            return

        try:
            self._serial = serial.Serial(self.port_name, baudrate, timeout=timeout)
            time.sleep(2)  # give an Arduino time to reset after the port opens
            print(f"[serial] connected to {self.port_name} @ {baudrate} baud")
        except (serial.SerialException, OSError) as exc:
            print(f"[serial] could not open {self.port_name}: {exc}")
            print("[serial] running without hardware")
            self._serial = None

    @staticmethod
    def ports():
        return [p.device for p in list_ports.comports()]

    @classmethod
    def auto_port(cls):
        ports = cls.ports()
        if not ports:
            return None
        print(f"[serial] available ports: {', '.join(ports)}")
        return ports[0]

    @property
    def connected(self):
        return self._serial is not None

    def poll(self):
        """Read every pending byte and keep the most recent key state."""
        if self._serial is None:
            return
        try:
            waiting = self._serial.in_waiting
            if not waiting:
                return
            for value in self._serial.read(waiting):
                state = STATE_MAP.get(value)
                if state:
                    self.key1, self.key2 = state
        except (serial.SerialException, OSError, ValueError) as exc:
            print(f"[serial] connection lost: {exc}")
            self._serial = None

    def send_led(self, on):
        """Send 'y' / 'n' for the LED. Only transmits on a state change."""
        if self._serial is None or on == self._led_sent:
            return
        try:
            self._serial.write(b"y" if on else b"n")
            self._led_sent = on
        except (serial.SerialException, OSError) as exc:
            print(f"[serial] could not write: {exc}")
            self._serial = None

    def close(self):
        if self._serial is not None:
            self._serial.close()
            self._serial = None
