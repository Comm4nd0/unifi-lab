"""Fernet decryption for worker-side reads of Django-written secrets.

Django's ``apps.common.fields.EncryptedTextField`` encrypts with
``cryptography.Fernet.MultiFernet`` using ``UVL_FERNET_KEY`` (current) +
optionally ``UVL_FERNET_KEY_PREV`` for rotation. Decryption on the worker
side uses the same construction — never the Django app, so this module
stays import-clean from the engine process.
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _multi_fernet():  # type: ignore[no-untyped-def]
    from cryptography.fernet import Fernet, MultiFernet

    current = os.environ.get("UVL_FERNET_KEY", "") or ""
    previous = os.environ.get("UVL_FERNET_KEY_PREV", "") or ""
    keys = [Fernet(k.encode()) for k in (current, previous) if k]
    if not keys:
        raise RuntimeError("UVL_FERNET_KEY is not configured for the worker")
    return MultiFernet(keys)


def decrypt(ciphertext: str) -> str:
    """Decrypt a value written by Django's EncryptedTextField.

    Raises cryptography.fernet.InvalidToken on key mismatch / corruption.
    Callers should catch and treat as an authentication failure.
    """
    if not ciphertext:
        return ""
    return _multi_fernet().decrypt(ciphertext.encode()).decode()
