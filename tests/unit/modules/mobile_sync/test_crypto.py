import base64
from src.modules.mobile_sync.crypto import (
    generate_keypair, ensure_keypair, decrypt_sealed_box,
    verify_jpeg_magic, sha256_bytes, store_agent_token, load_agent_token,
)
from nacl.public import SealedBox, PublicKey


def test_roundtrip_sealed_box():
    priv, pub = generate_keypair()
    # Simulate phone sealing a JPEG payload to the desktop public key.
    box = SealedBox(PublicKey(pub))
    payload = b"\xff\xd8\xff" + b"hello"
    ciphertext = box.encrypt(payload)
    # Store private key in keyring is not available in tests; decrypt via direct.
    from nacl.public import PrivateKey
    pt = SealedBox(PrivateKey(priv)).decrypt(ciphertext)
    assert pt == payload
    assert verify_jpeg_magic(pt)
    assert len(sha256_bytes(pt)) == 64


def test_ensure_keypair_returns_32_byte_keys():
    priv, pub = ensure_keypair()
    assert len(priv) == 32
    assert len(pub) == 32