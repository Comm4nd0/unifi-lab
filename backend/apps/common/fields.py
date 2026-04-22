"""Custom Django model fields.

``EncryptedTextField`` stores Fernet-encrypted text at rest. The key comes
from ``settings.FERNET_KEY``. A previous key (``FERNET_KEY_PREV``) may be
set during rotation — decrypt tries current first, then previous.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet() -> MultiFernet | None:
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
