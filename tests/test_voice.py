import json

from backend.audit import AuditLog
from backend.store import CustomerStore
from backend.tools import Tools
from backend.voice import CallBridge, session_update, system_prompt, twiml_connect


def make_bridge(tmp_path, customer_id="cust_006"):
    tools = Tools(CustomerStore(), AuditLog(tmp_path / "a.jsonl"))
    return CallBridge(tools, customer_id), tools


def test_prompt_is_scenario_agnostic_once_customer_substituted():
    text = system_prompt("cust_001")
    assert "{{customer_id}}" not in text
    assert "cust_001" in text


def test_session_declares_mulaw_both_directions_and_three_tools():
    update = session_update("cust_001")["session"]
    assert update["audio"]["input"]["format"]["type"] == "audio/pcmu"
    assert update["audio"]["output"]["format"]["type"] == "audio/pcmu"
    assert {t["name"] for t in update["tools"]} == {"check_payment_status", "retry_autopay_charge", "send_payment_link"}


def test_twiml_connects_stream_with_customer_parameter():
    xml = twiml_connect("wss://example.test/voice/media", "cust_003")
    assert '<Stream url="wss://example.test/voice/media">' in xml
    assert 'name="customer_id" value="cust_003"' in xml


def test_twilio_start_sets_stream_and_media_is_forwarded(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    assert bridge.from_twilio({"event": "start", "start": {"streamSid": "MZ1"}}) == []
    out = bridge.from_twilio({"event": "media", "media": {"payload": "AAA="}})
    assert out == [{"type": "input_audio_buffer.append", "audio": "AAA="}]


def test_agent_audio_goes_back_to_the_phone_stream(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    bridge.from_twilio({"event": "start", "start": {"streamSid": "MZ1"}})
    _, to_twilio = bridge.from_realtime({"type": "response.output_audio.delta", "delta": "BBB="})
    assert to_twilio == [{"event": "media", "streamSid": "MZ1", "media": {"payload": "BBB="}}]


def test_caller_barge_in_clears_queued_agent_audio(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    bridge.from_twilio({"event": "start", "start": {"streamSid": "MZ1"}})
    _, to_twilio = bridge.from_realtime({"type": "input_audio_buffer.speech_started"})
    assert to_twilio == [{"event": "clear", "streamSid": "MZ1"}]


def test_tool_call_runs_for_the_fixed_customer_and_returns_output(tmp_path):
    bridge, _ = make_bridge(tmp_path, customer_id="cust_006")
    to_realtime, _ = bridge.from_realtime({
        "type": "response.function_call_arguments.done", "name": "check_payment_status",
        "call_id": "c1", "arguments": json.dumps({"customer_id": "cust_999"}),
    })
    item = to_realtime[0]["item"]
    assert item["call_id"] == "c1"
    output = json.loads(item["output"])
    assert output["is_disputing"] is True  # the call's customer, not the one the model asked for
    assert to_realtime[1] == {"type": "response.create"}


def test_unknown_tool_returns_error_output_not_exception(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    to_realtime, _ = bridge.from_realtime({
        "type": "response.function_call_arguments.done", "name": "charge_card", "call_id": "c2", "arguments": "{}",
    })
    assert "error" in json.loads(to_realtime[0]["item"]["output"])


def test_opening_messages_set_session_then_speak(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    first, second = bridge.opening_messages()
    assert first["type"] == "session.update"
    assert second["type"] == "response.create"


def test_stream_start_from_server_path_records_stream_sid(tmp_path):
    # Regression: the server must record streamSid on start, or agent audio is dropped.
    bridge, _ = make_bridge(tmp_path)
    bridge.from_twilio({"event": "start", "start": {"streamSid": "MZ9"}})
    _, to_twilio = bridge.from_realtime({"type": "response.output_audio.delta", "delta": "CCC="})
    assert to_twilio and to_twilio[0]["streamSid"] == "MZ9"
