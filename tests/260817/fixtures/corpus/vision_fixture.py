from __future__ import annotations

import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.parse_args()

print(
    json.dumps(
        {
            "status": "complete",
            "labels": ["chart", "diagram", "screenshot"],
            "summary": "The image is chart-like and requires claim-level visual review.",
            "supported_claims": [
                {
                    "claim": "The image contains a chart-like visual.",
                    "evidence": "The deterministic fixture labels it chart, diagram, and screenshot.",
                    "caveat": "This fixture does not validate a financial claim.",
                }
            ],
            "model_name": "fixture-vision",
            "model_version": "2.0.0",
            "prompt_template_version": "chart-review-v1",
            "confidence": 0.91,
            "caveat": "deterministic visual review fixture",
            "audit_status": "approved",
            "reviewer": "fixture-reviewer",
        },
        sort_keys=True,
    )
)
