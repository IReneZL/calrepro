import ctypes.util
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from calrepro.core import ReproError
from calrepro.runner import run
from calrepro import worker


class HarnessTests(unittest.TestCase):
    def test_missing_seccomp_fails_closed(self):
        with patch('ctypes.util.find_library', return_value=None):
            with self.assertRaises(RuntimeError):
                worker.block_network()

    def test_guard_blocks_socket_in_child(self):
        source = str(Path(worker.__file__).resolve())
        script = '''import importlib.util, socket
spec = importlib.util.spec_from_file_location('guard', %r)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.apply_limits()
m.block_network()
for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
    try:
        socket.socket(family)
    except PermissionError:
        continue
    raise RuntimeError('network unexpectedly available')
print('blocked')
''' % source
        p = subprocess.run([sys.executable, '-I', '-B', '-c', script], capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, 'guard child failed')
        self.assertEqual(p.stdout, b'blocked\n')

    def test_worker_protocol_is_bounded_and_value_free(self):
        for raw in [b'bad SECRET', b'\xff', b'[]', b'null', b'{}',
                    b'{"outcome":"error","error":"SECRET"}',
                    b'{"outcome":"error","error":{}}',
                    b'{"outcome":"pass","events":"SECRET"}',
                    b'{"outcome":"fail","fingerprint":{"SECRET":true}}',
                    b'[' * 1100 + b']' * 1100, b'x' * 5000]:
            class FakeProcess:
                returncode = 0
                def __init__(self, *args, **kwargs):
                    kwargs['stdout'].write(raw)
                def communicate(self, *args, **kwargs):
                    return (None, None)
            with self.subTest(raw=raw[:20]), patch('calrepro.runner.subprocess.Popen', FakeProcess):
                with self.assertRaisesRegex(ReproError, '^worker-invalid-response$'):
                    run(sys.executable, '14.1.0')

    def test_worker_error_is_not_input_exception(self):
        p = subprocess.run([sys.executable, '-I', '-B', worker.__file__, 'bogus-SECRET', 'check'],
                           capture_output=True, timeout=10)
        result = json.loads(p.stdout)
        self.assertEqual(result['error'], 'invalid-worker-invocation')
        self.assertNotIn(b'SECRET', p.stdout + p.stderr)
