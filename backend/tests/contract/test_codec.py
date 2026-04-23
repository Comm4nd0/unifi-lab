"""Inform-codec round-trip tests against real capture fixtures.

These parametrize over every paired ``<name>.bin`` + ``<name>.meta.yaml``
in ``tests/fixtures/informs/``. On a fresh clone (no captures) they
collect zero parametrizations — harmless.

While ``engine.protocol.codec`` and ``tnbu.InformFrame`` still raise
``NotImplementedError`` (per CLAUDE.md: "real implementation awaits
pcap captures"), the assertions are marked ``xfail(strict=True)`` — so
they stay green in the current stubbed state, and will loudly flip to
``XPASS`` the moment Marco's real implementation lands, prompting the
``xfail`` removal. Drop a real capture in and the same mechanism does
double duty: the xfail tells you the codec isn't there yet.

This is a harness contract, not an implementation aid — no real bytes
are expected to decode today.
"""

from __future__ import annotations

import pytest

from ._inform_fixtures import discover_fixtures

FIXTURES = discover_fixtures()

codec_not_ready = pytest.mark.xfail(
    reason="engine.protocol.codec still stubbed — awaiting pcap-driven implementation",
    strict=True,
    raises=NotImplementedError,
)


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
@codec_not_ready
def test_tnbu_decode_matches_expected_mac(fixture):  # type: ignore[no-untyped-def]
    from engine.protocol.tnbu import InformFrame

    frame = InformFrame.decode(fixture.raw)
    assert frame.mac == fixture.expected_mac, (
        f"fixture {fixture.name}: decoded MAC {frame.mac!r} "
        f"does not match meta expected_mac {fixture.expected_mac!r}"
    )


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
@codec_not_ready
def test_tnbu_flags_match_aes_variant(fixture):  # type: ignore[no-untyped-def]
    from engine.protocol.tnbu import FLAG_AES_GCM, InformFrame

    frame = InformFrame.decode(fixture.raw)
    if fixture.expected_aes_variant == "gcm":
        assert frame.flags & FLAG_AES_GCM, (
            f"fixture {fixture.name} declares GCM but TNBU flag is missing"
        )
    else:
        assert not (frame.flags & FLAG_AES_GCM), (
            f"fixture {fixture.name} declares CBC but TNBU flag has GCM bit set"
        )


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
@codec_not_ready
def test_decode_inform_returns_expected_payload_keys(fixture):  # type: ignore[no-untyped-def]
    from engine.protocol.codec import decode_inform

    payload = decode_inform(fixture.raw, key=fixture.inform_key)
    missing = [k for k in fixture.expected_payload_keys if k not in payload]
    assert not missing, f"fixture {fixture.name}: missing expected keys {missing}"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
@codec_not_ready
def test_encode_inform_round_trips(fixture):  # type: ignore[no-untyped-def]
    """Decode → encode → must reproduce the original bytes.

    Round-trip is the strongest signal that the codec really understands
    the wire format end to end, rather than a lenient partial decode.
    """
    from engine.protocol.codec import decode_inform, encode_inform

    decoded = decode_inform(fixture.raw, key=fixture.inform_key)
    use_gcm = fixture.expected_aes_variant == "gcm"
    reencoded = encode_inform(
        payload=decoded,
        key=fixture.inform_key,
        mac=fixture.expected_mac,
        use_gcm=use_gcm,
    )
    assert reencoded == fixture.raw, (
        f"fixture {fixture.name}: re-encoded frame differs from original "
        f"({len(reencoded)} vs {len(fixture.raw)} bytes)"
    )


def test_fixture_dir_discoverable_even_when_empty() -> None:
    """Harness contract: a fresh clone with no captures collects cleanly.

    Parametrizing over ``FIXTURES`` with an empty list produces zero test
    items for the round-trip tests above — that is intentional and means
    the suite stays green until captures arrive.
    """
    # ``FIXTURES`` is evaluated at module import; this just confirms the
    # loader path didn't raise.
    assert isinstance(FIXTURES, list)
