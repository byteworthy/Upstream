"""Webhook signature utilities."""
from typing import Union, Dict, Any
import hashlib
import hmac
import json


def generate_signature(
    payload: Union[Dict[str, Any], str, bytes], secret: Union[str, bytes]
) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def verify_signature(
    payload: Union[Dict[str, Any], str, bytes],
    secret: Union[str, bytes],
    signature: str,
) -> bool:
    """Verify HMAC-SHA256 signature for webhook payload."""
    expected_signature = generate_signature(payload, secret)
    return hmac.compare_digest(expected_signature, signature)
