# Changelog

## [Unreleased]

### Added

- Subagent session filtering in `dsh_watch`: subagent sessions (detected from
  the `origin` field of the session log) are no longer tracked or announced —
  only the main session triggers bubbles and voice prompts.
- Waiting events now carry `kind` (`question` / `approval`) and `tool` fields.

### Fixed

- Subagent detection now scans the first 128 KB of the log (instead of only the
  first line) and re-checks on every file change, so a brand-new subagent file
  is no longer mistaken for a main session under a first-line race.
- `turn/end` is only announced when the turn actually completed
  (`reason.kind == "completed"`); aborted, errored, and cancelled turns stay
  silent.
- Tests updated for the new completion semantics (10 checks).

## [1.0.3] - 2026-08-15

### Changed

- Fully decouple from the phone push feature: remove all phone-notification
  mentions from the README and credits. This repository is the desktop pet
  only; phone notifications are out of scope here.

## [1.0.2] - 2026-08-15

### Changed

- Move the phone push helper out of this repository: `dsh_push.py` and
  `start_push.bat` now live in the
  [dsh-mobile-access](https://github.com/alexcarterio/dsh-mobile-access)
  repository under `dsh-push/`. The README points there and keeps the ntfy
  privacy note; existing local deployments keep working unchanged.
- Mark `dsh_watch.py` as the canonical copy (a mirror ships with
  dsh-mobile-access).

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
