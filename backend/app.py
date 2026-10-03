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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("redial")

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


# ---- Phone leg: Twilio Media Streams <-> OpenAI Realtime -------------------------------

import asyncio
import os
import time
from urllib.parse import parse_qsl

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import Response
import websockets

from backend.security import is_valid_twilio_request, stream_token, verify_stream_token
from backend.voice import REALTIME_URL, CallBridge, twiml_connect


@app.post("/voice/twiml")
async def voice_twiml(request: Request, customer_id: str) -> Response:
    # Only Twilio may start a call session. The signed URL is the public one Twilio requested.
    body = (await request.body()).decode()
    params = parse_qsl(body, keep_blank_values=True)
    public_url = f"{os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')}/voice/twiml"
    if request.url.query:
        public_url += f"?{request.url.query}"
    if not is_valid_twilio_request(public_url, params, request.headers.get("x-twilio-signature"),
                                   os.environ.get("TWILIO_AUTH_TOKEN")):
        return Response(status_code=403)
    if _tools.store.get(customer_id) is None:
        return Response(status_code=404)
    stream_url = f"wss://{request.url.netloc}/voice/media"
    if os.environ.get("PUBLIC_BASE_URL"):
        stream_url = os.environ["PUBLIC_BASE_URL"].rstrip("/").replace("https://", "wss://", 1) + "/voice/media"
    token = stream_token(customer_id, os.environ["TWILIO_AUTH_TOKEN"], int(time.time()))
    return Response(content=twiml_connect(stream_url, customer_id, token), media_type="application/xml")


@app.websocket("/voice/media")
async def voice_media(ws: WebSocket) -> None:
    await ws.accept()
    bridge = None
    # Refuse any stream that does not carry a valid, recent token from our TwiML. Checked before the
    # OpenAI session opens, so an unauthenticated client never reaches the model.
    # Twilio sends "connected" before "start"; skip anything before the start event.
    first = json.loads(await ws.receive_text())
    while first.get("event") == "connected":
        first = json.loads(await ws.receive_text())
    if first.get("event") != "start":
        await ws.close(code=1008)
        return
    params = first["start"].get("customParameters", {})
    if not verify_stream_token(params.get("customer_id", ""), params.get("token"),
                               os.environ.get("TWILIO_AUTH_TOKEN"), int(time.time())):
        log.warning("media stream rejected: invalid or expired stream token")
        await ws.close(code=1008)
        return
    log.info("media stream authorized for %s", params.get("customer_id"))
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
    async with websockets.connect(REALTIME_URL, additional_headers=headers) as realtime:
        try:
            async def handle_twilio_event(event):
                nonlocal bridge
                if event.get("event") == "start":
                    customer_id = event["start"]["customParameters"]["customer_id"]
                    bridge = CallBridge(_tools, customer_id)
                    bridge.from_twilio(event)  # records the streamSid needed to send audio back
                    for msg in bridge.opening_messages():
                        await realtime.send(json.dumps(msg))
                elif bridge is not None:
                    for msg in bridge.from_twilio(event):
                        await realtime.send(json.dumps(msg))

            async def twilio_to_realtime():
                await handle_twilio_event(first)
                async for raw in ws.iter_text():
                    await handle_twilio_event(json.loads(raw))

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
