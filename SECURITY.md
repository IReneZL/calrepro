# Security and privacy

## Trust boundary

Calendar contents are untrusted. The selected Python interpreter, its startup
behavior, installed packages, the host OS, and this tool must be trusted.
`--python` is an explicit executable choice, not a safe way to run unknown code.

Parser workers establish a fail-closed Linux `libseccomp` network syscall filter
before importing the parser. Resource limits bound CPU, wall time, and address
space. These controls reduce accidental network access and resource exhaustion;
they do not provide a general sandbox for malicious interpreter or package code,
or a guarantee against host compromise. Isolation setup failures are errors, not
permission to continue unguarded. No claim is made that a network namespace is
available or used.

Package installation is outside parser isolation and may contact PyPI. Review
packages and version pins before installation. Lock files pin versions without
artifact hashes. The project does not recreate the entire historical HA runtime.

## Data handling

The tool does not fetch feeds, log into accounts, use model APIs, or upload data.
Diagnostics deliberately avoid raw input and input-bearing exception details.
A reduced calendar is still sensitive: retained names, descriptions, locations,
URLs, and other properties can identify people or reveal private information.
Reduction does not redact or anonymize any retained content.

Raw export is explicit through `minimize --output`, exclusive-create only, with
file mode `0600`. Choose a private directory you control, inspect output before
sharing, and treat input and output files with the same care. Existing output
files must not be overwritten. Local backups, sync agents, and OS-level access
are outside the tool's control.

## Reporting

Use GitHub's private vulnerability reporting from the repository Security tab:
https://github.com/IReneZL/calrepro/security/advisories

Share a minimal synthetic example and version information, not a real calendar.
Do not post sensitive input to a public issue tracker.
