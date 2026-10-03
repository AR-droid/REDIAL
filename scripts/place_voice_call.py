"""Place one outbound Twilio call for a scenario. Twilio streams the call audio to our backend,
which runs the OpenAI Realtime agent (backend/voice.py).

Default is a dry run that prints the request. A real call requires --confirm.
The approved destination is hardcoded and checked here, independent of Twilio's verified-number rule.

Usage:
  .venv/bin/python scripts/place_voice_call.py <scenario 1-10>             # dry run
  .venv/bin/python scripts/place_voice_call.py <scenario 1-10> --confirm   # places a real call

Requires in .env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, PUBLIC_BASE_URL, OPENAI_API_KEY.
The backend must be running (make mock-server) and PUBLIC_BASE_URL must point at its tunnel.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parent.parent
APPROVED_NUMBER = "+919790339415"  # the one number the user approved for test calls


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def build_call(env: dict, scenario: int) -> dict:
    if not 1 <= scenario <= 10:
        raise SystemExit(f"scenario must be 1-10, got {scenario}")
    if env.get("APPROVED_CALL_NUMBER") != APPROVED_NUMBER:
        raise SystemExit("APPROVED_CALL_NUMBER in .env does not match the approved number")
    if env.get("TWILIO_FROM_NUMBER") == APPROVED_NUMBER:
        raise SystemExit("TWILIO_FROM_NUMBER and the approved number are the same; check the Twilio number")
    customer_id = f"cust_{scenario:03d}"
    query = urlencode({"customer_id": customer_id})
    return {
        "To": APPROVED_NUMBER,
        "From": env["TWILIO_FROM_NUMBER"],
        "Url": f"{env['PUBLIC_BASE_URL'].rstrip('/')}/voice/twiml?{query}",
        "customer_id": customer_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=int)
    parser.add_argument("--confirm", action="store_true", help="actually place the call")
    args = parser.parse_args()

    env = load_env()
    call = build_call(env, args.scenario)
    printable = {k: v for k, v in call.items() if k != "customer_id"}

    if not args.confirm:
        print("DRY RUN (no call placed). Twilio request that would be sent:")
        for key, value in printable.items():
            print(f"  {key}: {value}")
        return 0

    sid = env["TWILIO_ACCOUNT_SID"]
    r = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
        data=printable,
        auth=(sid, env["TWILIO_AUTH_TOKEN"]),
        timeout=60,
    )
    if r.status_code >= 300:
        print(f"Twilio returned {r.status_code}: {r.text[:500]}", file=sys.stderr)
        return 1
    body = r.json()
    print(f"placed scenario {args.scenario} ({call['customer_id']}), call sid {body.get('sid')}, status {body.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
