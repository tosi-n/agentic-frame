#!/usr/bin/env python3
"""Generate one Stimulir image for each bounded JSON request."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from urllib import error, request

ALLOWED = {"prompt", "model", "size", "quality"}
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def load_requests(folder: Path) -> list[tuple[Path, dict[str, str]]]:
    files = sorted(folder.glob("*.json"))
    if not files:
        raise ValueError("request directory has no JSON files")
    result = []
    for path in files:
        body = json.loads(path.read_text())
        if not isinstance(body, dict) or set(body) - ALLOWED:
            raise ValueError(f"{path.name}: unsupported request fields")
        if not isinstance(body.get("prompt"), str) or not body["prompt"].strip():
            raise ValueError(f"{path.name}: prompt is required")
        if len(body["prompt"]) > 32000:
            raise ValueError(f"{path.name}: prompt exceeds gateway limit")
        for key in ("model", "size", "quality"):
            if key in body and (not isinstance(body[key], str) or not body[key]):
                raise ValueError(f"{path.name}: invalid {key}")
        body.setdefault("model", os.getenv("STIMULIR_IMAGE_MODEL", "gpt-image-2"))
        result.append((path, body))
    return result


def generate(body: dict[str, str]) -> tuple[bytes, str]:
    key = os.getenv("STIMULIR_API_KEY", "").strip()
    if not key:
        raise ValueError("STIMULIR_API_KEY is required")
    base = os.getenv("STIMULIR_API_BASE", "https://api.stimulir.com").rstrip("/")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    project = os.getenv("STIMULIR_PROJECT_ID", "").strip()
    if project:
        headers["X-Project-Id"] = project
    payload = json.dumps(body).encode()
    call = request.Request(base + "/api/v1/inference/images/generations", data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(call, timeout=240) as response:
            result = json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f"Stimulir image request failed: HTTP {exc.code}") from exc
    try:
        item = result["data"][0]
        mime = item["mime_type"]
        encoded = item["b64_json"]
        if mime not in EXTENSIONS:
            raise ValueError("unsupported image type")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("image exceeds gateway limit")
        return raw, mime
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Stimulir returned no usable image") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    requests = load_requests(args.request_dir)
    for path, body in requests:
        print(f"{path.name}: model={body['model']} prompt_chars={len(body['prompt'])}")
    if args.dry_run:
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, body in requests:
        if any((args.output_dir / (path.stem + ext)).exists() for ext in EXTENSIONS.values()):
            print(f"{path.name}: existing output, skipped")
            continue
        raw, mime = generate(body)
        target = args.output_dir / (path.stem + EXTENSIONS[mime])
        target.write_bytes(raw)
        print(f"{path.name}: wrote {target}")


if __name__ == "__main__":
    main()
