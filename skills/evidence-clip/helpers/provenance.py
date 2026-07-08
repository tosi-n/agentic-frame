#!/usr/bin/env python3
"""Build/append a chain-of-custody sidecar JSON for an evidence clip.

This helper NEVER writes itself into extract_range.py, deid_transcript.py, or
deid_media.py -- those helpers stay dumb, on purpose. The agent explicitly
calls provenance.py after each step (capture -> extract -> deid) so the
chain-of-custody record is an explicit, auditable action rather than an
implicit side effect buried inside a media-processing helper.

No clock is read inside this file. --at is a REQUIRED argument the caller
supplies (an ISO 8601 timestamp) -- never datetime.utcnow() / Date.now() here.
The only "time-like" values this helper computes itself are sha256 digests,
which are pure functions of file bytes, not of wall-clock time, so they don't
violate the repo's no-clocks-in-helpers rule.
"""
import argparse
import hashlib
import json
import os


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sidecar", help="path to the <clip>.provenance.json sidecar")
    parser.add_argument("--op", required=True, help="operation name, e.g. extract, deid_transcript")
    parser.add_argument("--tool", required=True, help="tool/helper name that performed the op")
    parser.add_argument(
        "--at", required=True,
        help="ISO 8601 timestamp supplied by the caller (never generated in this helper)",
    )
    parser.add_argument("--input", required=True, help="input file for this operation")
    parser.add_argument("--output", default=None, help="output file for this operation, if any")
    parser.add_argument("--params", default=None, help="JSON string of extra params for this op")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        raise SystemExit(f"provenance.py: --input file not found: {args.input}")

    input_sha256 = sha256_of_file(args.input)
    output_sha256 = sha256_of_file(args.output) if args.output else None

    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            raise SystemExit(f"provenance.py: --params is not valid JSON: {e}")
    else:
        params = {}

    if os.path.exists(args.sidecar):
        with open(args.sidecar, "r") as f:
            sidecar = json.load(f)
    else:
        sidecar = {"source_sha256": input_sha256, "chain": []}

    sidecar["chain"].append({
        "op": args.op,
        "tool": args.tool,
        "at": args.at,
        "params": params,
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
    })

    with open(args.sidecar, "w") as f:
        json.dump(sidecar, f, indent=2)

    print(args.sidecar)


if __name__ == "__main__":
    main()
