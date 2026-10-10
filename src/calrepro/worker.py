"""Private worker entry point. Only fixed profiles; no user-supplied predicates.

This file is launched directly under a trusted, explicitly selected interpreter.
It intentionally depends only on the standard library until the guard is active.
"""
import sys
import os
import json

PINNED = {
    'annotated-types': '0.8.0', 'pydantic': '2.14.0',
    'pydantic_core': '2.50.0', 'python-dateutil': '2.9.0.post0',
    'six': '1.17.0', 'typing-inspection': '0.4.4',
    'typing_extensions': '4.16.0', 'tzdata': '2026.5',
}
PROFILES = ('11.1.0', '14.0.1', '14.1.0')
CONFERENCE = {'family': 'conference-model-type', 'exception': 'CalendarParseError',
              'component': 'Event', 'field': ['conference', 0],
              'validation_type': 'model_type', 'expected_model': 'Conference'}
DTSTAMP = {'family': 'dtstamp-property-trailing-space', 'exception': 'CalendarParseError',
           'stage': 'content-line', 'validation_type': 'invalid_property_name',
           'property': 'DTSTAMP', 'defect': 'trailing-space'}


def apply_limits():
    import resource
    for kind, maximum in ((resource.RLIMIT_CPU, 5),
                          (resource.RLIMIT_AS, 512 * 1024 * 1024),
                          (resource.RLIMIT_FSIZE, 64 * 1024),
                          (resource.RLIMIT_CORE, 0),
                          (resource.RLIMIT_NOFILE, 64)):
        _, hard = resource.getrlimit(kind)
        bound = maximum if hard == resource.RLIM_INFINITY else min(maximum, hard)
        resource.setrlimit(kind, (bound, bound))


def block_network():
    import ctypes
    import ctypes.util
    import errno
    import socket
    path = ctypes.util.find_library('seccomp')
    if not path:
        raise RuntimeError('missing seccomp')
    lib = ctypes.CDLL(path, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.restype = None
    ctx = lib.seccomp_init(0x7fff0000)
    if not ctx:
        raise RuntimeError('seccomp init')
    try:
        for name in ('socket', 'socketpair', 'connect', 'accept', 'accept4',
                     'bind', 'listen', 'sendto', 'sendmsg', 'sendmmsg',
                     'recvfrom', 'recvmsg', 'recvmmsg', 'io_uring_setup', 'socketcall'):
            nr = lib.seccomp_syscall_resolve_name(name.encode('ascii'))
            if nr >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, nr, 0) != 0:
                raise RuntimeError('seccomp rule')
        if lib.seccomp_load(ctx) != 0:
            raise RuntimeError('seccomp load')
    finally:
        lib.seccomp_release(ctx)
    try:
        s = socket.socket()
    except PermissionError:
        return
    s.close()
    raise RuntimeError('seccomp self test')


def fingerprint(exc):
    """Recognize error structure, never matching user values embedded in text."""
    from pydantic import ValidationError
    cause = exc.__cause__
    if isinstance(cause, ValidationError) and cause.title == 'Event':
        errors = cause.errors(include_url=False, include_context=True, include_input=False)
        if len(errors) == 1:
            error = errors[0]
            if (error.get('loc') == ('conference', 0)
                    and error.get('type') == 'model_type'
                    and error.get('ctx', {}).get('class_name') == 'Conference'):
                return CONFERENCE
    # The tokenizer wraps this exact constant without user data for this family.
    if (str(exc) == 'Calendar contents are not valid ICS format, see the detailed_error for more information'
            and exc.detailed_error == "Invalid property name 'DTSTAMP '"):
        return DTSTAMP
    return None


def execute(profile, mode):
    from importlib.metadata import version, PackageNotFoundError
    import platform
    try:
        actual = {name: version(name) for name in PINNED}
        actual['ical'] = version('ical')
    except PackageNotFoundError:
        return {'outcome': 'error', 'error': 'profile-not-installed'}
    if actual != dict(PINNED, ical=profile):
        return {'outcome': 'error', 'error': 'profile-version-mismatch'}
    if mode == 'env':
        return {'outcome': 'ready', 'python': platform.python_version(),
                'profile': profile, 'dependencies': actual, 'network': 'seccomp-blocked'}
    raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return {'outcome': 'error', 'error': 'input-too-large'}
    text = raw.decode('utf-8')
    from ical.calendar_stream import IcsCalendarStream
    from ical.compat import enable_compat_mode
    from ical.exceptions import CalendarParseError
    try:
        with enable_compat_mode(text) as compatible:
            cal = IcsCalendarStream.calendar_from_ics(compatible)
        return {'outcome': 'pass', 'events': len(cal.events)}
    except CalendarParseError as exc:
        fp = fingerprint(exc)
        return {'outcome': 'fail', 'fingerprint': fp} if fp else {'outcome': 'unsupported-failure'}
    except Exception:
        return {'outcome': 'unsupported-failure'}


def main():
    # Silence native writes as well as Python logging. Only this saved descriptor
    # carries a fixed-schema result, never parser stdout/stderr or input text.
    result_fd = os.dup(1)
    with open(os.devnull, 'wb') as null:
        os.dup2(null.fileno(), 1)
        os.dup2(null.fileno(), 2)
    result = {'outcome': 'error', 'error': 'worker-internal-failure'}
    try:
        if sys.platform != 'linux':
            result = {'outcome': 'error', 'error': 'linux-required'}
        elif len(sys.argv) != 3 or sys.argv[1] not in PROFILES or sys.argv[2] not in ('check', 'env'):
            result = {'outcome': 'error', 'error': 'invalid-worker-invocation'}
        else:
            try:
                apply_limits()
                block_network()
            except Exception:
                result = {'outcome': 'error', 'error': 'isolation-unavailable'}
            else:
                import logging
                logging.disable(logging.CRITICAL)
                result = execute(sys.argv[1], sys.argv[2])
    except BaseException:
        pass
    os.write(result_fd, json.dumps(result, sort_keys=True).encode('ascii') + b'\n')
    os.close(result_fd)


if __name__ == '__main__':
    main()
