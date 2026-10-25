#!/usr/bin/env python3
"""
log_edit.py
Appends a manual edit record to runs.jsonl as required by MASTER_PLAN.md rule #2:
{"timestamp": "...", "type": "manual_edit", "reason": "<reason>"}
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path


RUNS_LOG_PATH = Path("runs.jsonl")


def log_manual_edit(reason: str):
    if not reason:
        print("Usage: python3 log_edit.py \"<reason>\"", file=sys.stderr)
        sys.exit(1)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "manual_edit",
        "reason": reason.strip(),
    }

    with open(RUNS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Logged manual edit to {RUNS_LOG_PATH}: {reason}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 log_edit.py \"<reason>\"", file=sys.stderr)
        sys.exit(1)
    log_manual_edit(" ".join(sys.argv[1:]))
