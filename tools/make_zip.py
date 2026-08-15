# -*- coding: utf-8 -*-
"""Package the complete runtime source tree into a shareable zip.

Writes whale_pet_source.zip into the repository root, containing every file
needed to run the pet, plus the sprites/ and samples/ asset directories.
"""
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "whale_pet_source.zip")

# Top-level files required for a complete run.
TOP_FILES = [
    "desktop_pet.py",
    "desktop_pet.spec",
    "balance.py",
    "voice.py",
    "dsh_watch.py",
    "dsh_service.py",
    "dsh_push.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "config.example.json",
    "icon.ico",
    ".gitignore",
    "start_pet.bat",
    "start_push.bat",
    "install.bat",
    "uninstall.bat",
]

# Whole directories collected recursively.
DIRS = ["sprites", "samples"]


def collect_dir(rel_dir):
    """Return every file under a directory, as repo-relative '/'-separated paths."""
    paths = []
    for root, _, files in os.walk(os.path.join(REPO, rel_dir)):
        for name in files:
            full = os.path.join(root, name)
            paths.append(os.path.relpath(full, REPO).replace(os.sep, "/"))
    return paths


def main():
    files = list(TOP_FILES)
    for rel_dir in DIRS:
        files.extend(collect_dir(rel_dir))

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(REPO, rel), rel)

    print("files:", len(files))
    print("size:", os.path.getsize(OUT) // 1024, "KB")
    for rel in files:
        print(" ", rel)


if __name__ == "__main__":
    main()
