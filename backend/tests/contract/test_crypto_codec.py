"""Synthetic round-trip tests for protocol crypto and codec.

Run clean with zero fixtures — no pcap captures required. These tests
verify internal correctness (encode then decode reproduces the original)
and that the TNBU flags are set correctly for each cipher mode.
"""

from __future__ import annotations

import os

import pytest

_KEY = bytes.fromhex("ba86f2bbe107c7c57eb5f2690775c712")
_MAC = bytes.fromhex("020000abcdef")


# ── crypto primitives ────────────────────────────────────────────────


def test_cbc_round_trip() -> None:
    from engine.protocol.crypto import decrypt_cbc, encrypt_cbc

    iv = os.urandom(16)
    plaintext = b"UniFi CBC round-trip test payload"
    assert decrypt_cbc(_KEY, iv, encrypt_cbc(_KEY, iv, plaintext)) == plaintext


def test_cbc_different_ivs_produce_different_ciphertext() -> None:
    from engine.protocol.crypto import encrypt_cbc

    plaintext = b"same plaintext"
    iv1, iv2 = os.urandom(16), os.urandom(16)
    assert encrypt_cbc(_KEY, iv1, plaintext) != encrypt_cbc(_KEY, iv2, plaintext)


def test_gcm_round_trip() -> None:
    from engine.protocol.crypto import decrypt_gcm, encrypt_gcm

    nonce = os.urandom(12)
    plaintext = b"UniFi GCM round-trip test payload"
    assert decrypt_gcm(_KEY, nonce, encrypt_gcm(_KEY, nonce, plaintext)) == plaintext


def test_gcm_tag_is_appended() -> None:
    from engine.protocol.crypto import encrypt_gcm

    plaintext = b"test"
    ct = encrypt_gcm(_KEY, os.urandom(12), plaintext)
    # AESGCM appends a 16-byte tag, so ciphertext is always longer than plaintext.
    assert len(ct) == len(plaintext) + 16


def test_gcm_wrong_key_raises() -> None:
    from cryptography.exceptions import InvalidTag

    from engine.protocol.crypto import decrypt_gcm, encrypt_gcm

    nonce = os.urandom(12)
    ct = encrypt_gcm(_KEY, nonce, b"secret")
    wrong_key = os.urandom(16)
    with pytest.raises(InvalidTag):
        decrypt_gcm(wrong_key, nonce, ct)


# ── TNBU framing ─────────────────────────────────────────────────────


def test_tnbu_encode_decode_round_trip() -> None:
    from engine.protocol.tnbu import FLAG_ENCRYPTED, InformFrame

    iv = os.urandom(16)
    payload = b"ciphertext_blob"
    frame = InformFrame(mac=_MAC, flags=FLAG_ENCRYPTED, iv_or_nonce=iv, payload=payload)
    recovered = InformFrame.decode(frame.encode())
    assert recovered.mac == _MAC
    assert recovered.flags == FLAG_ENCRYPTED
    assert recovered.iv_or_nonce == iv
    assert recovered.payload == payload


def test_tnbu_starts_with_magic() -> None:
    from engine.protocol.tnbu import InformFrame

    frame = InformFrame(mac=_MAC, flags=0, iv_or_nonce=b"", payload=b"")
    assert frame.encode().startswith(b"TNBU")


def test_tnbu_decode_bad_magic_raises() -> None:
    from engine.protocol.tnbu import InformFrame

    raw = b"BADM" + b"\x00" * 20
    with pytest.raises(ValueError, match="magic"):
        InformFrame.decode(raw)


def test_tnbu_decode_truncated_raises() -> None:
    from engine.protocol.tnbu import InformFrame

    with pytest.raises(ValueError):
        InformFrame.decode(b"TNBU\x00\x00\x00\x01")


# ── high-level codec ─────────────────────────────────────────────────


@pytest.mark.parametrize("use_gcm", [True, False], ids=["gcm", "cbc"])
def test_codec_round_trip(use_gcm: bool) -> None:
    from engine.protocol.codec import decode_inform, encode_inform

    payload = {"mac": "02:00:00:ab:cd:ef", "model": "USW24P250", "version": "8.3.42"}
    frame = encode_inform(payload=payload, key=_KEY, mac=_MAC, use_gcm=use_gcm)
    assert frame.startswith(b"TNBU")
    result = decode_inform(frame, key=_KEY)
    assert result == payload


def test_codec_gcm_sets_flag() -> None:
    from engine.protocol.codec import encode_inform
    from engine.protocol.tnbu import FLAG_AES_GCM, InformFrame

    frame = encode_inform(payload={"x": 1}, key=_KEY, mac=_MAC, use_gcm=True)
    assert InformFrame.decode(frame).flags & FLAG_AES_GCM


def test_codec_cbc_clears_gcm_flag() -> None:
    from engine.protocol.codec import encode_inform
    from engine.protocol.tnbu import FLAG_AES_GCM, InformFrame

    frame = encode_inform(payload={"x": 1}, key=_KEY, mac=_MAC, use_gcm=False)
    assert not (InformFrame.decode(frame).flags & FLAG_AES_GCM)


def test_codec_encrypted_flag_always_set() -> None:
    from engine.protocol.codec import encode_inform
    from engine.protocol.tnbu import FLAG_ENCRYPTED, InformFrame

    for use_gcm in (True, False):
        frame = encode_inform(payload={}, key=_KEY, mac=_MAC, use_gcm=use_gcm)
        assert InformFrame.decode(frame).flags & FLAG_ENCRYPTED


def test_codec_mac_in_frame_matches_input() -> None:
    from engine.protocol.codec import encode_inform
    from engine.protocol.tnbu import InformFrame

    frame = encode_inform(payload={}, key=_KEY, mac=_MAC, use_gcm=True)
    assert InformFrame.decode(frame).mac == _MAC


def test_codec_wrong_key_raises() -> None:
    from cryptography.exceptions import InvalidTag

    from engine.protocol.codec import decode_inform, encode_inform

    frame = encode_inform(payload={"a": 1}, key=_KEY, mac=_MAC, use_gcm=True)
    with pytest.raises(InvalidTag):
        decode_inform(frame, key=os.urandom(16))


def test_codec_default_key_round_trip() -> None:
    """Default key must decode inform frames correctly — used pre-adoption."""
    from engine.protocol.codec import decode_inform, encode_inform
    from engine.protocol.keys import DEFAULT_INFORM_KEY

    payload = {"default": True, "mac": "02:00:00:ab:cd:ef", "model": "UAP-AC-Pro"}
    frame = encode_inform(payload=payload, key=DEFAULT_INFORM_KEY, mac=_MAC, use_gcm=True)
    assert decode_inform(frame, key=DEFAULT_INFORM_KEY) == payload
