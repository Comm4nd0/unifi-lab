"""Inform payload crypto — AES-128-CBC for older firmware, AES-128-GCM for newer.

The inform key is provisioned at adoption time and may rotate. Do not
log key bytes or plaintext payloads.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_BLOCK_BITS = 128


def encrypt_cbc(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    padder = sym_padding.PKCS7(_BLOCK_BITS).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def decrypt_cbc(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(_BLOCK_BITS).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def encrypt_gcm(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Encrypt with AES-128-GCM; returns ciphertext with 16-byte auth tag appended."""
    return AESGCM(key).encrypt(nonce, plaintext, aad or None)


def decrypt_gcm(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    """Decrypt AES-128-GCM; ciphertext must include the 16-byte auth tag suffix."""
    return AESGCM(key).decrypt(nonce, ciphertext, aad or None)
