"""Voice bridge: Twilio Media Streams <-> OpenAI Realtime API.

Twilio sends and receives 8 kHz G.711 mu-law audio, which Realtime accepts directly as audio/pcmu,
so no transcoding is needed. The same system prompt and the same three tools as the agent config
drive the conversation, and tool calls run against the local backend (see backend/tools.py).
"""

import base64
import json
from pathlib import Path

from backend.tools import Tools, ToolError

ROOT = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE = (ROOT / "agent" / "system_prompt.md").read_text()
REALTIME_MODEL = "gpt-realtime-mini"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
VOICE = "marin"
OPENING_LINE = "Greet the customer and say the opening line from the call: that this is a call about a payment that did not go through on their account, and ask whether now is a good time to talk."

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "check_payment_status",
        "description": "Returns the failed autopay charge details for a customer. Call this first on every call.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
    },
    {
        "type": "function",
        "name": "retry_autopay_charge",
        "description": "Retries the failed autopay charge for this customer.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
    },
    {
        "type": "function",
        "name": "send_payment_link",
        "description": "Sends a payment link to this customer.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
    },
    {
        "type": "function",
        "name": "escalate_to_human",
        "description": "Records a request for a human agent to take over. Use when the customer disputes the charge or the amount, or asks for a person.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string", "enum": ["customer_dispute", "amount_dispute", "customer_request"]}},
            "required": ["reason"],
        },
    },
]


def system_prompt(customer_id: str) -> str:
    return PROMPT_TEMPLATE.replace("{{customer_id}}", customer_id)


def twiml_connect(stream_url: str, customer_id: str, token: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="{stream_url}">'
        f'<Parameter name="customer_id" value="{customer_id}"/>'
        f'<Parameter name="token" value="{token}"/>'
        "</Stream></Connect></Response>"
    )


def session_update(customer_id: str) -> dict:
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": system_prompt(customer_id),
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "audio": {
                "input": {"format": {"type": "audio/pcmu"}, "turn_detection": {"type": "server_vad"}},
                "output": {"format": {"type": "audio/pcmu"}, "voice": VOICE},
            },
        },
    }


class CallBridge:
    """Routes audio and tool calls for one phone call. Pure logic: sockets are passed in by the server."""

    def __init__(self, tools: Tools, customer_id: str):
        self.tools = tools
        self.customer_id = customer_id
        self.stream_sid: str | None = None
        # The prompt requires the account check before anything else. Enforced here, per call.
        self.account_checked = False

    def opening_messages(self) -> list[dict]:
        return [session_update(self.customer_id), {"type": "response.create", "response": {"instructions": OPENING_LINE}}]

    def from_twilio(self, event: dict) -> list[dict]:
        """Map one Twilio Media Streams event to messages for OpenAI Realtime."""
        kind = event.get("event")
        if kind == "start":
            self.stream_sid = event["start"]["streamSid"]
            return []
        if kind == "media":
            return [{"type": "input_audio_buffer.append", "audio": event["media"]["payload"]}]
        return []

    def from_realtime(self, event: dict) -> tuple[list[dict], list[dict]]:
        """Map one OpenAI Realtime event. Returns (messages to Realtime, messages to Twilio)."""
        kind = event.get("type")
        to_realtime: list[dict] = []
        to_twilio: list[dict] = []

        if kind in ("response.output_audio.delta", "response.audio.delta") and self.stream_sid:
            to_twilio.append({"event": "media", "streamSid": self.stream_sid,
                              "media": {"payload": event["delta"]}})

        elif kind == "input_audio_buffer.speech_started" and self.stream_sid:
            # Caller started talking: stop any agent audio still queued on the phone line.
            to_twilio.append({"event": "clear", "streamSid": self.stream_sid})

        elif kind == "response.function_call_arguments.done":
            output = self.run_tool(event["name"], event.get("arguments", "{}"))
            to_realtime.append({"type": "conversation.item.create",
                                "item": {"type": "function_call_output", "call_id": event["call_id"], "output": output}})
            to_realtime.append({"type": "response.create"})

        elif kind == "error":
            to_twilio.append({"event": "error", "detail": event.get("error", {})})

        return to_realtime, to_twilio

    def run_tool(self, name: str, arguments: str) -> str:
        allowed = {t["name"] for t in TOOL_SCHEMAS}
        try:
            if name not in allowed:
                raise ToolError(f"unknown tool: {name}")
            # Escalation moves no money, so it is allowed before the account check.
            if name not in ("check_payment_status", "escalate_to_human") and not self.account_checked:
                raise ToolError("check_payment_status must be called before this action")
            args = json.loads(arguments or "{}")  # reject malformed arguments
            # The customer is fixed for this call. Ignore any other ID the model supplies.
            if name == "escalate_to_human":
                output = self.tools.escalate_to_human(self.customer_id, args.get("reason", ""))
            else:
                output = getattr(self.tools, name)(self.customer_id)
            if name == "check_payment_status":
                self.account_checked = True
            return json.dumps(output)
        except (ToolError, ValueError) as exc:
            return json.dumps({"error": str(exc)})
