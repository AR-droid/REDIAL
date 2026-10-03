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
