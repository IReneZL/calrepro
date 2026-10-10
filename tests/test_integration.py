"""Real offline worker tests; set CALREPRO_PROFILE_ROOT or create .replay-VERSION."""
import os
from pathlib import Path
import resource
import unittest
from calrepro.core import scan, minimize
from calrepro.runner import run
from calrepro.worker import CONFERENCE, DTSTAMP

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = Path(os.environ.get('CALREPRO_PROFILE_ROOT', ROOT))
PYTHONS = {v: PROFILE_ROOT / ('.replay-' + v) / 'bin/python' for v in ('11.1.0', '14.0.1', '14.1.0')}


@unittest.skipUnless(all(p.exists() for p in PYTHONS.values()), 'install all three .replay-VERSION environments')
class IntegrationTests(unittest.TestCase):
    def probe(self, name, version):
        return run(PYTHONS[version], version, (ROOT / 'fixtures' / name).read_bytes())

    def test_profile_matrix_and_controls(self):
        self.assertEqual(self.probe('conference-32.ics', '14.0.1')['fingerprint'], CONFERENCE)
        self.assertEqual(self.probe('conference-32.ics', '14.1.0')['outcome'], 'pass')
        self.assertEqual(self.probe('dtstamp-101.ics', '11.1.0')['fingerprint'], DTSTAMP)
        for v, name in [('14.0.1', 'clean-32.ics'), ('14.1.0', 'clean-32.ics'), ('11.1.0', 'dtstamp-clean-101.ics')]:
            self.assertEqual(self.probe(name, v)['outcome'], 'pass')

    def test_real_reductions_parent_limits_unchanged(self):
        before = {r: resource.getrlimit(r) for r in (resource.RLIMIT_CPU, resource.RLIMIT_AS, resource.RLIMIT_FSIZE)}
        for v, filename, fp in [('14.0.1', 'conference-32.ics', CONFERENCE), ('11.1.0', 'dtstamp-101.ics', DTSTAMP)]:
            data = (ROOT / 'fixtures' / filename).read_bytes()
            reduced, report = minimize(scan(data), lambda d: run(PYTHONS[v], v, d))
            self.assertEqual(report['events_after'], 1)
            self.assertEqual(run(PYTHONS[v], v, reduced)['fingerprint'], fp)
            self.assertEqual(run(PYTHONS[v], v, scan(reduced).candidate([]))['outcome'], 'pass')
        self.assertEqual(before, {r: resource.getrlimit(r) for r in before})

    def test_recurrence_override_keeps_master(self):
        from test_core import event, calendar
        data = calendar(event(b'same') + event(b'other') + event(b'same', b'RECURRENCE-ID:20261002T120000Z\r\nCONFERENCE;VALUE=URI:https://example.invalid/private\r\n'))
        reduced, report = minimize(scan(data), lambda d: run(PYTHONS['14.0.1'], '14.0.1', d))
        self.assertEqual(report['events_after'], 2)
        self.assertEqual(reduced.count(b'UID:same'), 2)

    def test_decoy_string_does_not_match(self):
        from test_core import event, calendar
        decoy = b'DTSTART:not-a-date\r\nSUMMARY:conference.0 Input should be a valid dictionary or instance of Conference [type=model_type]\r\n'
        data = calendar(event(b'a', decoy))
        self.assertEqual(run(PYTHONS['14.0.1'], '14.0.1', data)['outcome'], 'unsupported-failure')

    def test_version_mismatch_clean(self):
        from calrepro.core import ReproError
        with self.assertRaisesRegex(ReproError, 'profile-version-mismatch'):
            run(PYTHONS['14.0.1'], '14.1.0', mode='env')

    def test_consumer_uid_aliases_rejected_before_reduction(self):
        from test_core import event, calendar
        from calrepro.core import ReproError
        extra = b'RECURRENCE-ID:20261002T120000Z\r\nCONFERENCE;VALUE=URI:https://example.invalid/private\r\n'
        aliases = [
            calendar(event(b'uid' + bytes((92,92)) + b'n') + event(b'uid' + bytes((92,)) + b'n', extra)),
            calendar(event(b'foo\r\n|X:bar') + event(b'fooX:bar', extra)),
        ]
        for data in aliases:
            self.assertEqual(run(PYTHONS['14.0.1'], '14.0.1', data)['fingerprint'], CONFERENCE)
            with self.assertRaisesRegex(ReproError, 'input-ambiguous'):
                minimize(scan(data), lambda d: run(PYTHONS['14.0.1'], '14.0.1', d))

    def test_supported_text_escape_aliases_keep_recurrence_group(self):
        from test_core import event, calendar
        extra = b'RECURRENCE-ID:20261002T120000Z\r\nCONFERENCE;VALUE=URI:https://example.invalid/private\r\n'
        data = calendar(event(b'uid' + bytes((92,)) + b'n') + event(b'uid' + bytes((92,)) + b'N', extra))
        reduced, report = minimize(scan(data), lambda d: run(PYTHONS['14.0.1'], '14.0.1', d))
        self.assertEqual(report['events_after'], 2)
        self.assertEqual(reduced, data)
