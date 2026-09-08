"""Webhook signature helpers for external provider integrations."""

from __future__ import annotations

import hmac
from hashlib import sha256

SIGNATURE_PREFIX = "sha256="


def build_hmac_signature(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_hmac_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False

    expected_signature = build_hmac_signature(raw_body, secret)
    return hmac.compare_digest(signature, expected_signature)
