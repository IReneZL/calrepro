# Contributing

This release candidate targets Linux and trusted Python 3.11+ environments.
Keep the CLI dependency-free and replay dependencies in separate environments.

## Local checks

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src tests
.venv/bin/calrepro version
```

For parser integration checks, install the three `profiles/*.lock` files into
separate trusted environments, then use `env`, `check`, and `minimize` with explicit
absolute interpreter paths. Integration tests discover `.replay-VERSION/bin/python`
under the checkout, or under `CALREPRO_PROFILE_ROOT` when set. CI uses the checkout
paths on Python 3.12. These setup steps may use PyPI; replay workers must
remain offline. Linux must have `libseccomp` installed. A passing unit suite alone
does not demonstrate all parser profiles worked: inspect skipped integration tests
and run the documented replay commands against synthetic fixtures as appropriate.

## Change requirements

- Use synthetic calendar fixtures only. Never commit personal calendars, parser
  exception strings containing calendar values, credentials, or local exports
- Preserve retained bytes and UID-group integrity, including recurrence overrides,
  folded UIDs, nested alarms, and timezone definitions
- Test negative paths: malformed input, unknown failure, unavailable isolation,
  exhausted budgets, interpreter/profile mismatch, and existing output paths
- Keep unsupported failures distinct from supported fingerprints. Do not broaden
  fingerprints merely to make a failing case pass
- Never claim global minimality, root-cause proof, anonymity, or full HA parity
- Do not copy upstream implementation code; link to primary evidence instead

Before publication, review package contents, run installed-wheel smoke tests,
verify each replay profile, and review the security model. Version pins are not
hash-locked supply-chain verification. CI is a check definition, not evidence that
it has run successfully on a hosting service.
