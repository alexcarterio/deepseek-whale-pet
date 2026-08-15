# -*- coding: utf-8 -*-
"""Package the source tree into a shareable zip (excludes venv/build artifacts/
config)."""
import os
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "whale_pet_source.zip")

files = ["desktop_pet.py", "preprocess.py", "preprocess2.py", "start_pet.bat",
         "requirements.txt", "README.md", "LICENSE", "icon.ico", ".gitignore"]
for root, dirs, fs in os.walk(os.path.join(BASE, "sprites")):
    for f in fs:
        files.append(os.path.relpath(os.path.join(root, f), BASE).replace(os.sep, "/"))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(os.path.join(BASE, f), f)

print("files:", len(files))
print("size:", os.path.getsize(OUT) // 1024, "KB")
for f in files:
    print(" ", f)
