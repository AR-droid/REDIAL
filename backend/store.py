"""Loads fictional customer records from data/customers.json (single source of truth)."""

import json
from pathlib import Path

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "customers.json"


class CustomerStore:
    def __init__(self, data_path: Path = DEFAULT_DATA_PATH):
        records = json.loads(Path(data_path).read_text())
        self._by_id = {record["customer_id"]: record for record in records}

    def get(self, customer_id: str) -> dict | None:
        record = self._by_id.get(customer_id)
        return dict(record) if record is not None else None

    def all_ids(self) -> list[str]:
        return list(self._by_id)
