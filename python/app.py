"""Desktop UI - port of the original Processing sketch.

Screens
    1. Calibration - click an object to select its colour, then click DONE.
    2. Main screen - drag the PAINT / LED icons with the tracked colour while
       key 1 is active; release key 1 to open the screen.
    3. Paint screen - move the tracked colour over the canvas while key 1 is
       active to paint; key 2 returns to the main screen.
    4. LED screen - hover the ON / OFF button while key 1 is active to send
       'y' / 'n' to the Arduino; key 2 returns to the main screen.
"""

import cv2
import numpy as np

from assets import load
from serial_link import BluetoothLink
from tracker import ColorTracker

WINDOW_W, WINDOW_H = 800, 600
WINDOW_NAME = "Gesture Controlled UI"

# Geometry taken from the Processing sketch (width/height expressions resolved)
DONE_RECT = (666, 545, 134, 55)        # x, y, w, h - calibration DONE button
PAINT_HOME = (80, 71)                  # width/10, height/8.5
LED_HOME = (727, 71)                   # width/1.1, height/8.5
ICON_W, ICON_H = 200, 150              # width/4, height/4
PAINT_HIT = (180, 146)                 # avgX < 180 && avgY < 146
LED_HIT_MIN_X = 627                    # avgX > width/1.1 - width/8
LED_HIT_MAX_Y = 146
PAINT_BG = (533, 600)                  # width/1.5, height
PAINT_CANVAS = (210, 85, 380, 290)     # x, y, w, h of the drawing surface
LED_ON_RECT = (100, 140, 200, 120)     # x, y, w, h
LED_OFF_RECT = (500, 140, 200, 120)

TRACK_COLOR = (0xDB, 0xFA, 0x21)       # #21FADB in BGR
PAINT_BG_COLOR = (0x0B, 0x19, 0x6A)    # #0B196A in BGR
KEY_TEXT_COLOR = (0xE0, 0x96, 0x1B)    # #1B96E0 in BGR


def _inside(point, rect):
    x, y = point
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def _paste(window, image, x, y, w, h):
    """Paste image scaled to (w, h) with its top-left corner at (x, y)."""
    if image.shape[1] != w or image.shape[0] != h:
        image = cv2.resize(image, (w, h))
    win_h, win_w = window.shape[:2]
    dx0, dy0 = max(x, 0), max(y, 0)
    dx1, dy1 = min(x + w, win_w), min(y + h, win_h)
    if dx0 >= dx1 or dy0 >= dy1:
        return
    sx0, sy0 = dx0 - x, dy0 - y
    window[dy0:dy1, dx0:dx1] = image[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]


def _paste_center(window, image, cx, cy, w, h):
    _paste(window, image, int(cx - w / 2), int(cy - h / 2), w, h)


def _text_center(window, text, cx, cy, scale, color, thickness=2):
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    org = (int(cx - size[0] / 2), int(cy + size[1] / 2))
    cv2.putText(
        window, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
        thickness, cv2.LINE_AA,
    )


