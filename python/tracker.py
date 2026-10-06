"""Webcam colour tracking - port of the Processing captureEvent / pixel loop."""

import cv2
import numpy as np


class ColorTracker:
    def __init__(self, camera=0, threshold=50, width=800, height=600):
        self.cap = cv2.VideoCapture(camera)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"could not open camera {camera} - try a different --camera index"
            )
        self.threshold = threshold
        self.width = width
        self.height = height
        self.frame = None
        self.track_color = None  # BGR
        self.calibrated = False  # mirrors the X axis once calibration is done
        self.last = None

    def read(self):
        ok, frame = self.cap.read()
        if ok:
            self.frame = frame
        return self.frame

    def pick_color(self, x, y):
        """Sample the colour under the given window coordinates."""
        if self.frame is None:
            return None
        fh, fw = self.frame.shape[:2]
        px = min(max(int(x * fw / self.width), 0), fw - 1)
        py = min(max(int(y * fh / self.height), 0), fh - 1)
        self.track_color = self.frame[py, px].astype(np.int16)
        return tuple(int(c) for c in self.track_color)

    def update(self):
        """Return the mirrored centroid of pixels matching the tracked colour."""
        if self.frame is None or self.track_color is None:
            return self.last

        diff = self.frame.astype(np.int32) - self.track_color
        mask = np.sum(diff * diff, axis=2) < self.threshold * self.threshold
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            return self.last

        fh, fw = self.frame.shape[:2]
        avg_x = float(xs.mean()) * self.width / fw
        avg_y = float(ys.mean()) * self.height / fh
        if self.calibrated:
            avg_x = self.width - avg_x
        self.last = (avg_x, avg_y)
        return self.last

    def release(self):
        self.cap.release()
