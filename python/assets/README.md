UI images used by the app (PNG), with these exact names:

- `Done.png`       - calibration DONE button
- `Aisha.png`      - main screen background (800x600)
- `Paint.png`      - paint icon and paint screen artwork
- `LED_Toggle.png` - LED icon on the main screen
- `LED_on.png`     - LED ON button
- `LED_off.png`    - LED OFF button

The checked-in defaults are drawn by `generate.py` - run
`python python/assets/generate.py` to recreate them, or drop your own PNGs
over them. Any file you delete is generated as a labelled placeholder at
startup.