class App:
    def __init__(self, camera=0, port=None, threshold=50):
        self.link = BluetoothLink(port)
        self.tracker = ColorTracker(camera, threshold, WINDOW_W, WINDOW_H)

        self.images = {
            "Done": load("Done", DONE_RECT[2:]),
            "Aisha": load("Aisha", (WINDOW_W, WINDOW_H)),
            "Paint": load("Paint", (ICON_W, ICON_H)),
            "LED_Toggle": load("LED_Toggle", (ICON_W, ICON_H)),
            "LED_on": load("LED_on", (LED_ON_RECT[2], LED_ON_RECT[3])),
            "LED_off": load("LED_off", (LED_OFF_RECT[2], LED_OFF_RECT[3])),
        }
        self.canvas = np.zeros((PAINT_CANVAS[3], PAINT_CANVAS[2], 3), np.uint8)

        self.calibrated = False
        self.paint_screen = False
        self.led_screen = False
        self.move_paint = False
        self.move_led = False
        self.mouse = (0, 0)
        self.warn = ""
        self.avg = None

    # ------------------------------------------------------------------ setup
    def run(self):
        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)
        try:
            while True:
                self.link.poll()
                key1, key2 = self.link.key1, self.link.key2

                self.tracker.read()
                self.avg = self.tracker.update()

                if key2:
                    self.paint_screen = False
                    self.led_screen = False
                    self.move_paint = False
                    self.move_led = False

                window = np.zeros((WINDOW_H, WINDOW_W, 3), np.uint8)
                if not self.calibrated:
                    self._draw_calibration(window)
                elif self.paint_screen:
                    self._draw_paint(window, key1)
                elif self.led_screen:
                    self._draw_led(window, key1)
                else:
                    self._draw_ui(window, key1)

                if self.calibrated and self.avg:
                    cv2.circle(
                        window,
                        (int(self.avg[0]), int(self.avg[1])),
                        8, TRACK_COLOR, -1,
                    )

                cv2.imshow(WINDOW_NAME, window)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
        finally:
            self.link.close()
            self.tracker.release()
            cv2.destroyAllWindows()

    # ----------------------------------------------------------------- mouse
    def _on_mouse(self, event, x, y, flags, _param):
        self.mouse = (x, y)
        if event != cv2.EVENT_LBUTTONDOWN or self.calibrated:
            return
        if _inside((x, y), DONE_RECT):
            if self.tracker.track_color is None:
                self.warn = "Click an object first to select its colour"
            else:
                self.calibrated = True
                self.tracker.calibrated = True
        else:
            color = self.tracker.pick_color(x, y)
            self.warn = ""
            if color:
                print(f"[calibration] tracking colour BGR{color}")

    # ---------------------------------------------------------------- screens
    def _draw_calibration(self, window):
        frame = self.tracker.frame
        if frame is not None:
            _paste(window, frame, 0, 0, WINDOW_W, WINDOW_H)
        else:
            window[:] = (30, 30, 30)

        _paste(window, self.images["Done"], *DONE_RECT)
        if _inside(self.mouse, DONE_RECT):
            cv2.rectangle(
                window,
                (DONE_RECT[0], DONE_RECT[1]),
                (DONE_RECT[0] + DONE_RECT[2], DONE_RECT[1] + DONE_RECT[3]),
                (255, 255, 255), 3,
            )

        cv2.putText(
            window, "Click an object to select its colour, then click DONE",
            (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
            cv2.LINE_AA,
        )
        if self.tracker.track_color is not None:
            color = tuple(int(c) for c in self.tracker.track_color)
            cv2.rectangle(window, (20, 50), (60, 90), color, -1)
            cv2.rectangle(window, (20, 50), (60, 90), (255, 255, 255), 1)
        if self.warn:
            cv2.putText(
                window, self.warn, (20, 120), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (60, 60, 255), 2, cv2.LINE_AA,
            )

        if self.link.key1:
            cv2.putText(
                window, "Key-1 Pressed", (67, 571),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, KEY_TEXT_COLOR, 2, cv2.LINE_AA,
            )
        if self.link.key2:
            cv2.putText(
                window, "Key-2 Pressed", (67, 540),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, KEY_TEXT_COLOR, 2, cv2.LINE_AA,
            )

    def _draw_ui(self, window, key1):
        _paste(window, self.images["Aisha"], 0, 0, WINDOW_W, WINDOW_H)

        over_paint = (
            self.avg is not None
            and self.avg[0] < PAINT_HIT[0]
            and self.avg[1] < PAINT_HIT[1]
        )
        if key1 and self.avg and (over_paint or self.move_paint):
            self.move_paint = True
            self._paint_pos = self.avg
        elif self.move_paint:
            self.paint_screen = True
            self.move_paint = False
            self._paint_pos = PAINT_HOME
        else:
            self._paint_pos = PAINT_HOME
        _paste_center(
            window, self.images["Paint"], self._paint_pos[0], self._paint_pos[1],
            ICON_W, ICON_H,
        )

        over_led = (
            self.avg is not None
            and self.avg[0] > LED_HIT_MIN_X
            and self.avg[1] < LED_HIT_MAX_Y
        )
        if key1 and self.avg and (over_led or self.move_led):
            self.move_led = True
            self._led_pos = self.avg
        elif self.move_led:
            self.led_screen = True
            self.move_led = False
            self._led_pos = LED_HOME
        else:
            self._led_pos = LED_HOME
        _paste_center(
            window, self.images["LED_Toggle"], self._led_pos[0],
            self._led_pos[1], ICON_W, ICON_H,
        )

    def _draw_paint(self, window, key1):
        window[:] = PAINT_BG_COLOR
        _paste_center(
            window, self.images["Paint"], WINDOW_W // 2, WINDOW_H // 2,
            PAINT_BG[0], PAINT_BG[1],
        )

        if key1 and self.avg:
            px = int(self.avg[0] - PAINT_CANVAS[0])
            py = int(self.avg[1] - PAINT_CANVAS[1])
            if 0 <= px < PAINT_CANVAS[2] and 0 <= py < PAINT_CANVAS[3]:
                cv2.circle(self.canvas, (px, py), 4, (255, 255, 255), -1)

        _paste(window, self.canvas, *PAINT_CANVAS)
        cv2.putText(
            window, "key 2: back", (20, 30), cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (255, 255, 255), 2, cv2.LINE_AA,
        )

    def _draw_led(self, window, key1):
        window[:] = (255, 255, 255)
        _paste_center(
            window, self.images["LED_on"], LED_ON_RECT[0] + LED_ON_RECT[2] // 2,
            LED_ON_RECT[1] + LED_ON_RECT[3] // 2, LED_ON_RECT[2], LED_ON_RECT[3],
        )
        _paste_center(
            window, self.images["LED_off"],
            LED_OFF_RECT[0] + LED_OFF_RECT[2] // 2,
            LED_OFF_RECT[1] + LED_OFF_RECT[3] // 2, LED_OFF_RECT[2],
            LED_OFF_RECT[3],
        )

        command, label, color = None, None, None
        if key1 and self.avg:
            if _inside(self.avg, LED_ON_RECT):
                command, label, color = True, "LED turned on", (232, 30, 117)
            elif _inside(self.avg, LED_OFF_RECT):
                command, label, color = False, "LED turned off", (8, 8, 252)

        if label:
            _text_center(window, label, WINDOW_W // 2, WINDOW_H // 1.5, 1.2, color)
            self.link.send_led(command)

        cv2.putText(
            window, "key 2: back", (20, 30), cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (80, 80, 80), 2, cv2.LINE_AA,
        )
