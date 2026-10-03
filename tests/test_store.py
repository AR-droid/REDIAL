import json

from backend.store import DEFAULT_DATA_PATH, CustomerStore


def test_loads_all_ten_records():
    store = CustomerStore()
    assert len(store.all_ids()) == 10


def test_lookup_by_id_returns_record():
    record = CustomerStore().get("cust_006")
    assert record["name"] == "Arjun Rao"
    assert record["is_disputing"] is True


def test_missing_id_returns_none():
    assert CustomerStore().get("cust_999") is None


def test_get_returns_copy_not_internal_state():
    store = CustomerStore()
    store.get("cust_001")["amount_due"] = 0
    assert store.get("cust_001")["amount_due"] == 1249.00


def test_every_record_has_required_fields():
    required = {"customer_id", "name", "amount_due", "currency", "due_date", "failure_reason",
                "card_last4", "autopay_status", "is_disputing", "retry_count", "retry_result"}
    records = json.loads(DEFAULT_DATA_PATH.read_text())
    for record in records:
        assert required <= record.keys(), record["customer_id"]
