"""Append-only JSONL audit log. Every tool call is written here with mocked: true."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_AUDIT_PATH = Path(__file__).resolve().parent.parent / "demo" / "audit.jsonl"


class AuditLog:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or os.environ.get("REDIAL_AUDIT_PATH", DEFAULT_AUDIT_PATH))

    def record(self, tool: str, customer_id: str | None, result: dict, **extra) -> dict:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "customer_id": customer_id,
            "mocked": True,
            "result": result,
            **extra,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry
