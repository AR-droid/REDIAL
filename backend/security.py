"""Twilio request signature check (X-Twilio-Signature).

Twilio signs each webhook request as base64(HMAC-SHA1(auth_token, url + sorted POST params)).
See https://www.twilio.com/docs/usage/webhooks/webhooks-security. Fails closed: a missing token
or signature means the request is rejected.
"""

import base64
import hashlib
import hmac


def twilio_signature(url: str, params: list[tuple[str, str]], auth_token: str) -> str:
    payload = url
    for key, value in sorted(params):
        payload += key + value
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def is_valid_twilio_request(url: str, params: list[tuple[str, str]], signature: str | None, auth_token: str | None) -> bool:
    if not signature or not auth_token:
        return False
    return hmac.compare_digest(twilio_signature(url, params, auth_token), signature)


STREAM_TOKEN_MAX_AGE_SECONDS = 600


def stream_token(customer_id: str, auth_token: str, issued_at: int) -> str:
    """Per-call token put in the TwiML stream parameters. Binds the call to its customer and issue time."""
    message = f"{customer_id}:{issued_at}"
    mac = hmac.new(auth_token.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{issued_at}.{mac}"


def verify_stream_token(customer_id: str, token: str | None, auth_token: str | None, now: int) -> bool:
    if not token or not auth_token or "." not in token:
        return False
    issued_at_text, _ = token.split(".", 1)
    if not issued_at_text.isdigit():
        return False
    issued_at = int(issued_at_text)
    if not 0 <= now - issued_at <= STREAM_TOKEN_MAX_AGE_SECONDS:
        return False
    return hmac.compare_digest(stream_token(customer_id, auth_token, issued_at), token)
