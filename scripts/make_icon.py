"""Generate src/assets/icon.icns from scratch using only stdlib.

Produces a 1024x1024 master PNG (indigo squircle background + centered
waveform bars in lighter indigo), then shells out to sips/iconutil to build
the .icns bundle.
"""

import os
import struct
import subprocess
import sys
import tempfile
import zlib


# The squircle-ish macOS app-icon shape: render a rounded-rect with a fairly
# large corner radius so it reads as the familiar app tile at every size.
CORNER_RADIUS_RATIO = 0.225

# Heights mirror the drop-zone glyph (same 11-bar audio-level silhouette).
BAR_HEIGHTS = (28, 52, 74, 96, 112, 124, 112, 96, 74, 52, 28)

# Colors — match the app's dark-mode accent scheme.
BG_TOP = (0x1C, 0x1E, 0x3B)       # deep indigo
BG_BOTTOM = (0x2A, 0x2D, 0x56)    # warmer mid indigo
BAR_CORE = (0xA5, 0xB4, 0xFC)     # indigo-300
BAR_GLOW = (0x81, 0x8C, 0xF8)     # indigo-400 (edge softening)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    blob = tag + data
    crc = zlib.crc32(blob) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + blob + struct.pack(">I", crc)


def _write_png(path: str, pixels: bytearray, width: int, height: int) -> None:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(pixels), 9)
    with open(path, "wb") as f:
        f.write(sig)
        f.write(_png_chunk(b"IHDR", ihdr))
        f.write(_png_chunk(b"IDAT", idat))
        f.write(_png_chunk(b"IEND", b""))


def _lerp(a: int, b: int, t: float) -> int:
    return max(0, min(255, int(round(a + (b - a) * t))))


def _inside_rounded_rect(x: int, y: int, w: int, h: int, r: float) -> bool:
    if r <= 0:
        return True
    # Quadrants
    if x < r and y < r:
        dx, dy = r - x, r - y
        return dx * dx + dy * dy <= r * r
    if x >= w - r and y < r:
        dx, dy = x - (w - 1 - r), r - y
        return dx * dx + dy * dy <= r * r
    if x < r and y >= h - r:
        dx, dy = r - x, y - (h - 1 - r)
        return dx * dx + dy * dy <= r * r
    if x >= w - r and y >= h - r:
        dx, dy = x - (w - 1 - r), y - (h - 1 - r)
        return dx * dx + dy * dy <= r * r
    return True


def _render(size: int) -> bytearray:
    """Return raw RGBA pixel bytes for one size-by-size icon master."""
    radius = size * CORNER_RADIUS_RATIO
    pixels = bytearray()

    # Pre-compute bar geometry — scale the reference bar sizes to the canvas.
    ref_canvas_h = 150  # design grid height for BAR_HEIGHTS
    scale = size * 0.52 / ref_canvas_h  # bars span ~52% of icon height
    bar_w = max(2, int(size * 0.048))
    gap = max(2, int(size * 0.018))
    n = len(BAR_HEIGHTS)
    bars_total_w = n * bar_w + (n - 1) * gap
    bars_x0 = (size - bars_total_w) // 2
    bar_radius = bar_w / 2.0
    center_y = size // 2

    def _bar_alpha(x: int, y: int) -> int:
        """Return 0-255 coverage for bar pixel at (x, y). Caps are rounded."""
        for i, h in enumerate(BAR_HEIGHTS):
            bx = bars_x0 + i * (bar_w + gap)
            if bx <= x < bx + bar_w:
                pixel_h = max(2, int(round(h * scale)))
                top = center_y - pixel_h // 2
                bot = top + pixel_h
                if top <= y < bot:
                    # Rounded end caps: a semicircle inside each end.
                    if y < top + bar_radius:
                        dx = (x - (bx + bar_radius - 0.5))
                        dy = (y - (top + bar_radius - 0.5))
                        d = (dx * dx + dy * dy) ** 0.5
                        if d > bar_radius:
                            return 0
                        if d > bar_radius - 1:
                            return int((bar_radius - d) * 255)
                    elif y >= bot - bar_radius:
                        dx = (x - (bx + bar_radius - 0.5))
                        dy = (y - (bot - bar_radius - 0.5))
                        d = (dx * dx + dy * dy) ** 0.5
                        if d > bar_radius:
                            return 0
                        if d > bar_radius - 1:
                            return int((bar_radius - d) * 255)
                    return 255
        return 0

    for y in range(size):
        # Filter byte for PNG scanline
        pixels.append(0)

        # Vertical background gradient
        t = y / max(1, size - 1)
        bg_r = _lerp(BG_TOP[0], BG_BOTTOM[0], t)
        bg_g = _lerp(BG_TOP[1], BG_BOTTOM[1], t)
        bg_b = _lerp(BG_TOP[2], BG_BOTTOM[2], t)

        for x in range(size):
            # Background visibility — respects rounded square mask
            if not _inside_rounded_rect(x, y, size, size, radius):
                pixels.extend((0, 0, 0, 0))
                continue

            alpha = _bar_alpha(x, y)
            if alpha == 0:
                pixels.extend((bg_r, bg_g, bg_b, 255))
                continue

            # Blend bar color with background at anti-aliased coverage.
            a = alpha / 255.0
            core_r, core_g, core_b = BAR_CORE
            r = int(round(core_r * a + bg_r * (1 - a)))
            g = int(round(core_g * a + bg_g * (1 - a)))
            b = int(round(core_b * a + bg_b * (1 - a)))
            pixels.extend((r, g, b, 255))
    return pixels


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    dest = os.path.join(repo_root, "src", "assets", "icon.icns")

    with tempfile.TemporaryDirectory() as tmp:
        master = os.path.join(tmp, "icon_1024.png")
        print(f"rendering 1024x1024 master → {master}")
        pixels = _render(1024)
        _write_png(master, pixels, 1024, 1024)

        iconset = os.path.join(tmp, "AudioBoost.iconset")
        os.makedirs(iconset)

        variants = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]
        for px, name in variants:
            out = os.path.join(iconset, name)
            subprocess.run(
                ["sips", "-z", str(px), str(px), master, "--out", out],
                check=True, capture_output=True,
            )
            print(f"  · {name} ({px}px)")

        subprocess.run(
            ["iconutil", "-c", "icns", iconset, "-o", dest],
            check=True,
        )
        print(f"\n✓ wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
