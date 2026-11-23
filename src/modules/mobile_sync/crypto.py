"""Cryptography helpers for the mobile agent.

The desktop generates an X25519 keypair once. The private key never
leaves the machine (Windows Credential Manager); the public key is shared
with the phone through the pairing QR code. Photos are encrypted on the
phone with a libsodium sealed box to this public key, so the relay only
ever stores ciphertext.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import platform
import socket
from typing import Optional, Tuple

from nacl.public import PrivateKey, PublicKey, SealedBox
from nacl.utils import random as nacl_random

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "taj-froid-mobile"
PRIVATE_KEY_USER = "x25519-private-key"
AGENT_TOKEN_USER = "relay-agent-token"
DEVICE_ID_USER = "device-id-seed"

# Magic bytes for a JPEG, used to validate decrypted payloads.
JPEG_MAGIC = b"\xff\xd8\xff"


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def generate_keypair() -> Tuple[bytes, bytes]:
    """Returns (private_key_raw, public_key_raw)."""
    private = PrivateKey.generate()
    return bytes(private), bytes(private.public_key)


def load_private_key() -> Optional[bytes]:
    try:
        import keyring
    except ImportError:  # pragma: no cover - declared dependency
        return None
    stored = keyring.get_password(KEYRING_SERVICE, PRIVATE_KEY_USER)
    if not stored:
        return None
    try:
        return _b64decode(stored)
    except Exception:  # noqa: BLE001
        logger.error("Stored mobile private key is not valid base64.")
        return None


def store_private_key(private_key_raw: bytes) -> None:
    import keyring
    keyring.set_password(KEYRING_SERVICE, PRIVATE_KEY_USER, _b64encode(private_key_raw))


def ensure_keypair() -> Tuple[bytes, bytes]:
    """Returns (private, public) raw bytes, generating + storing if missing."""
    private = load_private_key()
    if private is None:
        private, public = generate_keypair()
        store_private_key(private)
        logger.info("Generated a new mobile X25519 keypair.")
        return private, public
    priv = PrivateKey(private)
    return private, bytes(priv.public_key)


def public_key_b64() -> str:
    _, public = ensure_keypair()
    return _b64encode(public)


def decrypt_sealed_box(ciphertext: bytes) -> bytes:
    """Decrypts a sealed box produced by the phone. Raises on failure."""
    private = load_private_key()
    if private is None:
        raise RuntimeError("No mobile private key is stored on this machine.")
    box = SealedBox(PrivateKey(private))
    return box.decrypt(ciphertext)


def verify_jpeg_magic(payload: bytes) -> bool:
    return payload.startswith(JPEG_MAGIC)


def sha256_bytes(payload: bytes) -> str:
    import hashlib
    return hashlib.sha256(payload).hexdigest()


def store_agent_token(token: str) -> None:
    import keyring
    keyring.set_password(KEYRING_SERVICE, AGENT_TOKEN_USER, token)


def load_agent_token() -> Optional[str]:
    try:
        import keyring
    except ImportError:  # pragma: no cover
        return None
    return keyring.get_password(KEYRING_SERVICE, AGENT_TOKEN_USER)


def delete_agent_token() -> None:
    try:
        import keyring
    except ImportError:  # pragma: no cover
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, AGENT_TOKEN_USER)
    except Exception:  # noqa: BLE001
        pass


def random_token(nbytes: int = 32) -> str:
    return _b64encode(nacl_random(nbytes))


def compute_device_id() -> str:
    """Deterministic device fingerprint (SHA-256 of machine + user + app).

    No stored seed needed — the fingerprint is reproducible on the same
    machine/user, so re-bootstrap always recognises the same device.
    """
    parts = [
        platform.node(),           # machine name
        os.getlogin() if hasattr(os, "getlogin") else os.environ.get("USERNAME", ""),
        socket.gethostname(),
        "tajfroid-mobile-agent",
    ]
    try:
        parts.append(platform.machine())
        parts.append(platform.processor())
    except Exception:  # noqa: BLE001
        pass
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()