# -*- coding: utf-8 -*-
"""
Phone notifications for the Whale Pet (sister module) -- forward DSH session
events to your phone via ntfy.

Reuses the event folding in dsh_watch.DshWatch (read-only session log access,
never intrusive to DSH):
  waiting_user -> approval / question waiting for the user -> high-priority push
  turn_done   -> one work turn finished                    -> normal push

Usage:
  py dsh_push.py            # watch continuously and push
  py dsh_push.py --test     # send one test notification right now (verify channel)

Configuration (optional environment variables):
  NTFY_URL     Push server, default https://ntfy.sh
  NTFY_TOPIC   Topic name (a topic is effectively a secret -- do not share it)
  NTFY_TOKEN   Optional: ntfy account access token
  NTFY_CLICK   Optional: URL to open when the notification is tapped
"""
import os
import sys
import time
import urllib.parse
import urllib.request

from dsh_watch import DshWatch, EVENT_TURN_DONE, EVENT_WAITING_USER

NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "YOUR_NTFY_TOPIC")
NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "")
# URL opened when a notification is tapped (e.g. your DSH web entrypoint).
# Leave empty to disable the tap action.
NTFY_CLICK = os.environ.get("NTFY_CLICK", "")
POLL_SECONDS = 2

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsh_push.log")


def log(msg):
    """Append to the log file (pythonw has no stdout; print would crash)."""
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n")
    except Exception:
        pass


def push(title, message, priority=3, tags=""):
    url = f"{NTFY_URL}/{urllib.parse.quote(NTFY_TOPIC, safe='')}"
    headers = {
        "Title": urllib.parse.quote(title, safe=""),
        "Priority": str(priority),
    }
    if tags:
        headers["Tags"] = tags
    if NTFY_CLICK:
        headers["Click"] = urllib.parse.quote(NTFY_CLICK, safe="")
    if NTFY_TOKEN:
        headers["Authorization"] = "Bearer " + NTFY_TOKEN
    req = urllib.request.Request(
        url, data=message.encode("utf-8"), method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        log(f"push failed: {e}")
        return None


def main():
    if "--test" in sys.argv:
        status = push("Channel test", "Whale Pet: DSH phone notifications are working!",
                      priority=5, tags="whale")
        print(f"[dsh_push] test push status: {status}", flush=True)
        return

    watch = DshWatch()
    log(f"started watching DSH sessions (topic={NTFY_TOPIC})")

    def on_event(ev):
        t = ev.get("type")
        title = ev.get("title") or "Untitled session"
        if t == EVENT_WAITING_USER:
            push("DSH needs you", f"\"{title}\" is waiting for you (approval or question)",
                 priority=5, tags="warning")
        elif t == EVENT_TURN_DONE:
            push("DSH task done", f"\"{title}\" finished a turn",
                 priority=3, tags="check")

    watch.on_event = on_event
    while True:
        try:
            watch.poll()
        except Exception as e:
            log(f"poll error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
