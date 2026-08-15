# -*- coding: utf-8 -*-
"""Unit tests for the dsh_watch event-stream state machine: build fake session
logs (zstd-compressed JSONL) and verify that ordinary tool execution is not
misreported, only questions / approvals report "waiting", and only turn/end
reports "done"."""
import json
import os
import shutil
import sys
import tempfile

import zstandard

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsh_watch import DshWatch, EVENT_TURN_DONE, EVENT_WAITING_USER

LID = "s1"


def ev(t, data=None, seq=None):
    return {"type": t, "seq": seq or 0, "time": 0,
            "data": data if data is not None else {}}


def tool_call(name, cid):
    return ev("tool/call", {"callId": cid, "name": name})


def tool_result(cid):
    return ev("tool/result", {"callId": cid})


def write_log(compressor, path, events):
    """Compress and write an event list to a session log (mimics DSH appends)."""
    text = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
    with open(path, "wb") as f:
        f.write(compressor.compress(text.encode("utf-8")))


def make_watch(tmp):
    w = DshWatch(home_dir=tmp)
    # Match the directory layout: sessions/<ws>/<sid>/session.jsonl.zstd
    ws = os.path.join(tmp, "sessions", "ws-test")
    sess = os.path.join(ws, LID)
    os.makedirs(sess, exist_ok=True)
    path = os.path.join(sess, "session.jsonl.zstd")
    return w, path


def main():
    tmp = tempfile.mkdtemp(prefix="dsh_watch_test_")
    w, path = make_watch(tmp)
    cctx = zstandard.ZstdCompressor()
    results = []

    def check(name, cond):
        results.append((name, cond))
        print(("PASS" if cond else "FAIL"), name)

    def append(events):
        # Rewrite the whole log (simulates file changes; monotonically growing
        # cases appear below)
        write_log(cctx, path, events)

    # 1) Baseline: session is running ordinary tools (pendingCalls non-empty,
    #    not running) -- the old version wrongly reported waiting_user; the new
    #    version must stay silent
    append([tool_call("read", "c1"), tool_call("glob", "c2")])
    evs = w.poll()
    check("baseline round: ordinary tools running must not report waiting", evs == [])

    # 2) Ordinary tool results -> no event; turn/end -> turn_done
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end")])
    evs = w.poll()
    check("ordinary tools done + turn/end -> turn_done",
          len(evs) == 1 and evs[0]["type"] == EVENT_TURN_DONE)

    # 3) ask_user_question pending -> waiting_user (a real waiting scenario)
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end"),
            tool_call("ask_user_question", "cq1")])
    evs = w.poll()
    check("ask_user_question pending -> waiting_user",
          len(evs) == 1 and evs[0]["type"] == EVENT_WAITING_USER)

    # 4) Question stays pending (file unchanged) -> do not re-emit
    evs = w.poll()
    check("question stays pending without re-emitting", evs == [])

    # 5) User answers (tool/result) -> pending cleared, then turn/end -> turn_done
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end"),
            tool_call("ask_user_question", "cq1"),
            tool_result("cq1"), ev("turn/end")])
    evs = w.poll()
    check("answer then turn/end -> turn_done with no extra waiting",
          len(evs) == 1 and evs[0]["type"] == EVENT_TURN_DONE)

    # 6) Approval pending: approval/asked -> waiting_user; decided clears it
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end"),
            tool_call("ask_user_question", "cq1"),
            tool_result("cq1"), ev("turn/end"),
            ev("approval/asked", {"id": "ap1"})])
    evs = w.poll()
    check("approval/asked -> waiting_user",
          len(evs) == 1 and evs[0]["type"] == EVENT_WAITING_USER)
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end"),
            tool_call("ask_user_question", "cq1"),
            tool_result("cq1"), ev("turn/end"),
            ev("approval/asked", {"id": "ap1"}),
            ev("approval/decided", {"id": "ap1"}), ev("turn/end")])
    evs = w.poll()
    check("approval decided + turn/end -> turn_done",
          len(evs) == 1 and evs[0]["type"] == EVENT_TURN_DONE)

    # 7) Model thinking (step/start not finished) produces no events
    append([tool_call("read", "c1"), tool_call("glob", "c2"),
            tool_result("c1"), tool_result("c2"), ev("turn/end"),
            tool_call("ask_user_question", "cq1"),
            tool_result("cq1"), ev("turn/end"),
            ev("approval/asked", {"id": "ap1"}),
            ev("approval/decided", {"id": "ap1"}), ev("turn/end"),
            ev("step/start", {"turn": 3, "step": 1})])
    evs = w.poll()
    check("step/start in progress -> no events", evs == [])

    # 8) Corrupt-log tolerance: writing truncated data must not raise
    with open(path, "ab") as f:
        f.write(b"\x00\x01broken")
    evs = w.poll()
    check("corrupt log does not raise", isinstance(evs, list))

    shutil.rmtree(tmp, ignore_errors=True)
    failed = [n for n, c in results if not c]
    print(f"\n{len(results)} checks total, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
