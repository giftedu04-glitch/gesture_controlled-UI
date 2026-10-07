"""Generate the six UI artwork PNGs for python/assets/ (drawn with OpenCV).

Run `python python/assets/generate.py` to recreate them; your own PNGs with
the same names simply overwrite these and are used instead.
"""

import os
import cv2
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
S = 4  # supersampling factor

# BGR colours
WHITE = (255, 255, 255)
GRAY = (158, 148, 139)
FRAME = (61, 54, 48)
TRACK = (33, 250, 219)
PAINT_BG = (106, 25, 11)  # #0B196A


def vgrad(w, h, top, bot):
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = np.array(top, np.float32) * (1 - g) + np.array(bot, np.float32) * g
    return np.repeat(arr.astype(np.uint8), w, axis=1)


def canvas(w, h, color):
    return np.full((h * S, w * S, 3), color, np.uint8)


def rr(img, x1, y1, x2, y2, r, color, border=None, bt=1):
    """Filled rounded rect; coords in logical pixels."""
    X1, Y1, X2, Y2, R = int(x1 * S), int(y1 * S), int(x2 * S), int(y2 * S), int(r * S)

    def fill(c, a, b, cc, dd, rad):
        if rad <= 0:
            cv2.rectangle(img, (a, b), (cc, dd), c, -1, cv2.LINE_AA)
            return
        cv2.rectangle(img, (a + rad, b), (cc - rad, dd), c, -1, cv2.LINE_AA)
        cv2.rectangle(img, (a, b + rad), (cc, dd - rad), c, -1, cv2.LINE_AA)
        for cx, cy in ((a + rad, b + rad), (cc - rad, b + rad),
                       (a + rad, dd - rad), (cc - rad, dd - rad)):
            cv2.circle(img, (cx, cy), rad, c, -1, cv2.LINE_AA)

    if border is not None:
        fill(border, X1, Y1, X2, Y2, R)
        t = int(bt * S)
        fill(color, X1 + t, Y1 + t, X2 - t, Y2 - t, R - t)
    else:
        fill(color, X1, Y1, X2, Y2, R)


def ctext(img, s, cx, cy, scale, color, thick=2, font=cv2.FONT_HERSHEY_SIMPLEX):
    ts = cv2.getTextSize(s, font, scale * S, thick * S)[0]
    org = (int(cx * S - ts[0] / 2), int(cy * S + ts[1] / 2))
    cv2.putText(img, s, org, font, scale * S, color, int(thick * S), cv2.LINE_AA)


def save(name, img, w, h):
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    path = os.path.join(OUT, name)
    cv2.imwrite(path, img)
    print("wrote", path)


