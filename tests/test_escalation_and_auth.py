import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import backend.app as app_module
from backend.audit import AuditLog
from backend.security import stream_token, verify_stream_token
from backend.store import CustomerStore
from backend.tools import Tools, ToolError
from backend.voice import CallBridge


def make_bridge(tmp_path, customer_id="cust_006"):
    return CallBridge(Tools(CustomerStore(), AuditLog(tmp_path / "a.jsonl")), customer_id)


def call(bridge, name, args="{}"):
    to_realtime, _ = bridge.from_realtime({"type": "response.function_call_arguments.done",
                                           "name": name, "call_id": "x", "arguments": args})
    return json.loads(to_realtime[0]["item"]["output"])


def test_escalation_is_audited_with_reason(tmp_path):
    tools = Tools(CustomerStore(), AuditLog(tmp_path / "a.jsonl"))
    result = tools.escalate_to_human("cust_006", "customer_dispute")
    assert result == {"status": "escalation_requested", "reason": "customer_dispute",
                      "message": "Request recorded for a human agent. No transfer was made."}
    entry = json.loads((tmp_path / "a.jsonl").read_text())
    assert entry["tool"] == "escalate_to_human" and entry["mocked"] is True and entry["reason"] == "customer_dispute"


def test_escalation_rejects_unknown_reason(tmp_path):
    tools = Tools(CustomerStore(), AuditLog(tmp_path / "a.jsonl"))
    with pytest.raises(ToolError):
        tools.escalate_to_human("cust_006", "because")


def test_escalation_allowed_before_account_check(tmp_path):
    assert "error" not in call(make_bridge(tmp_path), "escalate_to_human", '{"reason": "customer_request"}')


def test_escalation_does_not_unlock_payment_actions(tmp_path):
    bridge = make_bridge(tmp_path)
    call(bridge, "escalate_to_human", '{"reason": "customer_request"}')
    assert "error" in call(bridge, "send_payment_link")


def test_stream_token_round_trip():
    token = stream_token("cust_001", "tok", 1_000)
    assert verify_stream_token("cust_001", token, "tok", 1_000 + 60)


def test_stream_token_rejects_other_customer_wrong_key_and_expiry():
    token = stream_token("cust_001", "tok", 1_000)
    assert not verify_stream_token("cust_002", token, "tok", 1_010)
    assert not verify_stream_token("cust_001", token, "other", 1_010)
    assert not verify_stream_token("cust_001", token, "tok", 1_000 + 3_600)
    assert not verify_stream_token("cust_001", None, "tok", 1_010)


def test_media_socket_refuses_start_without_token(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    client = TestClient(app_module.app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/voice/media") as ws:
            ws.send_text(json.dumps({"event": "start", "start": {
                "streamSid": "MZ1", "customParameters": {"customer_id": "cust_001", "token": "bogus"}}}))
            ws.receive_text()


def test_media_socket_skips_connected_event_before_start(monkeypatch):
    # Regression: Twilio sends "connected" before "start". The token check must run on the start event.
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    seen = []

    def fake_verify(customer_id, token, auth_token, now):
        seen.append(customer_id)
        return True

    monkeypatch.setattr(app_module, "verify_stream_token", fake_verify)
    client = TestClient(app_module.app)
    try:
        # The OpenAI session is not available offline, so the call stops after authorization.
        with client.websocket_connect("/voice/media") as ws:
            ws.send_text(json.dumps({"event": "connected", "protocol": "Call"}))
            ws.send_text(json.dumps({"event": "start", "start": {"streamSid": "MZ2", "customParameters": {
                "customer_id": "cust_001", "token": "t"}}}))
            ws.receive_text()
    except Exception:
        pass
    assert seen == ["cust_001"]
