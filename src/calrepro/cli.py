"""calrepro command line interface."""
import argparse
import json
import sys
import time
from . import __version__
from .core import ReproError, read_input, scan, minimize, export_private
from .runner import run
from .worker import PROFILES


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's usual message may echo sensitive filenames or argument values.
        raise ReproError('invalid-command-arguments-use-help')


def parser():
    p = SafeParser(description='Local profile-specific calendar failure isolation (Linux only).')
    subs = p.add_subparsers(dest='command', required=True)
    subs.add_parser('version', help='print package version')
    for name in ('env', 'check', 'minimize'):
        sub = subs.add_parser(name)
        sub.add_argument('--profile', choices=PROFILES, required=True)
        sub.add_argument('--python', required=True, help='absolute path to a TRUSTED profile Python interpreter')
        if name != 'env':
            sub.add_argument('input', help='local UTF-8 ICS file, at most 2 MiB')
        if name == 'minimize':
            sub.add_argument('--output', required=True, help='explicit sensitive raw-ICS export; new file only')
            sub.add_argument('--max-trials', type=int, default=512)
            sub.add_argument('--total-seconds', type=int, default=300)
    return p


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == 'version':
            result, status = {'version': __version__}, 0
        elif args.command == 'env':
            result, status = run(args.python, args.profile, mode='env'), 0
        else:
            data = read_input(args.input)
            calendar = scan(data)
            if args.command == 'check':
                result = run(args.python, args.profile, data)
                status = {'pass': 0, 'fail': 1, 'unsupported-failure': 2}[result['outcome']]
            else:
                if not 3 <= args.max_trials <= 512 or not 1 <= args.total_seconds <= 300:
                    raise ReproError('invalid-reduction-budget')
                deadline = time.monotonic() + args.total_seconds
                reduced, result = minimize(calendar, lambda d: run(
                    args.python, args.profile, d, timeout=max(0.001, deadline - time.monotonic())),
                                           args.max_trials, args.total_seconds)
                export_private(args.output, reduced)
                result['warning'] = 'raw output remains sensitive; review locally before sharing'
                status = 0
            result['profile'] = args.profile
    except ReproError as exc:
        result, status = {'outcome': 'error', 'error': str(exc)}, 2
    except (OSError, ValueError, MemoryError):
        result, status = {'outcome': 'error', 'error': 'local-operation-failed'}, 2
    except KeyboardInterrupt:
        result, status = {'outcome': 'error', 'error': 'interrupted'}, 2
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == '__main__':
    sys.exit(main())
