"""AES-256-GCM for tokens at rest. Key: 32 bytes, base64 in TOKEN_ENCRYPTION_KEY."""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenCipher:
    def __init__(self, b64_key: str):
        key = base64.b64decode(b64_key)
        if len(key) != 32:
            raise ValueError("TOKEN_ENCRYPTION_KEY must decode to 32 bytes")
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: str, aad: str) -> str:
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, plaintext.encode(), aad.encode())
        return base64.b64encode(nonce + ct).decode()

    def decrypt(self, blob: str, aad: str) -> str:
        raw = base64.b64decode(blob)
        return self._aes.decrypt(raw[:12], raw[12:], aad.encode()).decode()


def redact(value: str | None) -> str:
    if not value:
        return ""
    return value[:4] + "…" if len(value) > 8 else "…"
