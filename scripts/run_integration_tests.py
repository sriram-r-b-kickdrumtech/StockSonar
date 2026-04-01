#!/usr/bin/env python3
"""Run pytest integration tests and write combined output to a log file.

Requires: docker compose up -d (Keycloak, Redis, MCP).

Usage::

  .venv/bin/python scripts/run_integration_tests.py
  .venv/bin/python scripts/run_integration_tests.py --log-file logs/pytest_integration.log

Extra pytest args are forwarded, e.g.::

  .venv/bin/python scripts/run_integration_tests.py -v -k pkce
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--log-file",
        default="",
        help="Default: logs/pytest_integration_<timestamp>.log when --save-log",
    )
    p.add_argument(
        "--save-log",
        action="store_true",
        help="Always write pytest stdout/stderr to logs/pytest_integration_<timestamp>.log",
    )
    p.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments after -- are passed to pytest (use: script.py -- -v)",
    )
    args = p.parse_args()

    log_path: Path | None = None
    if args.log_file:
        log_path = Path(args.log_file).resolve()
    elif args.save_log:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = (REPO_ROOT / "logs" / f"pytest_integration_{ts}.log").resolve()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(REPO_ROOT / "tests" / "integration"),
        "-v",
        "--tb=short",
        "-m",
        "integration",
    ]
    extra = args.pytest_args
    if extra and extra[0] == "--":
        extra = extra[1:]
    cmd.extend(extra)

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    if log_path is None:
        print("Running:", " ".join(cmd), flush=True)
        return subprocess.call(cmd, cwd=str(REPO_ROOT), env=env)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Logging to: {log_path}", file=sys.stderr)
    print("Running:", " ".join(cmd), flush=True)
    with log_path.open("w", encoding="utf-8") as log_f:
        log_f.write(f"# cmd: {' '.join(cmd)}\n\n")
        log_f.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_f.write(proc.stdout or "")
        log_f.flush()
        print(proc.stdout or "", end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
