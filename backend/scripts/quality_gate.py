"""Run the backend quality gate used before moving to the next phase."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CHECK_PATHS = ("app", "tests", "scripts", "alembic")


def run_step(label: str, command: Sequence[str]) -> int:
    print(f"\n== {label} ==")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=BACKEND_ROOT, check=False)
    if completed.returncode == 0:
        print(f"OK {label}")
    else:
        print(f"FAILED {label} ({completed.returncode})")
    return completed.returncode


def require_module(module_name: str, install_hint: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module_name, "--version"],
        cwd=BACKEND_ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"Missing required tool: {module_name}\n"
            f"Install development dependencies first:\n\n"
            f"  {install_hint}\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply Ruff formatting and safe lint fixes before running checks.",
    )
    parser.add_argument(
        "--with-smoke",
        action="store_true",
        help="Also run the live API smoke test. Requires Uvicorn to be running.",
    )
    args = parser.parse_args()

    python = sys.executable
    install_hint = rf"{python} -m pip install -r requirements-dev.txt"
    require_module("ruff", install_hint)

    commands: list[tuple[str, Sequence[str]]] = []
    if args.fix:
        commands.extend(
            [
                ("ruff format", [python, "-m", "ruff", "format", *CHECK_PATHS]),
                ("ruff safe fixes", [python, "-m", "ruff", "check", "--fix", *CHECK_PATHS]),
            ]
        )

    commands.extend(
        [
            ("compile", [python, "-m", "compileall", "-q", *CHECK_PATHS]),
            ("ruff format check", [python, "-m", "ruff", "format", "--check", *CHECK_PATHS]),
            ("ruff lint", [python, "-m", "ruff", "check", *CHECK_PATHS]),
            ("pytest", [python, "-m", "pytest", "-q"]),
        ]
    )

    alembic_executable = Path(sys.executable).with_name("alembic.exe")
    if not alembic_executable.exists():
        alembic_executable = Path(sys.executable).with_name("alembic")
    if alembic_executable.exists():
        commands.append(("alembic current", [str(alembic_executable), "current"]))

    if args.with_smoke:
        time.sleep(2)
        commands.append(("live API smoke test", [python, "scripts/smoke_test_api.py"]))

    for label, command in commands:
        exit_code = run_step(label, command)
        if exit_code != 0:
            return exit_code

    print("\nQuality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
