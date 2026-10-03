"""FastAPI app: Vapi tool-call webhook for the three recovery tools.

Vapi contract (per CLAUDE.md): always respond HTTP 200 with
{"results": [{"toolCallId": ..., "result": "<flat string>"}]}, or "error" instead of "result".
"""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.audit import AuditLog
from backend.store import CustomerStore
from backend.tools import Tools, ToolError

log = logging.getLogger("redial")

TOOL_NAMES = {"check_payment_status", "retry_autopay_charge", "send_payment_link"}

app = FastAPI(title="Redial backend")
_tools = Tools(CustomerStore(), AuditLog())


def _parse_arguments(raw) -> dict:
    # Vapi may send arguments as a dict or as a JSON string, depending on the model/config.
    if isinstance(raw, str):
        return json.loads(raw) if raw.strip() else {}
    return raw or {}


def _run_tool(name: str, arguments: dict) -> dict:
    if name not in TOOL_NAMES:
        raise ToolError(f"unknown tool: {name}")
    customer_id = arguments.get("customer_id")
    if not customer_id:
        raise ToolError("customer_id is required")
    return getattr(_tools, name)(customer_id)


@app.post("/tools")
async def tool_webhook(request: Request) -> JSONResponse:
    body = await request.json()
    message = body.get("message", {})
    if message.get("type") != "tool-calls":
        return JSONResponse({})

    results = []
    for call in message.get("toolCallList", []):
        call_id = call.get("id")
        fn = call.get("function", {})
        try:
            output = _run_tool(fn.get("name", ""), _parse_arguments(fn.get("arguments")))
            results.append({"toolCallId": call_id, "result": json.dumps(output)})
        except (ToolError, ValueError) as exc:
            # Tool-level failures still return HTTP 200 so Vapi can read the error and continue.
            results.append({"toolCallId": call_id, "error": str(exc)})
        except Exception:
            log.exception("unexpected error in tool %s", fn.get("name"))
            results.append({"toolCallId": call_id, "error": "internal tool error"})
    return JSONResponse({"results": results})


# ---- Phone leg: Twilio Media Streams <-> OpenAI Realtime -------------------------------

import asyncio
import os

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import Response
import websockets

from backend.voice import REALTIME_URL, CallBridge, twiml_connect


@app.post("/voice/twiml")
async def voice_twiml(request: Request, customer_id: str) -> Response:
    if _tools.store.get(customer_id) is None:
        return Response(status_code=404)
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    stream_url = f"wss://{host}/voice/media"
    return Response(content=twiml_connect(stream_url, customer_id), media_type="application/xml")


@app.websocket("/voice/media")
async def voice_media(ws: WebSocket) -> None:
    await ws.accept()
    bridge = None
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
    async with websockets.connect(REALTIME_URL, additional_headers=headers) as realtime:
        try:
            async def twilio_to_realtime():
                nonlocal bridge
                async for raw in ws.iter_text():
                    event = json.loads(raw)
                    if event.get("event") == "start":
                        customer_id = event["start"]["customParameters"]["customer_id"]
                        bridge = CallBridge(_tools, customer_id)
                        bridge.from_twilio(event)  # records the streamSid needed to send audio back
                        for msg in bridge.opening_messages():
                            await realtime.send(json.dumps(msg))
                    elif bridge is not None:
                        for msg in bridge.from_twilio(event):
                            await realtime.send(json.dumps(msg))

            async def realtime_to_twilio():
                async for raw in realtime:
                    event = json.loads(raw)
                    if bridge is None:
                        continue
                    to_realtime, to_twilio = bridge.from_realtime(event)
                    for msg in to_realtime:
                        await realtime.send(json.dumps(msg))
                    for msg in to_twilio:
                        await ws.send_text(json.dumps(msg))

            tasks = [asyncio.create_task(twilio_to_realtime()), asyncio.create_task(realtime_to_twilio())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
        except WebSocketDisconnect:
            pass
