"""Bounded raw-byte calendar scanning and UID-group deletion."""
from dataclasses import dataclass
import os
import stat
import time

MAX_INPUT = 2 * 1024 * 1024

class ReproError(Exception):
    """A fixed, content-free diagnostic safe to display."""


def read_input(path):
    try:
        # O_NONBLOCK also prevents an attacker-controlled FIFO from hanging open.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise ReproError('input-must-be-regular-file')
            data = f.read(MAX_INPUT + 1)
    except OSError:
        raise ReproError('input-unreadable') from None
    validate_bytes(data)
    return data


def validate_bytes(data):
    if len(data) > MAX_INPUT:
        raise ReproError('input-too-large')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        raise ReproError('input-not-utf8') from None
    if any(c < 32 and c not in (9, 10, 13) for c in data) or b'\x7f' in data:
        raise ReproError('input-binary-control')
    if b'\r' in data.replace(b'\r\n', b''):
        raise ReproError('input-invalid-line-ending')


@dataclass(frozen=True)
class Calendar:
    data: bytes
    spans: tuple
    groups: tuple

    def candidate(self, ids):
        events = {i for g in ids for i in self.groups[g]}
        parts, pos = [], 0
        for i, (a, b) in enumerate(self.spans):
            parts.append(self.data[pos:a])
            if i in events:
                parts.append(self.data[a:b])
            pos = b
        parts.append(self.data[pos:])
        return b''.join(parts)


def scan(data):
    validate_bytes(data)
    # Unfold only for recognizing structure and logical UID; slice original bytes.
    lines = []
    pos = 0
    for raw in data.splitlines(keepends=True):
        token = raw.rstrip(b'\r\n')
        end = pos + len(raw)
        if token.startswith(b'|'):
            # Pinned consumers also unfold '|'; that non-RFC alias is unsafe.
            raise ReproError('input-ambiguous-fold')
        if token.startswith((b' ', b'\t')):
            if not lines:
                raise ReproError('input-invalid-fold')
            lines[-1][1] = end
            lines[-1][2].extend(token[1:])
        else:
            lines.append([pos, end, bytearray(token)])
        pos = end
    stack, spans, uids, current_uid = [], [], [], None
    seen_calendar, closed, start = False, False, None
    for a, b, token in lines:
        token = bytes(token)
        if not token:
            if not stack:
                continue
            raise ReproError('input-empty-content-line')
        upper = token.upper()
        if upper.startswith(b'BEGIN:'):
            name = upper[6:]
            if not name or any(c not in b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in name):
                raise ReproError('input-malformed-boundary')
            if not stack:
                if seen_calendar or closed or name != b'VCALENDAR':
                    raise ReproError('input-single-calendar-required')
                seen_calendar = True
            elif name == b'VCALENDAR':
                raise ReproError('input-nested-calendar')
            if name == b'VEVENT':
                if stack != [b'VCALENDAR']:
                    raise ReproError('input-event-nesting')
                start, current_uid = a, None
            stack.append(name)
        elif upper.startswith(b'END:'):
            name = upper[4:]
            if not stack or stack[-1] != name:
                raise ReproError('input-unbalanced-boundary')
            if name == b'VEVENT':
                if current_uid is None:
                    raise ReproError('input-event-uid-required')
                spans.append((start, b))
                uids.append(current_uid)
            stack.pop()
            if not stack:
                closed = True
        else:
            if not stack or b':' not in token:
                raise ReproError('input-malformed-envelope')
            head, value = token.split(b':', 1)
            key = head.split(b';', 1)[0].upper()
            if key.strip() in (b'BEGIN', b'END'):
                raise ReproError('input-malformed-boundary')
            if stack == [b'VCALENDAR', b'VEVENT'] and key == b'UID':
                if current_uid is not None or not value or b';' in head:
                    raise ReproError('input-ambiguous-event-uid')
                # Chained consumer unescaping can alias an escaped backslash plus n
                # to a newline. Reject literal-backslash encodings conservatively.
                if bytes((92, 92)) in value:
                    raise ReproError('input-ambiguous-event-uid')
                # UID is case-sensitive TEXT. Normalize supported TEXT escapes.
                uid = bytearray()
                j = 0
                while j < len(value):
                    c = value[j]
                    if c == 92:
                        j += 1
                        if j == len(value) or value[j] not in b'\\;,nN':
                            raise ReproError('input-ambiguous-event-uid')
                        c = 10 if value[j] in b'nN' else value[j]
                    uid.append(c)
                    j += 1
                current_uid = bytes(uid)
    if stack or not seen_calendar or not closed:
        raise ReproError('input-unbalanced-boundary')
    groups = {}
    for i, uid in enumerate(uids):
        groups.setdefault(uid, []).append(i)
    return Calendar(data, tuple(spans), tuple(tuple(g) for g in groups.values()))


def minimize(calendar, oracle, max_trials=512, total_seconds=300):
    if not 3 <= max_trials <= 512 or not 1 <= total_seconds <= 300:
        raise ReproError('invalid-reduction-budget')
    started, calls = time.monotonic(), 0
    def probe(ids):
        nonlocal calls
        if calls >= max_trials:
            raise ReproError('trial-budget-exhausted')
        if time.monotonic() - started >= total_seconds:
            raise ReproError('total-time-budget-exhausted')
        calls += 1
        result = oracle(calendar.candidate(ids))
        if time.monotonic() - started >= total_seconds:
            raise ReproError('total-time-budget-exhausted')
        return result
    kept = list(range(len(calendar.groups)))
    baseline = probe(kept)
    if baseline.get('outcome') != 'fail':
        raise ReproError('no-supported-failure')
    empty = probe([])
    if empty == baseline:
        raise ReproError('unsupported-global-failure')
    n = 2
    while len(kept) >= 2:
        size = (len(kept) + n - 1) // n
        for start in range(0, len(kept), size):
            complement = kept[:start] + kept[start + size:]
            if probe(complement) == baseline:
                kept, n = complement, max(2, n - 1)
                break
        else:
            if n >= len(kept):
                break
            n = min(len(kept), n * 2)
    # Verify every individual group deletion and final replay; no partial export.
    for i in range(len(kept)):
        if probe(kept[:i] + kept[i + 1:]) == baseline:
            raise ReproError('unstable-oracle')
    if probe(kept) != baseline:
        raise ReproError('unstable-oracle')
    return calendar.candidate(kept), {
        'outcome': 'minimized', 'groups_before': len(calendar.groups),
        'groups_after': len(kept), 'events_before': len(calendar.spans),
        'events_after': sum(len(calendar.groups[g]) for g in kept),
        'oracle_calls': calls, 'fingerprint': baseline['fingerprint'],
        'minimality': '1-minimal by whole UID-group deletion; not global or property minimum',
    }


def export_private(path, data):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        raise ReproError('output-must-be-new-writable-path') from None
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        # Leave exclusive-created partial file private; never unlink a raced path.
        raise ReproError('output-write-failed-private-file-may-remain') from None
