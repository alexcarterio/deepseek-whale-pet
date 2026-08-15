# Changelog

## [Unreleased]

## [1.0.1] - 2026-08-15

### Security

- Add the missing `zstandard` dependency to `requirements.txt` (the DSH session
  watcher crashed on a fresh install without it).
- Hide the API key behind password-style input in the set-key dialog.
- Skip comment/blank lines when reading the key from the DSH credentials file.
- Launch DSH without a shell (`shell=False` with an argv list), removing the
  shell-injection surface from the launch path.
- URL-encode the city name in weather lookups.
- Narrow debug prints (no longer log full API response bodies).
- Document the data flow, API key storage, and ntfy privacy note in a new
  README "Privacy & Security" section.

### Added

- `tests/test_security_fixes.py` — 16 regression assertions covering the items
  above.

## [1.0.0] - 2026-08-15

### Added

- Initial public release: desktop pet with DSH session notifications, voice announcements, balance lookup, auto-launch, and ntfy phone push.
