#!/usr/bin/env python3
"""Stop running Hot70 test scripts via STOP file + PID files."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "reports" / "runs"


def _read_pid(pid_file: Path) -> int | None:
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
        return int(raw)
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop running smoke/full tests.")
    parser.add_argument("--reason", default="manual_stop")
    parser.add_argument("--no-kill", action="store_true", help="Only write STOP file; do not taskkill PID files.")
    args = parser.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    stop_file = RUNS / "STOP"
    stop_note = f"{datetime.now().isoformat(timespec='seconds')} {args.reason}"
    stop_file.write_text(stop_note, encoding="utf-8")
    print(f"stop_file={stop_file}")

    if args.no_kill:
        print("skip taskkill (--no-kill)")
        return

    pid_files = sorted(RUNS.glob("*latest.pid"))
    if not pid_files:
        print("no pid files")
        return

    for pf in pid_files:
        pid = _read_pid(pf)
        if not pid:
            print(f"skip invalid pid file: {pf}")
            continue
        cmd = ["taskkill", "/PID", str(pid), "/T", "/F"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"killed pid={pid} via {pf.name}")
        else:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            print(f"taskkill pid={pid} failed: {stderr or stdout or 'unknown'}")


if __name__ == "__main__":
    main()