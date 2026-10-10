# Third-party dependency notices

calrepro implementation code is MIT-licensed. Its parser adapter is original API
usage; it does not embed upstream implementation code. Synthetic fixtures were
carried forward from this project’s own calendar reproduction spike. No real
calendar data is included. The replay packages below are installed separately,
not vendored into the CLI. Their licenses are independent of calrepro’s license.

This inventory was verified from distribution metadata and license files in the
installed 11.1.0, 14.0.1, and 14.1.0 replay environments on 2026-10-10. License
files are reproduced unchanged under `licenses/`. The inventory describes these
specific replay distributions, not every transitive native component or a legal
opinion about redistribution. Consult the packages themselves before bundling them.

| Distribution | Version | Metadata license | License text |
| --- | --- | --- | --- |
| annotated-types | 0.8.0 | MIT | [1](licenses/annotated-types-0.8.0-1.txt) |
| ical | 11.1.0 | Apache-2.0 | [1](licenses/ical-11.1.0-1.txt) |
| ical | 14.0.1 | Apache-2.0 | [1](licenses/ical-14.0.1-1.txt) |
| ical | 14.1.0 | Apache-2.0 | [1](licenses/ical-14.1.0-1.txt) |
| pydantic | 2.14.0 | MIT | [1](licenses/pydantic-2.14.0-1.txt) |
| pydantic_core | 2.50.0 | MIT | [1](licenses/pydantic_core-2.50.0-1.txt) |
| python-dateutil | 2.9.0.post0 | Dual License | [1](licenses/python-dateutil-2.9.0.post0-1.txt) |
| six | 1.17.0 | MIT | [1](licenses/six-1.17.0-1.txt) |
| typing-inspection | 0.4.4 | MIT | [1](licenses/typing-inspection-0.4.4-1.txt) |
| typing_extensions | 4.16.0 | PSF-2.0 | [1](licenses/typing_extensions-4.16.0-1.txt) |
| tzdata | 2026.5 | Apache-2.0 | [1](licenses/tzdata-2026.5-1.txt), [2](licenses/tzdata-2026.5-2.txt) |

`python-dateutil` describes a dual license; its accompanying file explains the
Apache-2.0 terms for newer contributions and the BSD terms for older contributions.
`typing_extensions` includes historical Python license terms in its full license.
The package notices above retain the original copyright and attribution text.

Python and the host-provided libseccomp library are also required system components;
neither is bundled. Their licenses and any platform-specific notices are supplied
by the interpreter and operating-system distributor. Build and CI tools are
development dependencies, not CLI runtime dependencies.
