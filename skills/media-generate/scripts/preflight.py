#!/usr/bin/env python3
"""Check local media tooling and credential presence without printing secrets."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_environment(names: tuple[str, ...]) -> bool:
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        print("Missing environment variables: " + ", ".join(missing))
        return False
    print("Required environment variables are present (access not yet verified).")
    return True


def check_dreamina() -> bool:
    binary = shutil.which("dreamina-canvas")
    if not binary:
        print("Dreamina Canvas CLI is missing; follow the separately installed dreamina-canvas-cli skill.")
        return False
    try:
        result = subprocess.run([binary, "auth", "status"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        print("Dreamina login check could not run; follow dreamina-canvas-cli authentication instructions.")
        return False
    if result.returncode:
        print("Dreamina login is unavailable; follow dreamina-canvas-cli authentication instructions.")
        return False
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        status = {}
    if status.get("ok") is True and status.get("data", {}).get("loggedIn") is True:
        print("Dreamina CLI reports an existing login; verify the intended account before generation.")
        return True
    print("Dreamina login could not be confirmed; follow dreamina-canvas-cli authentication instructions.")
    return False


def check_tesseract() -> bool:
    binary = shutil.which("tsrct")
    if not binary:
        for path in (Path.home() / "Library/Application Support/Tesseract/bin/tsrct", Path.home() / ".local/share/Tesseract/bin/tsrct"):
            if path.is_file():
                binary = str(path)
                break
    if not binary:
        print("Tesseract CLI is missing; follow tesseract-motion/references/installation.md.")
        return False
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        print("Tesseract CLI did not start; follow its installation guide.")
        return False
    if result.returncode:
        print("Tesseract CLI did not start; follow its installation guide.")
        return False
    pin = Path(__file__).resolve().parents[2] / "tesseract-motion/references/cli-version.txt"
    if not pin.is_file():
        print("Tesseract version pin is missing; release package is incomplete.")
        return False
    required = pin.read_text().strip()
    if required not in result.stdout:
        print(f"Tesseract CLI version does not match required {required}; follow its installation guide.")
        return False
    print(f"Tesseract CLI starts at required version {required}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", action="store_true", help="Check Console gateway key presence")
    parser.add_argument("--native", action="store_true", help="Check scoped HybrIE access settings")
    parser.add_argument("--dreamina", action="store_true", help="Check optional Dreamina CLI login")
    parser.add_argument("--tesseract", action="store_true", help="Check Tesseract CLI installation")
    args = parser.parse_args()
    if not any((args.gateway, args.native, args.dreamina, args.tesseract)):
        parser.error("select at least one check")
    results = []
    if args.gateway:
        results.append(check_environment(("STIMULIR_API_KEY",)))
    if args.native:
        results.append(check_environment(("HYBRIE_BASE_URL", "HYBRIE_BEARER_KEY", "HYBRIE_BUSINESS_PROFILE_ID", "HYBRIE_POOL_ID")))
    if args.dreamina:
        results.append(check_dreamina())
    if args.tesseract:
        results.append(check_tesseract())
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
