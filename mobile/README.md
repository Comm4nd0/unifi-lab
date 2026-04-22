# UVL Mobile

**Phase 5 — not yet implemented.**

This directory will hold the Flutter viewer app (iOS + Android + web).
Stack per the vault design:

- Flutter 3.x + Dart
- Riverpod state management
- `dio` + `retrofit` for HTTP
- `hive` for local persistence
- Read-only in v1

## Bootstrap

When Phase 5 begins:

```bash
cd mobile
flutter create . --project-name uvl_mobile --org com.unifilab --platforms=ios,android,web
flutter pub get
```

Then wire up Riverpod providers and generate the Dart client from the
OpenAPI spec at `../schemas/openapi.yaml`.
