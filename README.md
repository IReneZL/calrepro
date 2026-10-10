# calrepro

A small, Linux-only developer CLI for reproducing selected `ical` import failures
and reducing a calendar to a byte-preserving, 1-minimal set of event UID groups.
This is release candidate **0.1.0rc1**. Source and prereleases are available at
https://github.com/IReneZL/calrepro. This candidate is not published to PyPI.

The tool runs a specified, trusted Python environment locally. It does not fetch
calendar URLs, access accounts, call model APIs, upload files, or repair calendars.
Its two supported failure families are a `CONFERENCE` validation failure and a
malformed `DTSTAMP` property-name failure. Other parser failures are unsupported.

## Install and prepare a replay environment

Requirements: Linux, Python 3.11 or later for the CLI, and the system `libseccomp`
shared library. The CLI has no Python runtime dependencies; parser dependencies
live in separate environments. Installed package metadata for all three `ical`
profiles declares `Requires-Python: >=3.11`; that is a compatibility declaration,
not test evidence. The verified replay happy path uses Python **3.12.14**. Other
interpreter/dependency pairings are not established by this release candidate.
CI is configured for Python 3.12 replay and is not a claim that hosted CI has run.

From a source checkout:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install .
python3.12 -m venv .replay-14.0.1
.replay-14.0.1/bin/python -m pip install --only-binary=:all: --index-url https://pypi.org/simple -r profiles/ical-14.0.1.lock
```

Installing packages may use the network. Parser execution is separately guarded
and offline. Review and trust the interpreter and installed packages before use.
The lock files pin versions, not artifact hashes, and are not a full historical
Home Assistant environment. Wheels also include these files under
`share/calrepro/profiles` in the installation prefix.

Replay profiles: `11.1.0`, `14.0.1`, and `14.1.0`, each with a matching
`profiles/ical-VERSION.lock`. Create a separate environment for each profile.

## Use

Use an absolute path to the replay environment's Python executable:

```sh
.venv/bin/calrepro version
.venv/bin/calrepro env --profile 14.0.1 --python "$PWD/.replay-14.0.1/bin/python"
.venv/bin/calrepro check input.ics --profile 14.0.1 --python "$PWD/.replay-14.0.1/bin/python"
.venv/bin/calrepro minimize input.ics --output reduced.ics --profile 14.0.1 --python "$PWD/.replay-14.0.1/bin/python"
```

`check` reports whether this consumer parses the input. `minimize` accepts only a
recognized failure and preserves its structured fingerprint while deleting whole
UID groups. `env` reports the selected replay environment. Command results emit JSON
with safe diagnostics rather than calendar values or raw parser exceptions.

Exit statuses:

- `0`: parsing passed, or minimization/environment/version command succeeded
- `1`: `check` reproduced a supported failure
- `2`: unsupported failure, invalid input, resource limit, or harness failure

Optional minimization limits: `--max-trials` (3–512, default 512) and
`--total-seconds` (1–300, default 300). Lower limits may stop before a result
can be certified. A successful result is 1-minimal: removing any one remaining
UID group stops reproducing the target fingerprint. This is not a global minimum,
a property-level minimum, or proof of the underlying cause.

## Synthetic demo

After preparing `.replay-14.0.1` above, run this from the source checkout:

```sh
.venv/bin/calrepro check fixtures/conference-32.ics --profile 14.0.1 --python "$PWD/.replay-14.0.1/bin/python"
# Expected exit status: 1 (recognized CONFERENCE failure)
.venv/bin/calrepro minimize fixtures/conference-32.ics --output reduced-conference.ics --profile 14.0.1 --python "$PWD/.replay-14.0.1/bin/python"
# Expected exit status: 0; JSON reports events_before=32 and events_after=1
```

The destination must not already exist. This fixture has one event per UID group,
so its result is also 32 → 1 groups. With a separate 14.1.0 environment installed
from its lock file, the original synthetic fixture passes `check`. The supplied
`dtstamp-101.ics` fixture similarly reduces 101 → 1 under profile 11.1.0. These are
synthetic demonstrations, not the original reporters’ calendars.

## What is preserved

Events sharing the same logical, unfolded UID are reduced together, including
recurrence masters and overrides. Every event must have exactly one UID property;
a UID shared across different events is valid. Missing UIDs, duplicate UID
properties in one event, UID parameters, invalid UID TEXT escapes, escaped literal backslashes in UIDs,
physical lines beginning with `|`, malformed
component boundaries, nested or multiple calendars, binary input, and non-UTF-8
input are rejected. UID matching is case-sensitive and normalizes supported RFC TEXT escapes.
The escaped-backslash and pipe-fold restrictions deliberately reject inputs whose
UID identity can differ between RFC decoding and the pinned consumers; this prevents
those known aliases from splitting a consumer recurrence group.

Only whole `VEVENT` spans are removed. All remaining bytes, including line folds,
calendar metadata, nested event components, and `VTIMEZONE` definitions, remain
unchanged. Timezones are never pruned. Grouping by UID is deliberately conservative
and does not prove all semantic dependencies between events have been modeled.

## Bounds and security

- Input: at most 2 MiB
- Each parser worker: 5 seconds CPU, 10 seconds wall time, 512 MiB address space
- Minimization: at most 512 trials and a 300-second reduction deadline; input
  reading/scanning and final file export occur outside that deadline
- Linux `libseccomp` network syscall filtering, installed before parser imports;
  inability to establish the guard fails closed

This is a bounded local replay guard, **not a malicious-code sandbox**. Only use a
trusted Python executable and trusted installed packages. See [SECURITY.md](SECURITY.md).

The reduced file still contains sensitive calendar data. Reduction is not
anonymization. Writing it requires the explicit `--output` option, creates a new
file with mode `0600`, and never overwrites an existing destination. Inspect it
before sharing. JSON output is designed to avoid calendar-content disclosure;
that does not make the exported `.ics` file safe to publish.

## Scope and provenance

The adapter follows the Home Assistant compatibility-mode/parser call sequence,
not the whole Home Assistant integration. It does not test fetching, caching,
recurrence expansion, entity setup, or UI behavior. The historical `CONFERENCE`
case compares `ical` 14.0.1 and 14.1.0; the malformed `DTSTAMP` case uses 11.1.0.
These are narrow regression reproductions, not a general ICS standards validator
or broad real-world compatibility claim. Fixtures are synthetic; upstream source
code is not included.

Historical references behind the supported cases:

- [Home Assistant CONFERENCE report #178292](https://github.com/home-assistant/core/issues/178292)
- [Home Assistant dependency update #178626](https://github.com/home-assistant/core/pull/178626)
- [ical 14.1.0 release](https://github.com/allenporter/ical/releases/tag/14.1.0)
- [Home Assistant malformed DTSTAMP report #158482](https://github.com/home-assistant/core/issues/158482)

These links identify provenance, not upstream endorsement or a claim that an
issue remains open. No upstream implementation source is included.

Development and verification instructions are in [CONTRIBUTING.md](CONTRIBUTING.md).
The project is MIT-licensed; separately installed replay dependencies retain their
own licenses, documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This checkout is a local release candidate, not a
claim of publication, upstream endorsement, or production readiness.
