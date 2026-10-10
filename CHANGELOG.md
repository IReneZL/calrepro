# Changelog

## 0.1.0rc1 — 2026-10-10

First public release candidate for https://github.com/IReneZL/calrepro.

- Package a dependency-free CLI with explicit trusted parser-environment selection
- Add `check`, `minimize`, `env`, and `version` commands
- Provide pinned replay profiles for `ical` 11.1.0, 14.0.1, and 14.1.0
- Recognize selected CONFERENCE and malformed DTSTAMP failure fingerprints
- Reduce whole unfolded-UID groups while preserving all retained bytes and timezones
- Bound local replay and fail closed when Linux network isolation cannot be set up
- Require explicit, private, no-overwrite export of reduced calendar files

Scope remains narrow: no repair, anonymity, global minimality, full Home Assistant
integration, cross-platform support, or malicious-code sandbox claim.

- Reject ambiguous UID backslash encodings and non-RFC pipe folds that alias
  recurrence identities in the pinned consumers; unfold lines in linear time.
