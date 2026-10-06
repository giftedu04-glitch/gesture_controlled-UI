"""Headless tests for the app logic - camera, GUI and serial are faked."""

import cv2
import numpy as np
import pytest

import app as app_mod
from assets import load


class FakeTracker:
    def __init__(self, *args, **kwargs):
        self.frame = None
        self.track_color = None
        self.calibrated = False
        self.last = None
        self.threshold = 50
        self.width, self.height = 800, 600

    def read(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[100:200, 100:200] = (0, 0, 255)  # red blob
        self.frame = frame
        return frame

    def pick_color(self, x, y):
        px = min(int(x * 640 / 800), 639)
        py = min(int(y * 480 / 600), 479)
        self.track_color = self.frame[py, px].astype(np.int16)
        return tuple(int(c) for c in self.track_color)

    def update(self):
        if self.frame is None or self.track_color is None:
            return self.last
        diff = self.frame.astype(np.int32) - self.track_color
        mask = np.sum(diff * diff, axis=2) < self.threshold ** 2
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            return self.last
        avg_x = float(xs.mean()) * 800 / 640
        avg_y = float(ys.mean()) * 600 / 480
        if self.calibrated:
            avg_x = 800 - avg_x
        self.last = (avg_x, avg_y)
        return self.last

    def release(self):
        pass


class FakeLink:
    def __init__(self, *args, **kwargs):
        self.key1 = False
        self.key2 = False
        self.sent = []

    def poll(self):
        pass

    def send_led(self, on):
        self.sent.append(on)

    def close(self):
        pass

    @staticmethod
    def ports():
        return []


@pytest.fixture
def make_app(monkeypatch):
    monkeypatch.setattr(app_mod, "ColorTracker", FakeTracker)
    monkeypatch.setattr(app_mod, "BluetoothLink", FakeLink)

    def _make():
        application = app_mod.App()
        application.tracker.read()
        return application

    return _make


def new_window():
    return np.zeros((600, 800, 3), np.uint8)


def test_calibration_picks_colour_and_mirrors(make_app):
    application = make_app()
    application._draw_calibration(new_window())
    application._on_mouse(cv2.EVENT_LBUTTONDOWN, 187, 187, None, None)
    assert tuple(application.tracker.track_color) == (0, 0, 255)

    application._on_mouse(cv2.EVENT_LBUTTONDOWN, 700, 570, None, None)  # DONE
    assert application.calibrated

    avg_x, avg_y = application.tracker.update()
    assert abs(avg_x - 613.1) < 1  # mirrored X of the red blob
    assert abs(avg_y - 186.9) < 1

    # clicks after calibration must not re-sample the colour
    application._on_mouse(cv2.EVENT_LBUTTONDOWN, 300, 300, None, None)
    assert tuple(application.tracker.track_color) == (0, 0, 255)


def test_done_requires_a_colour_first(make_app):
    application = make_app()
    application._on_mouse(cv2.EVENT_LBUTTONDOWN, 700, 570, None, None)
    assert not application.calibrated
    assert application.warn


def test_dragging_paint_icon_opens_paint_screen(make_app):
    application = make_app()
    application.avg = (100, 100)
    application._draw_ui(new_window(), key1=True)
    assert application.move_paint
    assert not application.paint_screen

    application._draw_ui(new_window(), key1=False)  # release key 1
    assert application.paint_screen


def test_dragging_led_icon_opens_led_screen(make_app):
    application = make_app()
    application.avg = (700, 100)
    application._draw_ui(new_window(), key1=True)
    assert application.move_led

    application._draw_ui(new_window(), key1=False)
    assert application.led_screen


def test_paint_screen_draws_on_canvas(make_app):
    application = make_app()
    application.avg = (210 + 90, 85 + 115)
    application._draw_paint(new_window(), key1=True)
    assert tuple(application.canvas[115, 90]) == (255, 255, 255)

    application.avg = (210 + 90, 85 + 115)
    application._draw_paint(new_window(), key1=False)  # no key 1, no paint
    assert tuple(application.canvas[10, 10]) == (0, 0, 0)


def test_key2_returns_to_main_screen(make_app):
    application = make_app()
    application.paint_screen = True
    application.led_screen = True
    application.move_paint = application.move_led = True
    application.link.key2 = True

    window = application.step()

    assert not (
        application.paint_screen
        or application.led_screen
        or application.move_paint
        or application.move_led
    )
    assert window.shape == (600, 800, 3)


def test_led_screen_sends_y_and_n(make_app):
    application = make_app()
    application.led_screen = True
    application.avg = (200, 200)
    application._draw_led(new_window(), key1=True)
    application.avg = (600, 200)
    application._draw_led(new_window(), key1=True)
    assert application.link.sent == [True, False]

    application._draw_led(new_window(), key1=False)  # key 1 inactive -> no send
    assert application.link.sent == [True, False]


def test_all_screens_render(make_app):
    application = make_app()
    application.avg = None
    application._draw_calibration(new_window())
    application.calibrated = True
    application._draw_ui(new_window(), key1=False)  # icons at home clip fine
    application._draw_paint(new_window(), key1=False)
    application._draw_led(new_window(), key1=True)


def test_placeholders_generated_for_missing_assets():
    image = load("Aisha", (800, 600))
    assert image.shape == (600, 800, 3)
