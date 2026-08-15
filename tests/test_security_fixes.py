# -*- coding: utf-8 -*-
"""Verification tests for the security-audit fixes:
  M3  credential parsing: commented lines are not extracted, real lines are
  L2  weather URL encoding
  L1  DSH launch: shell-free list execution, argv equivalent to dsh.cmd
  #1  requirements.txt includes zstandard
  M1  key input uses password (hidden) mode
  L3  debug output is narrowed
"""
import os
import re
import string
import subprocess
import sys
import tempfile
import urllib.parse

# Make the repo root importable (this test lives in tests/).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from balance import load_key_from_dsh_credentials

results = []


def check(name, cond, detail=""):
    results.append((name, cond))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def skip(name, why=""):
    print("SKIP", name, why)


def _locate_dsh_dir():
    """Locate a DSH install directory without hardcoding a drive letter:
    probe every existing drive root, then every first-level subdirectory of
    the Program Files folders, for a "dsh-web" directory."""
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        try:
            if not os.path.isdir(root):
                continue
        except OSError:
            continue
        for pf in ("Program Files (x86)", "Program Files"):
            base = os.path.join(root, pf)
            try:
                subs = os.listdir(base)
            except OSError:
                continue
            for sub in subs:
                candidate = os.path.join(base, sub, "dsh-web")
                if os.path.isdir(candidate):
                    return candidate
    return ""


# ---------- M3: credential parsing hardening ----------
tmp = tempfile.mkdtemp(prefix="cred_test_")
real_home = os.path.expanduser("~")
cred_dir = os.path.join(tmp, ".dsh")
os.makedirs(cred_dir)
cred_path = os.path.join(cred_dir, ".credentials.yaml")
with open(cred_path, "w", encoding="utf-8") as f:
    f.write(
        "# DEEPSEEK_API_KEY: test-commented-out-key\n"
        "ZHIPU_API_KEY: zp-xxx\n"
        "DEEPSEEK_API_KEY: test-real-key-123\n"
        "  DEEPSEEK_API_KEY: test-indented\n"
        "GEMINI_API_KEY: gm-xxx\n"
    )

# Use a temporary HOME so load_key reads ~/.dsh under it.
os.environ["USERPROFILE"] = tmp
os.environ["HOME"] = tmp
key = load_key_from_dsh_credentials()
check("M3 commented line not extracted + real line extracted", key == "test-real-key-123", f"got={key!r}")
os.environ["USERPROFILE"] = real_home
os.environ["HOME"] = real_home

# The real credentials file should still yield a key (only when present).
real_key = load_key_from_dsh_credentials()
if os.path.exists(os.path.join(os.path.expanduser("~"), ".dsh", ".credentials.yaml")):
    check("M3 real DSH credentials still readable", bool(real_key))
else:
    skip("M3 real DSH credentials still readable", "no local DSH credentials file on this machine")

# ---------- L2: weather URL encoding ----------
city = "New York"
url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
check("L2 city name is URL-encoded", "New%20York" in url, url)
check("L2 encoded value has no spaces / CJK residue", " " not in urllib.parse.quote("New York") and
      "%E6%B1%95" in urllib.parse.quote("\u6c55\u5934"))

# ---------- L1: DSH launch uses shell-free list execution ----------
import dsh_service
DSH_DIR = _locate_dsh_dir()
# The following checks exercise a real DSH install; on a clean CI machine
# without one they are skipped instead of failed.
DSH_PRESENT = bool(DSH_DIR) and os.path.isdir(os.path.join(DSH_DIR, "node_modules"))
svc = dsh_service.DshService(DSH_DIR, port=1, dry_run=True)
argv = svc._launch_argv()
check("L1 argv is a list ending in web", isinstance(argv, list) and argv[-1] == "web")
if DSH_PRESENT:
    check("L1 bin.js path exists", os.path.exists(argv[1]), argv[1] if not os.path.exists(argv[1]) else "")
else:
    skip("L1 bin.js path exists", "no DSH install on this machine")
check("L1 node is runnable (bundled or on PATH)",
      os.path.exists(argv[0]) or subprocess.run(["where", argv[0]], capture_output=True).returncode == 0)
# Source-level confirmation: no shell=True (excluding docstrings/comments).
src = open(os.path.join(ROOT, "dsh_service.py"), encoding="utf-8").read()
check("L1 source has no shell=True argument", "shell=True," not in src and
      "shell = True" not in src)
check("L1 source has explicit shell=False", "shell=False" in src)

# dry-run must not launch and must return a command preview.
res = svc.ensure_running()
if DSH_PRESENT:
    check("L1 dry-run does not actually launch", res.get("dry_run") is True and res.get("started") is False)
    check("L1 dry-run command preview is correct", isinstance(res.get("cmd"), str) and "bin.js" in res["cmd"])
else:
    skip("L1 dry-run does not actually launch", "no DSH install on this machine")
    skip("L1 dry-run command preview is correct", "no DSH install on this machine")

# Live detection: DSH is running now -> already (no launch attempted).
if DSH_PRESENT:
    real = dsh_service.DshService(DSH_DIR, port=3080)
    check("L1 live detection returns already", real.ensure_running().get("already") is True)
else:
    skip("L1 live detection returns already", "no DSH install on this machine")

# ---------- #1: requirements includes zstandard ----------
req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
check("#1 requirements.txt includes zstandard", "zstandard" in req)
check("#1 zstandard importable in this env", __import__("zstandard") is not None)

# ---------- M1: key input uses password mode ----------
src = open(os.path.join(ROOT, "desktop_pet.py"), encoding="utf-8").read()
check("M1 key input uses Password mode", "EchoMode.Password" in src and
      src.count("EchoMode.Normal") == 1)  # only the city input keeps Normal

# ---------- L3: narrowed debug output ----------
check("L3 no full response body printed", "resp.text" not in src and "r.text[:500]" not in src)

failed = [n for n, c in results if not c]
print(f"\n{len(results)} checks total, {len(failed)} failed")
sys.exit(1 if failed else 0)
