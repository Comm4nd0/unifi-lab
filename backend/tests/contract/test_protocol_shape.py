"""Contract tests for the inform protocol interface.

Phase 0: verifies the codec module exposes the expected symbols so that
once bytes-level implementation lands, callers won't need to adapt. The
bytes-level tests live under ``tests/contract/`` once pcaps are committed.
"""

from __future__ import annotations

import pytest


def test_tnbu_constants_exported():
    from engine.protocol import tnbu

    assert tnbu.MAGIC == b"TNBU"
    assert tnbu.VERSION == 1
    assert tnbu.FLAG_ENCRYPTED == 1
    assert tnbu.FLAG_COMPRESSED == 2
    assert tnbu.FLAG_AES_GCM == 4


def test_codec_surface_exists():
    from engine.protocol import codec, crypto

    assert callable(codec.encode_inform)
    assert callable(codec.decode_inform)
    assert callable(crypto.encrypt_cbc)
    assert callable(crypto.decrypt_cbc)
    assert callable(crypto.encrypt_gcm)
    assert callable(crypto.decrypt_gcm)


def test_codec_raises_until_implemented():
    from engine.protocol import codec

    with pytest.raises(NotImplementedError):
        codec.encode_inform(payload={}, key=b"\x00" * 16, mac=b"\x00" * 6)
