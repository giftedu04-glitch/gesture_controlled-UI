"""Image loading.

The original Processing sketch loaded Done.png, Aisha.png, Paint.png,
LED_Toggle.png, LED_on.png and LED_off.png from its data/ folder.
Drop your own copies into python/assets/ and they will be used automatically;
otherwise a simple placeholder is generated so the app runs out of the box.
"""

import os

import cv2
import numpy as np

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

PLACEHOLDERS = {
    "Done": ((70, 170, 70), "DONE"),
    "Aisha": ((106, 26, 19), "Gesture UI"),
    "Paint": ((170, 110, 30), "PAINT"),
    "LED_Toggle": ((232, 30, 117), "LED"),
    "LED_on": ((70, 200, 70), "LED ON"),
    "LED_off": ((60, 60, 230), "LED OFF"),
}


def _label(image, text, scale=1.0, thickness=2):
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    h, w = image.shape[:2]
    org = ((w - size[0]) // 2, (h + size[1]) // 2)
    cv2.putText(
        image, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255),
        thickness, cv2.LINE_AA,
    )


def load(name, size):
    """Return the image resized to exactly (width, height)."""
    width, height = size
    path = os.path.join(ASSETS_DIR, f"{name}.png")
    image = cv2.imread(path) if os.path.exists(path) else None
    if image is None:
        color, text = PLACEHOLDERS[name]
        image = np.full((height, width, 3), color, np.uint8)
        _label(image, text, scale=max(0.5, width / 300.0))
    elif image.shape[1] != width or image.shape[0] != height:
        image = cv2.resize(image, (width, height))
    return image
