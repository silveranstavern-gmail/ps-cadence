The Cadence icon depicts an open book and a speech waveform in the reader's colors.
`../ui/cadence.svg` is the editable vector source used by the header and browser tab.
`cadence.png` is its transparent 1024px raster export. `cadence.ico` contains 16, 20,
24, 32, 40, 48, 64, 128, and 256px variants for Windows title bars, taskbars, and Explorer.

After changing the SVG, export it on a transparent background and regenerate the ICO
with Pillow (a development-only tool):

```python
from PIL import Image
Image.open('assets/cadence.png').save('assets/cadence.ico', sizes=[
    (n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)
])
```

The desktop entry point supplies the ICO explicitly to pywebview, including launches
from Python. `reader.spec` embeds it in the executable and copies it into the runtime
resources. Windows product/version properties are in `windows-version.txt`.
