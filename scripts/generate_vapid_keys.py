"""Generate VAPID keys for Web Push notifications.

Usage:
    python scripts/generate_vapid_keys.py

Prints a public/private key pair to paste into .env:
    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...
    VAPID_SUBJECT=mailto:you@example.com
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()
    public_key = _b64url(
        vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
    )
    private_key = _b64url(
        vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    )
    print("VAPID_PUBLIC_KEY=" + public_key)
    print("VAPID_PRIVATE_KEY=" + private_key)
    print("# VAPID_SUBJECT=mailto:you@example.com (replace with your address)")


if __name__ == "__main__":
    main()
