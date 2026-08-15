# -*- coding: utf-8 -*-
"""
DeepSeek Open Platform API balance query (Whale Pet capability layer).

Endpoint: GET https://api.deepseek.com/user/balance
Returns a balance_infos array with per-currency balance details (CNY / USD, etc.).
This endpoint consumes no tokens -- it is a free, read-only query.

API key lookup order (decided by the caller):
  1. ds_api_key in the pet's config.json (filled in manually by the user)
  2. DEEPSEEK_API_KEY in the DSH credentials file ~/.dsh/.credentials.yaml
"""
import os
import re

import requests

BALANCE_URL = "https://api.deepseek.com/user/balance"


def fetch_balance(api_key, timeout=10):
    """Query the balance; returns a normalized dict:
    {"ok": True, "available": bool, "currency": "CNY",
     "total": 0.0, "granted": 0.0, "topped_up": 0.0}
    or {"ok": False, "error": "reason"}
    """
    if not api_key:
        return {"ok": False, "error": "no API key configured"}
    try:
        r = requests.get(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Accept": "application/json"},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "request timed out"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "network connection failed"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}

    if r.status_code == 401:
        return {"ok": False, "error": "invalid API key (401)"}
    if r.status_code != 200:
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    try:
        data = r.json()
    except Exception:
        return {"ok": False, "error": "unexpected response format"}

    infos = data.get("balance_infos") or []
    info = infos[0] if infos else {}
    try:
        return {
            "ok": True,
            "available": bool(data.get("is_available")),
            "currency": info.get("currency", "CNY"),
            "total": float(info.get("total_balance", 0) or 0),
            "granted": float(info.get("granted_balance", 0) or 0),
            "topped_up": float(info.get("topped_up_balance", 0) or 0),
        }
    except (TypeError, ValueError):
        return {"ok": False, "error": "could not parse balance fields"}


def format_balance(info, short=False):
    """Turn a fetch_balance result into a human-readable string."""
    if not info.get("ok"):
        return f"Balance query failed: {info.get('error', 'unknown error')}"
    cur = info.get("currency", "CNY")
    total = info.get("total", 0)
    if short:
        return f"Balance {total:.2f} {cur}"
    return (f"Balance {total:.2f} {cur} | granted {info.get('granted', 0):.2f}"
            f" | topped up {info.get('topped_up', 0):.2f}")


def load_key_from_dsh_credentials():
    """Read DEEPSEEK_API_KEY from the DSH credentials file (fallback key source)."""
    cred_path = os.path.join(os.path.expanduser("~"), ".dsh", ".credentials.yaml")
    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    m = re.search(r"^\s*DEEPSEEK_API_KEY\s*:\s*(\S+)", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


# ---------- self-check ----------
if __name__ == "__main__":
    key = load_key_from_dsh_credentials()
    print("Key in DSH credentials:", (key[:8] + "...") if key else "(none)")
    info = fetch_balance(key)
    print(format_balance(info))
