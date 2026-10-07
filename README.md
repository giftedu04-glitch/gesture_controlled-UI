# Gesture Controlled UI

[![CI](https://github.com/giftedu04-glitch/gesture_controlled-UI/actions/workflows/ci.yml/badge.svg)](https://github.com/giftedu04-glitch/gesture_controlled-UI/actions/workflows/ci.yml)

A colour-tracking gesture interface that controls a desktop app with your hand
(via webcam) and an Arduino (via hall sensors + Bluetooth).

Originally written as **Arduino (C++) + Processing**, this version ports the
Processing desktop app to **Python** (OpenCV + PySerial). The Arduino sketch is
unchanged in behaviour and lives in `arduino/`.

## How it works

- The **Arduino** reads two hall sensors and sends a byte (1-4) over Bluetooth
  whenever the sensor combination changes. It also switches its on-board LED
  on/off when the desktop app sends `y` / `n`.
- The **Python app** captures the webcam, tracks a colour you pick during
  calibration, and uses the tracked position as a virtual pointer:
  - hover an icon while **key 1** is active to drag it
  - release **key 1** to open the Paint or LED screen
  - **key 2** returns to the main screen
  - on the LED screen, hovering ON/OFF while key 1 is active sends `y` / `n`
    back to the Arduino

## Project structure

```
.
├── arduino/
│   └── gesture_controller/
│       └── gesture_controller.ino   # firmware (unchanged behaviour)
├── hdl/
│   ├── gesture_controller.v         # Verilog model of the firmware
│   ├── test_gesture_controller.py   # cocotb testbench
│   └── Makefile                     # `make test` wrapper
├── python/
│   ├── main.py                      # entry point / CLI flags
│   ├── app.py                       # screens + main loop (ported from Processing)
│   ├── tracker.py                   # webcam colour tracking (captureEvent + pixel loop)
│   ├── serial_link.py               # Bluetooth link (Serial object)
│   ├── assets.py                    # image loading with generated placeholders
│   └── assets/                      # drop Done.png, Aisha.png, ... here
├── requirements.txt
└── README.md
```

## Hardware

| Component        | Connection                      |
|------------------|---------------------------------|
| Hall sensor 1    | Arduino pin 9                   |
| Hall sensor 2    | Arduino pin 10                  |
| Bluetooth (HC-05)| TX → pin 11, RX → pin 12 (software serial @ 9600 baud) |
| LED              | Arduino pin 13 (on-board)       |

Upload `arduino/gesture_controller/gesture_controller.ino` with the Arduino IDE
as usual.

The full bill of materials for assembling the circuit (Arduino Nano, 2x A3144
hall sensors, a small magnet on the thumb, HC-05/HC-06 Bluetooth module, 9V
battery, dot board, gloves, ...) is listed in the
[Circuit Digest VR project](https://circuitdigest.com/microcontroller-projects/virtual-reality-using-arduino)
this repository is based on.

## Software setup

Requires Python 3.9+ and a webcam.

```bash
git clone https://github.com/giftedu04-glitch/gesture_controlled-UI.git
cd gesture_controlled-UI
pip install -r requirements.txt
```

Run the app:

```bash
cd python
python main.py                    # camera 0, first serial port found
python main.py --list-serial      # show available Bluetooth/COM ports
python main.py --port COM5        # pick the Bluetooth module explicitly
python main.py --camera 1         # pick a different webcam
python main.py --threshold 70     # looser colour matching
```

The app works without the Arduino attached (it just reports that it is running
without hardware).

### Images

The original sketch loaded `Done.png`, `Aisha.png`, `Paint.png`,
`LED_Toggle.png`, `LED_on.png` and `LED_off.png`. Place your own copies in
`python/assets/` and they will be used automatically; if a file is missing a
labelled placeholder is generated so the app still runs. (Generated PNGs are
git-ignored.)

## Using the app

1. **Calibration** - click the object whose colour you want to track, then
   click **DONE** (bottom-right). The pointer circle follows that colour and is
   mirrored horizontally, like a mirror.
2. **Main screen** - move the tracked colour over the PAINT or LED icon while
   key 1 is active (hall sensor state) to drag it; release key 1 to open the
   screen.
3. **Paint screen** - keep key 1 active and move over the canvas to paint
   white strokes. Press key 2 to go back.
4. **LED screen** - hover the ON or OFF button while key 1 is active to switch
   the Arduino LED. Press key 2 to go back.

Press `Esc` or `q` to quit.

## Tests

The tests are fully headless - the camera, GUI and serial port are all faked:

```bash
pip install pytest
python -m pytest python/tests -q
```

GitHub Actions (`.github/workflows/ci.yml`) runs them on every push and pull
request with Python 3.10 and 3.13.

### HDL tests (cocotb + Verilog)

`hdl/` contains a cycle-accurate Verilog model of the Arduino firmware
(`hdl/gesture_controller.v`) and a cocotb testbench that proves the behaviour
documented below: the hall-sensor combination → Bluetooth byte mapping (bytes
1-4, sent only when the combination changes) and the `y` / `n` LED control.

Requirements: [Icarus Verilog](https://steveicarus.github.io/iverilog/) on your
PATH and cocotb (`pip install cocotb`), then:

```bash
python hdl/test_gesture_controller.py            # fast, no wave dump
python hdl/test_gesture_controller.py --waves    # also writes hdl/sim_build/waves.vcd
```

(or `make -C hdl`)

GitHub Actions (`.github/workflows/hdl.yml`) runs the same suite on every push
and pull request (Icarus via `apt`, cocotb via `pip`), then generates the
visual report below from the VCD + JUnit XML and uploads it as the
**`visual-test-results` artifact** of the run (HTML report, `waves.vcd`,
`results.xml`, `pytest_junit.xml`; kept for 90 days). Download it from the run
summary page of the *HDL* workflow.

A rendered snapshot of the results - circuit diagram, gesture-to-byte mapping,
the interactive simulated waveform (0-1404 ns, Icarus VCD dump) and per-test
detail for both suites - is checked in at
[docs/test_results.html](docs/test_results.html).

## Key state mapping (Arduino → app)

| Byte | Hall sensor 1 | Hall sensor 2 | key 1 | key 2 |
|------|---------------|---------------|-------|-------|
| 1    | LOW           | LOW           | true  | true  |
| 2    | HIGH          | LOW           | false | true  |
| 3    | LOW           | HIGH          | true  | false |
| 4    | HIGH          | HIGH          | false | false |

## Differences from the Processing version

- Python 3 + OpenCV replace Processing; PySerial replaces the Processing Serial
  library.
- Serial port and camera index are chosen with `--port` / `--camera` instead of
  hard-coded list indexes.
- The DONE button must be clicked (the original finished calibration on hover,
  which also overwrote the sampled colour).
- Missing image assets are generated as placeholders instead of failing.
- Lost colour tracking keeps the last pointer position instead of jumping to
  the top-left corner.
