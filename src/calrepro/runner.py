"""Content-free, bounded subprocess transport for trusted parser environments."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from .core import ReproError
from .worker import CONFERENCE, DTSTAMP, PINNED, PROFILES


def run(python, profile, data=b'', mode='check', timeout=10):
    if sys.platform != 'linux':
        raise ReproError('linux-required')
    if profile not in PROFILES:
        raise ReproError('unknown-profile')
    interpreter = Path(python)
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ReproError('trusted-absolute-python-path-required')
    # Environment cannot inject modules or startup hooks. Interpreter/site packages
    # themselves remain trusted; this is not an arbitrary-code sandbox.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
    with tempfile.TemporaryFile() as output:
        try:
            p = subprocess.Popen([str(interpreter), '-I', '-B', str(Path(__file__).with_name('worker.py')),
                                  profile, mode], stdin=subprocess.PIPE, stdout=output,
                                 stderr=subprocess.DEVNULL, close_fds=True, env=env,
                                 start_new_session=True)
            try:
                p.communicate(data, timeout=min(timeout, 10))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.communicate()
                raise ReproError('worker-timeout') from None
            except BaseException:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait()
                raise
        except OSError:
            raise ReproError('worker-start-failed') from None
        if p.returncode != 0:
            raise ReproError('worker-resource-limit-or-crash')
        output.seek(0)
        raw = output.read(4097)
    if len(raw) > 4096:
        raise ReproError('worker-invalid-response')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ReproError('worker-invalid-response') from None
    if not isinstance(result, dict):
        raise ReproError('worker-invalid-response')
    outcome = result.get('outcome')
    if outcome == 'error':
        # Whitelist even the worker's diagnostics: never echo arbitrary JSON.
        allowed = {'profile-not-installed', 'profile-version-mismatch', 'linux-required',
                   'invalid-worker-invocation', 'isolation-unavailable', 'worker-internal-failure',
                   'input-too-large'}
        error = result.get('error')
        raise ReproError(error if isinstance(error, str) and error in allowed else 'worker-invalid-response')
    if mode == 'env' and outcome == 'ready':
        import re
        if (result.get('dependencies') == dict(PINNED, ical=profile)
                and isinstance(result.get('python'), str)
                and re.fullmatch(r'\d+\.\d+\.\d+', result['python'])):
            return {'outcome': 'ready', 'profile': profile, 'python': result['python'],
                    'dependencies': dict(PINNED, ical=profile), 'network': 'seccomp-blocked'}
    if outcome == 'pass' and type(result.get('events')) is int and 0 <= result['events'] <= 100000:
        return {'outcome': 'pass', 'events': result['events']}
    if outcome == 'unsupported-failure':
        return {'outcome': 'unsupported-failure'}
    if outcome == 'fail' and result.get('fingerprint') in (CONFERENCE, DTSTAMP):
        return {'outcome': 'fail', 'fingerprint': result['fingerprint']}
    raise ReproError('worker-invalid-response')
