"""Custom Django model fields.

``EncryptedTextField`` stores Fernet-encrypted text at rest.
``EncryptedBinaryField`` stores Fernet-encrypted raw bytes at rest (e.g. AES
inform keys) as a base64-encoded ciphertext in a TextField column.

The Fernet key comes from ``settings.FERNET_KEY``. A previous key
(``FERNET_KEY_PREV``) may be set during rotation — decrypt tries current first,
then previous.
"""

from __future__ import annotations

import base64

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet():  # type: ignore[no-untyped-def]
    from cryptography.fernet import Fernet, MultiFernet

    current = getattr(settings, "FERNET_KEY", "") or ""
    previous = getattr(settings, "FERNET_KEY_PREV", "") or ""
    keys = [Fernet(k.encode()) for k in (current, previous) if k]
    if not keys:
        return None
    return MultiFernet(keys)


class EncryptedTextField(models.TextField):
    description = "Fernet-encrypted text."

    def from_db_value(self, value, expression, connection):  # type: ignore[no-untyped-def]
        if value in (None, ""):
            return value
        f = _fernet()
        if f is None:
            raise ImproperlyConfigured("FERNET_KEY is not configured.")
        return f.decrypt(value.encode()).decode()

    def to_python(self, value):  # type: ignore[no-untyped-def]
        return value

    def get_prep_value(self, value):  # type: ignore[no-untyped-def]
        if value in (None, ""):
            return value
        f = _fernet()
        if f is None:
            raise ImproperlyConfigured("FERNET_KEY is not configured.")
        return f.encrypt(str(value).encode()).decode()


class EncryptedBinaryField(models.TextField):
    """Store arbitrary bytes encrypted with Fernet; persisted as base64 text.

    Round-trips: Python ``bytes`` → Fernet-encrypt → base64 → TextField column.
    On read: base64 decode → Fernet-decrypt → ``bytes``.
    Designed for compact binary secrets such as AES-128 inform keys.
    """

    description = "Fernet-encrypted binary data."

    def from_db_value(self, value, expression, connection):  # type: ignore[no-untyped-def]
        if value in (None, ""):
            return b""
        f = _fernet()
        if f is None:
            raise ImproperlyConfigured("FERNET_KEY is not configured.")
        return f.decrypt(base64.b64decode(value))

    def to_python(self, value):  # type: ignore[no-untyped-def]
        if isinstance(value, bytes) or value is None:
            return value
        # Coming from deserialization as a base64 string without encryption context.
        try:
            return base64.b64decode(value)
        except Exception:
            return value

    def get_prep_value(self, value):  # type: ignore[no-untyped-def]
        if not value:
            return ""
        f = _fernet()
        if f is None:
            raise ImproperlyConfigured("FERNET_KEY is not configured.")
        raw = value if isinstance(value, bytes) else str(value).encode()
        return base64.b64encode(f.encrypt(raw)).decode()
