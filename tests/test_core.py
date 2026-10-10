import contextlib
import io
import os
from pathlib import Path
import resource
import tempfile
import unittest
from unittest.mock import patch

from calrepro.core import ReproError, MAX_INPUT, read_input, scan, minimize, export_private
from calrepro.cli import main
from calrepro.runner import run
from calrepro.worker import CONFERENCE


def event(uid=b'a', extra=b''):
    return b'BEGIN:VEVENT\r\nUID:' + uid + b'\r\nDTSTAMP:20261001T000000Z\r\nDTSTART:20261001T120000Z\r\n' + extra + b'END:VEVENT\r\n'


def calendar(body=b''):
    return b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Synthetic calrepro//EN\r\n' + body + b'END:VCALENDAR\r\n'


class CoreTests(unittest.TestCase):
    def test_exact_bytes_and_uid_recurrence_groups(self):
        zone = b'BEGIN:VTIMEZONE\r\nTZID:Dummy\r\nEND:VTIMEZONE\r\n'
        master = event(b'foo', b'SUMMARY:folded\r\n  value\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\nEND:VALARM\r\n')
        override = event(b'fo\r\n o', b'RECURRENCE-ID:20261002T120000Z\r\n')
        data = calendar(zone + master + event(b'drop') + override)
        c = scan(data)
        self.assertEqual(c.groups, ((0, 2), (1,)))
        self.assertEqual(c.candidate([0]), calendar(zone + master + override))
        self.assertEqual(c.candidate([]), calendar(zone))
        self.assertEqual(c.candidate([0, 1]), data)

    def test_uid_case_sensitive_and_escape_normalization(self):
        c = scan(calendar(event(b'A') + event(b'a') + event(b'x\\n') + event(b'x\\N')))
        self.assertEqual(c.groups, ((0,), (1,), (2, 3)))

    def test_malformed_structures(self):
        good = calendar(event())
        invalid = [good + good, b'junk\r\n' + good, good + b'junk',
                   good.replace(b'END:VEVENT', b'END:VTODO'),
                   good.replace(b'UID:a\r\n', b''),
                   good.replace(b'UID:a', b'UID:a\r\nUID:b'),
                   good.replace(b'UID:a', b'UID;X-THING=1:a'),
                   good.replace(b'UID:a', b'UID:bad\\q'),
                   good.replace(b'UID:a', b'UID:bad' + bytes((92,92)) + b'n'),
                   good.replace(b'UID:a', b'UID:a\r\n|X:bar'),
                   good.replace(b'BEGIN:VEVENT', b'BEGIN :VEVENT'),
                   good.replace(b'BEGIN:VEVENT', b'BEGIN:VCALENDAR\r\nBEGIN:VEVENT'),
                   good.replace(b'BEGIN:VEVENT', b'BEGIN:VTODO\r\nBEGIN:VEVENT'),
                   b' BEGIN:VCALENDAR\r\n', b'', b'BEGIN:VCALENDAR\r\n']
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ReproError):
                scan(value)

    def test_bytes_rejected_before_oracle(self):
        for value in [b'\xff', b'\x00', b'\x7f', b'\r', b'x' * (MAX_INPUT + 1)]:
            with self.assertRaises(ReproError):
                scan(value)

    def test_read_bound_and_regular_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'input'
            with p.open('wb') as f:
                f.truncate(MAX_INPUT + 100000)
            with self.assertRaisesRegex(ReproError, 'input-too-large'):
                read_input(p)
            p.unlink()
            os.mkfifo(p)
            with self.assertRaisesRegex(ReproError, 'regular-file'):
                read_input(p)

    def test_reduction_preserves_groups_and_minimality(self):
        data = calendar(event(b'keep') + event(b'other') + event(b'keep', b'X-BAD:yes\r\n'))
        oracle = lambda d: {'outcome': 'fail', 'fingerprint': CONFERENCE} if b'X-BAD:yes' in d else {'outcome': 'pass', 'events': 0}
        out, report = minimize(scan(data), oracle)
        self.assertEqual(out, calendar(event(b'keep') + event(b'keep', b'X-BAD:yes\r\n')))
        self.assertEqual(report['groups_after'], 1)
        self.assertEqual(report['events_after'], 2)

    def test_global_failures_and_clean_inputs(self):
        c = scan(calendar(event()))
        with self.assertRaisesRegex(ReproError, 'unsupported-global-failure'):
            minimize(c, lambda d: {'outcome': 'fail', 'fingerprint': CONFERENCE})
        with self.assertRaisesRegex(ReproError, 'no-supported-failure'):
            minimize(c, lambda d: {'outcome': 'unsupported-failure'})

    def test_unknown_and_different_failure_not_target(self):
        c = scan(calendar(event(b'bad', b'X-BAD:yes\r\n') + event(b'decoy')))
        def oracle(d):
            if b'X-BAD:yes' in d:
                return {'outcome': 'fail', 'fingerprint': CONFERENCE}
            return {'outcome': 'unsupported-failure'}
        out, _ = minimize(c, oracle)
        self.assertIn(b'X-BAD:yes', out)
        self.assertNotIn(b'UID:decoy', out)

    def test_budgets_no_export(self):
        c = scan(calendar(event()))
        oracle = lambda d: {'outcome': 'fail', 'fingerprint': CONFERENCE} if b'VEVENT' in d else {'outcome': 'pass', 'events': 0}
        with self.assertRaisesRegex(ReproError, 'trial-budget'):
            minimize(c, oracle, max_trials=3)
        for trials in [0, 513]:
            with self.assertRaisesRegex(ReproError, 'invalid-reduction-budget'):
                minimize(c, oracle, max_trials=trials)
        with patch('calrepro.core.time.monotonic', side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(ReproError, 'total-time-budget'):
                minimize(c, oracle, total_seconds=1)

    def test_private_exclusive_export(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'result'
            prior = os.umask(0)
            try:
                export_private(p, b'secret')
            finally:
                os.umask(prior)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ReproError):
                export_private(p, b'new')
            link = Path(d) / 'link'
            link.symlink_to(p)
            with self.assertRaises(ReproError):
                export_private(link, b'new')
            self.assertEqual(p.read_bytes(), b'secret')

    def test_cli_does_not_echo_sensitive_args(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['check', 'secret-person.ics', '--profile', 'SECRET', '--python', '/SECRET'])
        self.assertEqual(code, 2)
        self.assertNotIn('SECRET', output.getvalue())
        self.assertNotIn('secret-person', output.getvalue())

    def test_parent_limits_unchanged_missing_profile(self):
        import sys
        limits = {r: resource.getrlimit(r) for r in (resource.RLIMIT_CPU, resource.RLIMIT_AS, resource.RLIMIT_FSIZE)}
        # Current core-test interpreter usually lacks profiles; either outcome is safe.
        try:
            run(sys.executable, '14.1.0', mode='env')
        except ReproError as e:
            self.assertIn(str(e), {'profile-not-installed', 'profile-version-mismatch'})
        self.assertEqual(limits, {r: resource.getrlimit(r) for r in limits})

    def test_timeout_is_clean(self):
        import sys
        with self.assertRaisesRegex(ReproError, 'worker-timeout'):
            run(sys.executable, '14.1.0', timeout=0.000001)

    def test_explicit_trusted_interpreter(self):
        with self.assertRaisesRegex(ReproError, 'absolute-python'):
            run('python', '14.1.0')

    def test_huge_cli_budget_is_clean_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            source, dest = Path(d) / 'input.ics', Path(d) / 'output.ics'
            source.write_bytes(calendar(event()))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(['minimize', str(source), '--output', str(dest),
                               '--profile', '14.0.1', '--python', '/trusted/python',
                               '--total-seconds', '9' * 400])
            self.assertEqual(result, 2)
            self.assertIn('invalid-reduction-budget', output.getvalue())
            self.assertNotIn('99999', output.getvalue())
            self.assertFalse(dest.exists())
