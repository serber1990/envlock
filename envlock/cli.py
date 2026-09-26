#!/usr/bin/env python3
"""
envlock — freeze a project's Python/Node/system environment and detect drift.

Exit codes:  0 no drift (at or above --fail-on)   1 drift detected   2 usage or I/O error
"""
import argparse
import sys
from pathlib import Path

from shellcolorize import Color

from . import __version__
from .diff import diff_snapshots
from .renderer import render_json, render_markdown, render_terminal
from .snapshot import DEFAULT_PATH, EnvSnapshot, take_snapshot

EXIT_OK, EXIT_DRIFT, EXIT_ERROR = 0, 1, 2
FAIL_LEVELS = {'info': 'INFO', 'warning': 'WARNING', 'critical': 'CRITICAL'}


# Progress and errors go to stderr so stdout only carries the report (safe to pipe into jq).
def _ok(msg):   print(f"  {Color.GREEN}✔{Color.RESET}  {msg}", file=sys.stderr)
def _step(msg): print(f"  {Color.CYAN}▶{Color.RESET}  {msg}", file=sys.stderr)
def _err(msg):  print(f"  {Color.RED}✖{Color.RESET}  {msg}", file=sys.stderr)


# ── snapshot ──────────────────────────────────────────────────────────────────

def cmd_snapshot(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else DEFAULT_PATH
    path = Path(args.path)
    if not path.is_dir():
        _err(f'Not a directory: {path}')
        return EXIT_ERROR

    print(f"\n  {Color.CYAN}{Color.BOLD}envlock  ·  snapshot{Color.RESET}\n", file=sys.stderr)
    _step(f'Scanning environment at {path.resolve()}...')
    snap = take_snapshot(path=str(path))

    try:
        snap.save(output)
    except OSError as e:
        _err(f'Cannot write {output}: {e.strerror}')
        return EXIT_ERROR

    py, nd, system = snap.python, snap.node, snap.system
    n_pkgs = len(py.get('packages', {}).get('pip_installed', {}))
    print()
    _ok(f'Baseline saved: {output}')
    print(f"  Python   : {py.get('python_version') or 'not found'}  "
          f"({n_pkgs} packages, {py.get('interpreter') or 'no interpreter'})")
    print(f"  Node     : {nd.get('node_version') or 'not found'}  "
          f"(files: {', '.join(nd.get('lockfiles', [])) or 'none'})")
    print(f"  OS       : {system.get('os') or '?'}  [{system.get('arch') or '?'}]")
    print(f"  Runtimes : {', '.join(system.get('runtimes', {})) or 'none detected'}")
    print()
    return EXIT_OK

# ── check / diff ──────────────────────────────────────────────────────────────

def _load(path: Path):
    try:
        return EnvSnapshot.load(path)
    except FileNotFoundError:
        _err(f'Snapshot not found: {path}')
    except (OSError, ValueError) as e:
        _err(f'Cannot read snapshot {path}: {e}')
    return None


def _report(report, args: argparse.Namespace) -> int:
    fmt = args.format
    if fmt == 'terminal' and args.output:
        fmt = 'markdown' if str(args.output).endswith('.md') else 'json'

    if fmt == 'terminal':
        render_terminal(report)
    else:
        text = render_json(report) if fmt == 'json' else render_markdown(report)
        if args.output:
            try:
                Path(args.output).write_text(text + '\n', encoding='utf-8')
            except OSError as e:
                _err(f'Cannot write {args.output}: {e.strerror}')
                return EXIT_ERROR
            _ok(f'Report saved to {args.output}')
        else:
            print(text)

    if args.fail_on == 'never':
        return EXIT_OK
    return EXIT_DRIFT if report.has_at_least(FAIL_LEVELS[args.fail_on]) else EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline) if args.baseline else DEFAULT_PATH
    if not baseline_path.exists():
        _err(f'Baseline not found: {baseline_path}')
        _err("Run 'envlock snapshot' first to create one.")
        return EXIT_ERROR
    baseline = _load(baseline_path)
    if baseline is None:
        return EXIT_ERROR

    _step('Collecting current environment...')
    current = take_snapshot(path=args.path)
    return _report(diff_snapshots(baseline, current), args)


def cmd_diff(args: argparse.Namespace) -> int:
    snap_a, snap_b = _load(Path(args.snapshot_a)), _load(Path(args.snapshot_b))
    if snap_a is None or snap_b is None:
        return EXIT_ERROR
    return _report(diff_snapshots(snap_a, snap_b), args)

# ── main ──────────────────────────────────────────────────────────────────────

def _add_report_options(p: argparse.ArgumentParser) -> None:
    p.add_argument('--format', '-f', choices=['terminal', 'json', 'markdown'], default='terminal',
                   help='Report format (default: terminal)')
    p.add_argument('--output', '-o', metavar='FILE',
                   help='Write the report to FILE (json or markdown; inferred from .md/.json if needed)')
    p.add_argument('--fail-on', choices=['info', 'warning', 'critical', 'never'], default='info',
                   help='Lowest severity that makes the exit code 1 (default: info = any change)')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='envlock',
        description='Freeze Python, Node and system environments — detect drift before it breaks your builds.',
        epilog='exit codes: 0 no drift · 1 drift detected · 2 error',
    )
    parser.add_argument('-v', '--version', action='version', version=f'envlock {__version__}')
    sub = parser.add_subparsers(dest='command', metavar='COMMAND')

    p_snap = sub.add_parser('snapshot', help='Capture the current environment as baseline')
    p_snap.add_argument('--path', '-p', metavar='DIR', default='.',
                        help='Project directory to scan (default: current dir)')
    p_snap.add_argument('--output', '-o', metavar='FILE',
                        help=f'Output path (default: {DEFAULT_PATH})')

    p_check = sub.add_parser('check', help='Compare the current environment against the baseline')
    p_check.add_argument('--baseline', '-b', metavar='FILE',
                         help=f'Baseline to compare against (default: {DEFAULT_PATH})')
    p_check.add_argument('--path', '-p', metavar='DIR', default='.',
                         help='Project directory to scan (default: current dir)')
    _add_report_options(p_check)

    p_diff = sub.add_parser('diff', help='Compare two snapshot files')
    p_diff.add_argument('snapshot_a', metavar='BASELINE')
    p_diff.add_argument('snapshot_b', metavar='CURRENT')
    _add_report_options(p_diff)
    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    Color.auto()

    if args.command is None:
        parser.print_help()
        sys.exit(EXIT_OK)

    dispatch = {'snapshot': cmd_snapshot, 'check': cmd_check, 'diff': cmd_diff}
    try:
        sys.exit(dispatch[args.command](args))
    except KeyboardInterrupt:
        _err('Interrupted')
        sys.exit(130)


if __name__ == '__main__':
    main()
