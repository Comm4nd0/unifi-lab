"""Inform payload crypto — AES-128-CBC for older firmware, AES-128-GCM for newer.

The inform key is provisioned at adoption time and may rotate. Do not
log key bytes or plaintext payloads.
"""

from __future__ import annotations


def encrypt_cbc(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    raise NotImplementedError("AES-CBC encrypt not implemented — awaiting pcap captures")


def decrypt_cbc(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    raise NotImplementedError("AES-CBC decrypt not implemented — awaiting pcap captures")


def encrypt_gcm(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    raise NotImplementedError("AES-GCM encrypt not implemented — awaiting pcap captures")


def decrypt_gcm(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    raise NotImplementedError("AES-GCM decrypt not implemented — awaiting pcap captures")
