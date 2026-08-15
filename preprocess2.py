# -*- coding: utf-8 -*-
"""Sprite edge decontamination + premultiplied-alpha scaling:
1) Un-blend edge pixels against white to recover their true color (removes the
   white fringe seen during movement / rotation)
2) Scale with the black/white composite method and generate every sprite size

Usage: python preprocess2.py [src_dir] [out_dir]
  src_dir: folder with front.png / side.png / back.png source images
           (default: "sprites")
  out_dir: output folder for the processed sprites (default: "sprites")
"""
from PIL import Image
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "sprites")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SCRIPT_DIR, "sprites")
SIZES = {0.55: 187, 0.7: 238, 0.9: 306}

os.makedirs(OUT, exist_ok=True)


def decontaminate(im):
    """Un-blend edge pixels against white: pixel = fg*a + 255*(1-a) -> fg = (pixel - 255*(1-a))/a"""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 0 < a < 255:
                t = a / 255.0
                if a < 40:          # extremely faint edges -> transparent, avoid noise
                    px[x, y] = (0, 0, 0, 0)
                    continue
                nr = (r - 255 * (1 - t)) / t
                ng = (g - 255 * (1 - t)) / t
                nb = (b - 255 * (1 - t)) / t
                px[x, y] = (int(max(0, min(255, nr))), int(max(0, min(255, ng))),
                            int(max(0, min(255, nb))), a)
    return im


def cutout(path):
    """White-background flood-fill cutout (reuses the v1 logic)"""
    im = Image.open(path).convert("RGBA")
    from PIL import ImageDraw
    w, h = im.size
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(im, (sx, sy), (0, 0, 0, 0), thresh=30)
    return im.crop(im.getbbox())


def premult_resize(im, height):
    """Premultiplied-alpha scaling: scale once on black and once on white, then
    solve for the true color + alpha"""
    w0, h0 = im.size
    nw = max(1, round(w0 * height / h0))
    black = Image.new("RGBA", im.size, (0, 0, 0, 255))
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    b_img = Image.alpha_composite(black, im).resize((nw, height), Image.LANCZOS)
    w_img = Image.alpha_composite(white, im).resize((nw, height), Image.LANCZOS)
    bp, wp = b_img.load(), w_img.load()
    out = Image.new("RGBA", (nw, height))
    op = out.load()
    for y in range(height):
        for x in range(nw):
            br, bg, bb, _ = bp[x, y]
            wr, wg, wb, _ = wp[x, y]
            a = 255 - max(wr - br, wg - bg, wb - bb)   # coverage
            if a < 6:
                op[x, y] = (0, 0, 0, 0)
                continue
            t = a / 255.0
            op[x, y] = (int(max(0, min(255, br / t))), int(max(0, min(255, bg / t))),
                        int(max(0, min(255, bb / t))), a)
    return out


for name in ["front", "side", "back"]:
    raw = cutout(os.path.join(SRC, f"{name}.png"))
    clean = decontaminate(raw)
    for mult, h in SIZES.items():
        im = premult_resize(clean, h)
        im.save(os.path.join(OUT, f"{name}_{h}.png"))
        print(f"{name}_{h}.png {im.size}")

# Tray icon (shrink from the mid size)
icon = Image.open(os.path.join(OUT, "front_187.png")).convert("RGBA")
icon = premult_resize(icon, 64)
icon.save(os.path.join(OUT, "icon.png"))
print("icon 64x64")
