"""Run a command with a hard wall-clock timeout and preserve its output."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=170, help="Maximum runtime in seconds")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command after --")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a command after --")
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        print(output, end="" if output.endswith("\n") or not output else "\n")
        print(f"TIMED OUT after {args.timeout}s: {' '.join(command)}", file=sys.stderr, flush=True)
        return 124
    print(result.stdout, end="" if result.stdout.endswith("\n") or not result.stdout else "\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
