---
name: Bug report
about: Report a reproducible problem using synthetic data only
---

## Privacy check

Never attach real ICS/calendar files, raw parser logs, credentials, access tokens,
private feed URLs, or sensitive screenshots. Reduced calendars are not anonymous.
For security concerns, follow SECURITY.md rather than filing a public report.
Use a hand-written synthetic fixture with invented values, or describe the issue
without attachments. Review every item before submitting.

- [ ] This report contains no real calendar content, logs, credentials, or private URLs
- [ ] Any fixture was created from scratch with synthetic values

## Environment

- calrepro version:
- Linux distribution and architecture:
- Python version and selected replay profile:
- Result of `calrepro env` (review its JSON before sharing):

Do not paste absolute paths containing personal information.

## Expected and observed behavior

Describe the behavior and safe error code. Avoid raw third-party exceptions.

## Synthetic reproduction

List commands with placeholder paths and, if necessary, a minimal synthetic
fixture. Include the exit status and content-free JSON from calrepro after review.

## Scope

Does this affect checking, UID-group reduction, byte preservation, export, or
isolation setup? Note any nondefault trial/time budgets.