# ----------------------------------------------------------------- Done.png
def gen_done():
    w, h = 134, 55
    img = vgrad(w * S, h * S, (80, 185, 63), (54, 134, 35))
    rr(img, 1, 1, w - 1, h - 1, 0, (54, 134, 35), border=(30, 70, 25), bt=2)
    cv2.rectangle(img, (int(5 * S), int(5 * S)), (int((w - 5) * S), int((h - 5) * S)),
                  (120, 220, 140), max(1, S // 2), cv2.LINE_AA)
    ctext(img, "DONE", w / 2, h / 2 + 1, 0.9, WHITE, 2)
    save("Done.png", img, w, h)


# --------------------------------------------------------------- Aisha.png
def gen_aisha():
    w, h = 800, 600
    img = vgrad(w * S, h * S, (23, 17, 13), (34, 27, 22))

    # empty-slot frames aligned with the PAINT / LED hit regions
    cv2.rectangle(img, (0, 0), (int(180 * S), int(146 * S)), FRAME, 2 * S, cv2.LINE_AA)
    cv2.rectangle(img, (int(627 * S), 0), (int(w * S) - 1, int(146 * S)),
                  FRAME, 2 * S, cv2.LINE_AA)
    ctext(img, "PAINT", 80, 170, 0.55, GRAY, 1)
    ctext(img, "LED", 713, 170, 0.55, GRAY, 1)

    ctext(img, "GESTURE CONTROLLED UI", 400, 250, 1.15, WHITE, 2)
    ctext(img, "drag an icon with your tracked colour while key 1 is held",
          400, 300, 0.55, GRAY, 1)
    ctext(img, "release key 1 to open it  -  key 2 goes back", 400, 332, 0.55, GRAY, 1)

    # tracked-colour cursor demo
    cx, cy = 400, 450
    for radius, col in ((44, (76, 118, 100)), (30, (54, 168, 145))):
        cv2.circle(img, (cx * S, cy * S), radius * S, col, 2 * S, cv2.LINE_AA)
    cv2.circle(img, (cx * S, cy * S), 12 * S, TRACK, -1, cv2.LINE_AA)
    ctext(img, "your tracked colour", 400, 530, 0.5, GRAY, 1)
    save("Aisha.png", img, w, h)


# --------------------------------------------------------------- Paint.png
def gen_paint():
    w, h = 200, 150
    img = np.full((h * S, w * S, 3), PAINT_BG, np.uint8)

    def blob(x, y, r, col):
        cv2.circle(img, (int(x * S), int(y * S)), int(r * S), col, -1, cv2.LINE_AA)

    # drips from the top edge (visible when this image is the paint backdrop)
    for x, col in ((40, (40, 40, 230)), (95, (0, 220, 230)), (150, (60, 170, 60))):
        blob(x, 10, 7, col)
        cv2.rectangle(img, (int((x - 2) * S), int(12 * S)),
                      (int((x + 2) * S), int(24 * S)), col, -1, cv2.LINE_AA)

    # palette
    cv2.ellipse(img, (100 * S, 66 * S), (66 * S, 46 * S), 0, 0, 360,
                (65, 164, 217), -1, cv2.LINE_AA)
    blob(98, 92, 15, PAINT_BG)  # thumb hole
    for x, y, col in ((60, 42, (40, 40, 230)), (92, 28, (0, 220, 230)),
                      (128, 36, (60, 170, 60)), (148, 66, (200, 200, 0)),
                      (56, 72, (230, 60, 230))):
        blob(x, y, 9, col)

    # splashes along the bottom edge
    for x, y, r, col in ((45, 118, 10, (230, 60, 230)), (105, 128, 12, (200, 200, 0)),
                         (160, 115, 9, (0, 220, 230)), (75, 137, 6, (40, 40, 230)),
                         (138, 140, 5, (60, 170, 60))):
        blob(x, y, r, col)
    save("Paint.png", img, w, h)


# ----------------------------------------------------------- LED_Toggle.png
def gen_led_toggle():
    w, h = 200, 150
    img = vgrad(w * S, h * S, (55, 50, 45), (38, 33, 29))

    cx, cy = 100, 64
    for deg in (0, 45, 135, 180, 225, 270, 315):
        a = np.deg2rad(deg)
        x1 = int((cx + np.cos(a) * 44) * S)
        y1 = int((cy + np.sin(a) * 44) * S)
        x2 = int((cx + np.cos(a) * 56) * S)
        y2 = int((cy + np.sin(a) * 56) * S)
        cv2.line(img, (x1, y1), (x2, y2), (120, 220, 255), 3 * S, cv2.LINE_AA)

    cv2.circle(img, (cx * S, cy * S), 36 * S, (40, 190, 245), -1, cv2.LINE_AA)
    rr(img, 82, 96, 118, 116, 4, (120, 125, 130), border=(70, 75, 80), bt=1)
    cv2.line(img, (int(86 * S), int(105 * S)), (int(114 * S), int(105 * S)),
             (70, 75, 80), 2 * S, cv2.LINE_AA)
    cv2.line(img, (int(86 * S), int(111 * S)), (int(114 * S), int(111 * S)),
             (70, 75, 80), 2 * S, cv2.LINE_AA)
    ctext(img, "LED", 100, 136, 0.8, WHITE, 2)
    save("LED_Toggle.png", img, w, h)


# -------------------------------------------------------- LED_on/off.png
def _led_button(name, top, bot, border, label):
    w, h = 200, 120
    bt = 2  # border thickness (logical px)
    img = np.full((h * S, w * S, 3), WHITE, np.uint8)
    button = vgrad(w * S, h * S, top, bot)

    # filled rounded-rect mask
    mimg = np.zeros((h * S, w * S, 3), np.uint8)
    rr(mimg, 6, 6, w - 6, h - 6, 16, WHITE)
    filled = mimg[:, :, 0]
    img[filled > 0] = button[filled > 0]

    # border ring = filled minus eroded filled
    inner = cv2.erode(filled, np.ones((bt * 2 * S + 1, bt * 2 * S + 1), np.uint8))
    img[(filled > 0) & (inner == 0)] = border

    # power icon + label
    cx, cy, r = 100, 44, 18
    cv2.ellipse(img, (cx * S, cy * S), (r * S, r * S), 0, -60, 240,
                WHITE, 3 * S, cv2.LINE_AA)
    cv2.line(img, (cx * S, (cy - r - 6) * S), (cx * S, (cy + 2) * S),
             WHITE, 3 * S, cv2.LINE_AA)
    ctext(img, label, 100, 88, 0.95, WHITE, 2)
    save(name, img, w, h)


def gen_led_on():
    _led_button("LED_on.png", (80, 185, 63), (54, 134, 35), (35, 90, 25), "ON")


def gen_led_off():
    _led_button("LED_off.png", (90, 60, 220), (46, 34, 207), (110, 25, 30), "OFF")


if __name__ == "__main__":
    gen_done()
    gen_aisha()
    gen_paint()
    gen_led_toggle()
    gen_led_on()
    gen_led_off()
