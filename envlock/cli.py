#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from shellcolorize import Color

from .snapshot import EnvSnapshot, take_snapshot, DEFAULT_PATH
from .diff import diff_snapshots
from .renderer import render_terminal, render_markdown, render_json

VERSION = "1.0.0"


def _ok(msg):   print(f"  {Color.GREEN}✔{Color.RESET}  {msg}")
def _step(msg): print(f"  {Color.CYAN}▶{Color.RESET}  {msg}")
def _err(msg):  print(f"  {Color.RED}✖{Color.RESET}  {msg}")


# ── snapshot ──────────────────────────────────────────────────────────────────

def cmd_snapshot(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else DEFAULT_PATH
    path   = args.path or '.'

    print()
    print(f"  {Color.CYAN}{Color.BOLD}envlock  ·  snapshot{Color.RESET}")
    print()
    _step(f'Scanning environment at {Path(path).resolve()}...')

    snap = take_snapshot(path=path, verbose=True)

    _step(f'Saving baseline to {output}...')
    try:
        snap.save(output)
    except PermissionError:
        _err(f'Permission denied: {output}')
        return 1

    py  = snap.python
    nd  = snap.node
    sys = snap.system

    print()
    _ok(f'Baseline saved: {output}')
    _ok(f'Python   : {py.get("python_version", "not found")}  '
        f'({sum(len(v) for v in py.get("packages", {}).values())} packages tracked)')
    _ok(f'Node     : {nd.get("node_version") or "not found"}  '
        f'(lockfiles: {", ".join(nd.get("lockfiles", [])) or "none"})')
    _ok(f'OS       : {sys.get("os", "?")}  [{sys.get("arch", "?")}]')
    _ok(f'Runtimes : {", ".join(sys.get("runtimes", {}).keys()) or "none detected"}')
    print()
    return 0


# ── check ─────────────────────────────────────────────────────────────────────

def cmd_check(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline) if args.baseline else DEFAULT_PATH

    if not baseline_path.exists():
        _err(f'Baseline not found: {baseline_path}')
        _err("Run 'envlock snapshot' first to create one.")
        return 1

    _step('Loading baseline...')
    try:
        baseline = EnvSnapshot.load(baseline_path)
    except Exception as e:
        _err(f'Failed to load baseline: {e}')
        return 1

    _step('Collecting current environment...')
    current = take_snapshot(path=args.path or '.', verbose=False)

    _step('Comparing...')
    report = diff_snapshots(baseline, current)

    fmt = getattr(args, 'format', 'terminal')
    _output_report(report, fmt, getattr(args, 'output', None))

    return 1 if report.changes else 0


# ── diff ──────────────────────────────────────────────────────────────────────

def cmd_diff(args: argparse.Namespace) -> int:
    try:
        snap_a = EnvSnapshot.load(Path(args.snapshot_a))
        snap_b = EnvSnapshot.load(Path(args.snapshot_b))
    except FileNotFoundError as e:
        _err(f'File not found: {e}')
        return 1
    except Exception as e:
        _err(f'Failed to load snapshot: {e}')
        return 1

    report = diff_snapshots(snap_a, snap_b)
    _output_report(report, getattr(args, 'format', 'terminal'), getattr(args, 'output', None))
    return 1 if report.changes else 0


# ── shared output ─────────────────────────────────────────────────────────────

def _output_report(report, fmt: str, output_path) -> None:
    if fmt == 'json':
        print(render_json(report))
    elif fmt == 'markdown':
        md = render_markdown(report)
        if output_path:
            Path(output_path).write_text(md, encoding='utf-8')
            _ok(f'Report saved to {output_path}')
        else:
            print(md)
    else:
        render_terminal(report)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='envlock',
        description='Detect drift in Python, Node, and system environments.',
    )
    parser.add_argument('-v', '--version', action='version', version=f'envlock {VERSION}')
    sub = parser.add_subparsers(dest='command', metavar='COMMAND')

    # snapshot
    p_snap = sub.add_parser('snapshot', help='Capture current environment as baseline')
    p_snap.add_argument('--path', '-p', metavar='DIR', default='.',
                        help='Project directory to scan (default: current dir)')
    p_snap.add_argument('--output', '-o', metavar='FILE',
                        help=f'Output path (default: {DEFAULT_PATH})')

    # check
    p_check = sub.add_parser('check', help='Compare current environment against baseline')
    p_check.add_argument('--baseline', '-b', metavar='FILE',
                         help=f'Baseline to compare against (default: {DEFAULT_PATH})')
    p_check.add_argument('--path', '-p', metavar='DIR', default='.',
                         help='Project directory to scan (default: current dir)')
    p_check.add_argument('--format', '-f', choices=['terminal', 'json', 'markdown'],
                         default='terminal')
    p_check.add_argument('--output', '-o', metavar='FILE',
                         help='Save report to file (markdown format only)')

    # diff
    p_diff = sub.add_parser('diff', help='Compare any two snapshot files')
    p_diff.add_argument('snapshot_a', metavar='BASELINE')
    p_diff.add_argument('snapshot_b', metavar='CURRENT')
    p_diff.add_argument('--format', '-f', choices=['terminal', 'json', 'markdown'],
                        default='terminal')
    p_diff.add_argument('--output', '-o', metavar='FILE',
                        help='Save report to file (markdown format only)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch = {'snapshot': cmd_snapshot, 'check': cmd_check, 'diff': cmd_diff}
    sys.exit(dispatch[args.command](args))


if __name__ == '__main__':
    main()
