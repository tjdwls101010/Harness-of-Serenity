from __future__ import annotations

import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
args = parser.parse_args()

if not open(args.input, "rb").read().endswith(b"chart"):
    result = {
        "status": "complete",
        "text": "Allocation is constrained by qualified capacity.",
        "extractor_name": "fixture-ocr",
        "extractor_version": "1.0.0",
        "confidence": 0.98,
        "caveat": "deterministic text-bearing fixture",
        "claim_status": "established",
        "audit_status": "approved",
        "reviewer": "fixture-reviewer",
    }
else:
    result = {
        "status": "complete",
        "text": "",
        "extractor_name": "fixture-ocr",
        "extractor_version": "1.0.0",
        "confidence": 0.71,
        "caveat": "chart layout cannot establish the claim without visual review",
        "claim_status": "insufficient",
        "audit_status": "approved",
        "reviewer": "fixture-reviewer",
    }

print(json.dumps(result, sort_keys=True))
