# -*- coding: utf-8 -*-
"""
DSH process detection and launch (Whale Pet capability layer).

Detection: TCP-probe 127.0.0.1:<port>, then GET / and verify the response
contains the __DSH_BOOT__ marker, so we only treat the port as DSH Web when
it really is DSH and not some other program.
Launch: run node_modules\\.bin\\dsh.cmd web inside dsh_dir, writing output to
run.pet.log. When dry_run=True, return the command that would run instead of
actually starting it (for tests / preview).

Safety boundary: this module only *launches* (starts) DSH. It never stops,
restarts, or kills the DSH process.
"""
import os
import socket
import subprocess
import urllib.request

DSH_BOOT_MARK = "__DSH_BOOT__"
PORT_DEFAULT = 3080


class DshService:
    def __init__(self, dsh_dir, port=PORT_DEFAULT, dry_run=False, on_log=None):
        self.dsh_dir = dsh_dir
        self.port = int(port)
        self.dry_run = bool(dry_run)
        self.on_log = on_log or (lambda msg: None)

    def _cmd_path(self):
        return os.path.join(self.dsh_dir, "node_modules", ".bin", "dsh.cmd")

    def is_running(self, timeout=1.5):
        """Port reachable + response contains the DSH marker -> DSH Web is up."""
        try:
            s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
            s.close()
        except OSError:
            return False
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/",
                headers={"User-Agent": "dafeiyu-pet/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(65536).decode("utf-8", "ignore")
            return DSH_BOOT_MARK in body
        except Exception:
            return False

    def ensure_running(self):
        """Make sure DSH Web is running. Returns a status dict:
        {"started": bool, "already": bool, "error": str|None, "cmd": str|None, "dry_run": bool}
        """
        if self.is_running():
            return {"started": False, "already": True, "error": None, "cmd": None, "dry_run": False}

        cmd_path = self._cmd_path()
        if not os.path.isdir(self.dsh_dir):
            return {"started": False, "already": False,
                    "error": f"DSH directory does not exist: {self.dsh_dir}", "cmd": None, "dry_run": False}
        if not os.path.exists(cmd_path):
            return {"started": False, "already": False,
                    "error": f"DSH launcher not found: {cmd_path}", "cmd": None, "dry_run": False}

        cmd = f'"{cmd_path}" web'
        if self.dry_run:
            self.on_log(f'[dry-run] would run: cd /d "{self.dsh_dir}" && {cmd}')
            return {"started": False, "already": False, "error": None,
                    "cmd": cmd, "dry_run": True}

        try:
            log_path = os.path.join(self.dsh_dir, "run.pet.log")
            with open(log_path, "ab") as logf:
                subprocess.Popen(
                    cmd,
                    cwd=self.dsh_dir,
                    shell=True,
                    stdin=subprocess.DEVNULL,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                                   | subprocess.CREATE_NO_WINDOW,
                )
            self.on_log(f"launched DSH: {cmd}")
            return {"started": True, "already": False, "error": None, "cmd": cmd, "dry_run": False}
        except Exception as e:
            return {"started": False, "already": False,
                    "error": str(e)[:120], "cmd": cmd, "dry_run": False}


# ---------- self-check (detection + dry-run preview only, never a real launch) ----------
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        dsh_dir = sys.argv[1]
    else:
        dsh_dir = os.path.join(os.environ.get("ProgramFiles(x86)", ""), "dsh-web")
    svc = DshService(dsh_dir, port=PORT_DEFAULT)
    print("DSH dir:", dsh_dir)
    print("launcher exists:", os.path.exists(svc._cmd_path()))
    print("DSH Web running now:", svc.is_running())
    print("ensure_running:", svc.ensure_running())
    print("--- dry-run preview ---")
    dry = DshService(dsh_dir, port=PORT_DEFAULT, dry_run=True)
    print("ensure_running(dry_run):", dry.ensure_running())
    print("fake port (dry_run):", DshService(dsh_dir, port=1, dry_run=True).ensure_running())
