from __future__ import annotations

import json


print(
    json.dumps(
        {
            "status": "failed",
            "text": None,
            "extractor_name": "fixture-ocr",
            "extractor_version": "1.0.0",
            "confidence": None,
            "caveat": "fixed unavailable extractor fixture",
            "claim_status": "unknown",
            "audit_status": "needs_reconciliation",
            "reviewer": None,
            "error": "fixed Vision unavailable",
        },
        sort_keys=True,
    )
)
