# -*- coding: utf-8 -*-
"""Three-view sprite cutout + normalization: white background -> transparent
PNG, uniform height, cropped empty margins.

Usage: python preprocess.py [src_dir] [out_dir]
  src_dir: folder with front.png / side.png / back.png source images
           (default: "sprites")
  out_dir: output folder for the processed sprites (default: "sprites")
"""
from PIL import Image, ImageDraw
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "sprites")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SCRIPT_DIR, "sprites")
TARGET_H = 340  # pet display height (px)

os.makedirs(OUT, exist_ok=True)


def cutout(path):
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    # 1) Flood-fill from the four corners so the whole background turns
    #    transparent (whites inside the character are unaffected)
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(im, (sx, sy), (0, 0, 0, 0), thresh=30)
    # 2) Remove white fringes: bright pixels next to transparent areas also
    #    become transparent (eliminates anti-aliasing halos)
    for _ in range(3):
        px = im.load()
        changed = False
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if r > 215 and g > 215 and b > 215:
                    # Check whether any neighbor is transparent
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                            px[x, y] = (0, 0, 0, 0)
                            changed = True
                            break
        if not changed:
            break
    # 3) Crop transparent margins
    bbox = im.getbbox()
    if bbox is None:
        raise RuntimeError(f"{path}: cutout ended up empty!")
    im = im.crop(bbox)
    # 4) Normalize height
    w2, h2 = im.size
    scale = TARGET_H / h2
    im = im.resize((max(1, round(w2 * scale)), TARGET_H), Image.LANCZOS)
    return im


for name in ["front", "side", "back"]:
    im = cutout(os.path.join(SRC, f"{name}.png"))
    out_path = os.path.join(OUT, f"{name}.png")
    im.save(out_path)
    print(f"{name}: {im.size} -> {out_path}")

# Tray icon
Icon = cutout(os.path.join(SRC, "front.png")).resize((64, 64), Image.LANCZOS)
Icon.save(os.path.join(OUT, "icon.png"))
print("icon: 64x64")
