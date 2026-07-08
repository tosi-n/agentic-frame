#!/usr/bin/env python3
"""Redact PII from a transcript via the Stimulir hosted de-identification endpoint.

This is a REAL network call to a real hosted endpoint -- it is not a stub.
POST {STIMULIR_API_URL}/api/v1/privacy/deidentify with body {"text": ...} and
Authorization: Bearer {STIMULIR_API_KEY}. Confirmed exactly against the HybrIE
Rust source (hybrie-server/src/api/privacy.rs DeidentifyResponse struct):

    {"text": <redacted text>, "redactions": <int>, "entity_types": [<str>, ...]}

HARD LIMITATION -- read before wiring this into any audio workflow: this
endpoint NEVER returns match offsets or original matched values. It can only
produce a redacted TEXT artifact. There is no timing information in the
response, so this helper cannot drive a downstream audio bleep/mute step by
itself. If the agent needs to mute the corresponding audio spans in the
source clip, it must diff the original transcript text against this helper's
redacted output to locate what changed, then map that onto Whisper
word-level timestamps (if available) to get seconds -- and pass the result
to deid_media.py's --mute-ranges. This helper does none of that mapping.
"""
import argparse
import json
import os
import sys

import httpx

DEFAULT_API_URL = "https://api.stimulir.com"


def extract_text(raw: str) -> str:
    """Pull plain text out of a .txt file or a JSON transcript (Whisper
    verbose_json shape with a top-level "text" field, or a "segments" list of
    {"text": ...} objects). Falls back to treating the whole file as plain
    text if it isn't parseable JSON or doesn't match either shape.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(parsed, dict):
        if "text" in parsed and isinstance(parsed["text"], str):
            return parsed["text"]
        if "segments" in parsed and isinstance(parsed["segments"], list):
            return " ".join(
                seg.get("text", "") for seg in parsed["segments"] if isinstance(seg, dict)
            )

    # Valid JSON but not a recognized transcript shape (e.g. a bare string,
    # number, list, or dict without "text"/"segments") -- treat as plain text.
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="plain .txt transcript or JSON transcript file")
    parser.add_argument("--out", required=True, help="output path for the redacted text")
    args = parser.parse_args()

    api_url = os.environ.get("STIMULIR_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY")
    if not api_key:
        raise SystemExit(
            "deid_transcript.py: STIMULIR_API_KEY is not set. This helper makes a "
            "real call to the Stimulir de-identification endpoint and needs a real "
            "hyb_* key -- see install.md for where to get one. Refusing to proceed."
        )

    with open(args.input, "r") as f:
        raw = f.read()
    text = extract_text(raw)

    url = f"{api_url}/api/v1/privacy/deidentify"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"text": text},
            timeout=30.0,
        )
    except httpx.RequestError as e:
        raise SystemExit(f"deid_transcript.py: request to {url} failed: {e}")

    if response.status_code != 200:
        body_snippet = response.text[:500] if response.text else ""
        raise SystemExit(
            f"deid_transcript.py: {url} returned HTTP {response.status_code}: {body_snippet}"
        )

    data = response.json()
    redacted_text = data["text"]
    redactions = data.get("redactions", 0)
    entity_types = data.get("entity_types", [])

    with open(args.out, "w") as f:
        f.write(redacted_text)

    sys.stderr.write(f"redacted {redactions} span(s), entity types: {entity_types}\n")


if __name__ == "__main__":
    main()
