#!/usr/bin/env python3
"""Deterministic stand-in for the external tesseract binary boundary."""

from __future__ import annotations

import sys


if sys.argv[1:] == ["--version"]:
    print("tesseract 9.9.9-fixture")
    raise SystemExit(0)

if sys.argv[-1:] == ["tsv"]:
    print("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext")
    print("5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t96.0\tQualified")
    print("5\t1\t1\t1\t1\t2\t2\t0\t1\t1\t94.0\tcapacity")
    print("5\t1\t1\t1\t1\t3\t4\t0\t1\t1\t92.0\tis constrained")
    raise SystemExit(0)

print("unexpected fixture argv", file=sys.stderr)
raise SystemExit(64)
