# Inform fixtures

Binary captures of inform frames used by the codec tests in
`backend/tests/contract/test_codec.py`. Each capture is a single TCP
payload (the inform request or response body — not a full pcap), which
keeps the tests decoupled from pcap parsing libraries.

## Layout

Each fixture is a pair:

```
<name>.bin        # raw inform frame bytes (TCP payload)
<name>.meta.yaml  # sidecar with expected decode results
```

Example sidecar:

```yaml
name: phase0-adopt
description: Initial adopt inform from USW24P250 → UDM-SE
direction: device_to_controller   # or controller_to_device
inform_key: "00112233445566778899aabbccddeeff"   # 32 hex chars (16 bytes)
expected_mac: "02:00:00:ab:cd:ef"
expected_aes_variant: gcm                          # or cbc
expected_payload_keys:
  - inform_url
  - mac
  - model
  - version
  - cfgversion
  - uptime
```

## Extracting from tshark

```bash
tshark -r capture.pcapng \
    -Y 'tcp.port == 8080 and tcp.flags.push == 1' \
    -T fields -e data \
  | xxd -r -p > phase0-adopt.bin
```

## Rules

- **Never commit the inform key of a real production controller.** Use a
  lab controller with an inform key you can rotate after capture.
- **Never commit captures that contain real passphrases or PII** — strip
  or regenerate the payload in the lab before committing.
- Keep files under 64 KB where possible; large captures slow the suite.
