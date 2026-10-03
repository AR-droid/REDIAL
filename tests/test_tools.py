import json

import pytest
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.audit import AuditLog
from backend.store import CustomerStore
from backend.tools import PAYMENT_LINK_HOST, Tools, ToolError


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def tools(audit):
    return Tools(CustomerStore(), audit)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the webhook at a throwaway audit file so tests never write demo/audit.jsonl.
    monkeypatch.setattr(app_module, "_tools", Tools(CustomerStore(), AuditLog(tmp_path / "a.jsonl")))
    return TestClient(app_module.app)


def read_audit(audit):
    return [json.loads(line) for line in audit.path.read_text().splitlines()]


def test_check_payment_status_shape(tools):
    result = tools.check_payment_status("cust_002")
    assert set(result) == {"amount_due", "currency", "due_date", "failure_reason",
                           "autopay_status", "is_disputing", "retry_count"}
    assert result["retry_count"] == 1


def test_check_payment_status_unknown_customer(tools):
    with pytest.raises(ToolError):
        tools.check_payment_status("cust_999")


@pytest.mark.parametrize("customer_id,expected", [
    ("cust_001", "succeeded"),
    ("cust_002", "declined"),
    ("cust_005", "declined"),
])
def test_retry_is_deterministic_per_scenario(tools, customer_id, expected):
    assert tools.retry_autopay_charge(customer_id)["status"] == expected
    assert tools.retry_autopay_charge(customer_id)["status"] == expected


def test_send_payment_link_uses_example_domain(tools):
    result = tools.send_payment_link("cust_003")
    assert result["status"] == "sent"
    assert result["link"] == f"{PAYMENT_LINK_HOST}/cust_003"
    assert "example.com" in result["link"]


def test_every_tool_call_is_audit_logged_as_mocked(tools, audit):
    tools.check_payment_status("cust_001")
    tools.retry_autopay_charge("cust_001")
    tools.send_payment_link("cust_001")
    entries = read_audit(audit)
    assert [e["tool"] for e in entries] == ["check_payment_status", "retry_autopay_charge", "send_payment_link"]
    assert all(e["mocked"] is True for e in entries)


def test_webhook_returns_vapi_result_shape(client):
    body = {"message": {"type": "tool-calls", "toolCallList": [{
        "id": "call_1", "type": "function",
        "function": {"name": "check_payment_status", "arguments": {"customer_id": "cust_001"}},
    }]}}
    resp = client.post("/tools", json=body)
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["toolCallId"] == "call_1"
    assert isinstance(result["result"], str)
    assert json.loads(result["result"])["failure_reason"] == "insufficient_funds"


def test_webhook_accepts_string_arguments(client):
    body = {"message": {"type": "tool-calls", "toolCallList": [{
        "id": "call_2", "function": {"name": "send_payment_link", "arguments": '{"customer_id": "cust_003"}'},
    }]}}
    result = client.post("/tools", json=body).json()["results"][0]
    assert json.loads(result["result"])["status"] == "sent"


def test_webhook_tool_error_is_still_http_200(client):
    body = {"message": {"type": "tool-calls", "toolCallList": [{
        "id": "call_3", "function": {"name": "check_payment_status", "arguments": {"customer_id": "nope"}},
    }]}}
    resp = client.post("/tools", json=body)
    assert resp.status_code == 200
    assert "error" in resp.json()["results"][0]
    assert "result" not in resp.json()["results"][0]


def test_webhook_unknown_tool_is_http_200_error(client):
    body = {"message": {"type": "tool-calls", "toolCallList": [{
        "id": "call_4", "function": {"name": "charge_card", "arguments": {"customer_id": "cust_001"}},
    }]}}
    resp = client.post("/tools", json=body)
    assert resp.status_code == 200
    assert "error" in resp.json()["results"][0]


def test_webhook_ignores_non_tool_messages(client):
    resp = client.post("/tools", json={"message": {"type": "status-update"}})
    assert resp.status_code == 200
    assert resp.json() == {}
