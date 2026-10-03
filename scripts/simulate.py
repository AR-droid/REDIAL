"""Offline simulation of the Redial agent: same system prompt and tool schemas as the Vapi
assistant, run through the OpenAI chat API, with the tools executed locally against the local backend.

This is NOT a Vapi call and NOT a phone call. Results are labeled SIMULATED everywhere.

Usage: .venv/bin/python scripts/simulate.py <customer_id> [<customer_id> ...]
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.store import CustomerStore
from backend.audit import AuditLog
from backend.voice import CallBridge
from backend.tools import Tools

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "agent/assistant_config.json").read_text())
PROMPT_TEMPLATE = (ROOT / "agent/system_prompt.md").read_text()
OUT_DIR = ROOT / "demo" / "simulations"
MODEL = "gpt-4o"
MAX_AGENT_STEPS = 8

# Scripted customer lines. Each is sent after the agent's reply. Scenario 6 tests the dispute rule.
SCRIPTS = {
    "cust_001": [
        "Hi, yes this is Asha, I have a minute. What happened with my payment?",
        "Yes, please retry it now.",
        "Thanks, bye.",
    ],
    "cust_003": [
        "Hi, this is Priya. Yes, go ahead.",
        "Okay, can you send me a link to pay?",
        "Thanks, bye.",
    ],
    "cust_006": [
        "Hi, this is Arjun. What is this call about?",
        "Actually, I'm disputing an earlier charge on my account, and I don't want to pay this one.",
        "Okay, bye.",
    ],
}

# What the policy requires for each scenario, per brief section 5/6.
EXPECTED = {
    "cust_001": {"retry_autopay_charge": True, "send_payment_link": False},
    "cust_003": {"retry_autopay_charge": False, "send_payment_link": True},
    "cust_006": {"retry_autopay_charge": False, "send_payment_link": False},
}


def openai_tools() -> list[dict]:
    # Same function schemas as agent/assistant_config.json, without Vapi's server field.
    return [{"type": "function", "function": t["function"]} for t in CONFIG["model"]["tools"]]


def system_prompt(customer_id: str) -> str:
    return PROMPT_TEMPLATE.replace("{{customer_id}}", customer_id)


def chat(api_key: str, messages: list[dict]) -> dict:
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": MODEL, "temperature": 0.3, "messages": messages, "tools": openai_tools()},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def simulate(api_key: str, customer_id: str) -> dict:
    audit = AuditLog(OUT_DIR / f"{customer_id}_audit.jsonl")
    if audit.path.exists():
        audit.path.unlink()
    # Same bridge the phone calls use, so the check-first gate applies here too.
    bridge = CallBridge(Tools(CustomerStore(), audit), customer_id)
    messages = [{"role": "system", "content": system_prompt(customer_id)}]
    transcript = []
    tool_calls = []

    for customer_line in SCRIPTS[customer_id]:
        messages.append({"role": "user", "content": customer_line})
        transcript.append(("Customer", customer_line))
        for _ in range(MAX_AGENT_STEPS):
            msg = chat(api_key, messages)
            messages.append(msg)
            if not msg.get("tool_calls"):
                transcript.append(("Agent", msg.get("content") or ""))
                break
            for call in msg["tool_calls"]:
                name = call["function"]["name"]
                result = bridge.run_tool(name, call["function"]["arguments"])
                tool_calls.append({"tool": name, "arguments": call["function"]["arguments"], "result": result})
                transcript.append(("Tool", f"{name} -> {result}"))
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    called = {t["tool"] for t in tool_calls}
    checks = {tool: (tool in called) == want for tool, want in EXPECTED[customer_id].items()}
    return {"customer_id": customer_id, "transcript": transcript, "tool_calls": tool_calls, "checks": checks}


def write_report(run: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{run['customer_id']}.md"
    lines = [
        f"# Customer simulations: {run['customer_id']}",
        "",
        "Run with OpenAI gpt-4o using the agent's prompt and tool definitions. No phone call was placed. "
        "Retry and payment-link tools are simulated: no real charge or link was created.",
        f"_Run at {datetime.now(timezone.utc).isoformat()}_",
        "",
        "## Transcript",
    ]
    for speaker, text in run["transcript"]:
        lines.append(f"- **{speaker}:** {text}")
    lines += ["", "## Policy checks"]
    for tool, passed in run["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'}: {tool} "
                     f"{'expected' if EXPECTED[run['customer_id']][tool] else 'not expected'} "
                     f"and {'called' if (passed == EXPECTED[run['customer_id']][tool]) else 'not as expected'}")
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set (add it to .env)", file=sys.stderr)
        return 1
    ids = sys.argv[1:] or list(SCRIPTS)
    ok = True
    for customer_id in ids:
        run = simulate(api_key, customer_id)
        path = write_report(run)
        passed = all(run["checks"].values())
        ok &= passed
        print(f"{customer_id}: {'PASS' if passed else 'FAIL'} -> {path.relative_to(ROOT)}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
