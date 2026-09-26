"""
Diff two EnvSnapshots and produce a structured drift report.

Severity rules:
  CRITICAL  Python/Node major.minor change, OS or architecture change
  WARNING   package removed or downgraded, declared constraint changed,
            runtime patch change, lockfile removed, env var removed/changed
  INFO      package added or upgraded, lockfile or env var added
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .versions import compare_versions, same_minor

SEVERITIES = ('CRITICAL', 'WARNING', 'INFO')


@dataclass
class Change:
    section:     str
    kind:        str       # added | removed | changed
    severity:    str       # CRITICAL | WARNING | INFO
    description: str
    detail:      Optional[str] = None


@dataclass
class EnvDriftReport:
    baseline_meta: dict
    current_meta:  dict
    changes:       List[Change] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.changes

    @property
    def critical(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'CRITICAL']

    @property
    def warnings(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'WARNING']

    @property
    def info(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'INFO']

    def has_at_least(self, severity: str) -> bool:
        """True if any change is as severe as `severity` or more."""
        rank = SEVERITIES.index(severity)
        return any(SEVERITIES.index(c.severity) <= rank for c in self.changes)

# ── Per-section diffing ───────────────────────────────────────────────────────

def _diff_runtime(label: str, section: str, a: Optional[str], b: Optional[str],
                  critical_on_minor: bool) -> List[Change]:
    if a == b or (not a and not b):
        return []
    if a and b:
        if critical_on_minor and not same_minor(a, b):
            severity = 'CRITICAL'
        elif section == 'system.os':
            severity = 'CRITICAL'
        else:
            severity = 'WARNING'
        return [Change(section, 'changed', severity, f'{label} version changed', f'{a} → {b}')]
    if b:
        return [Change(section, 'added', 'INFO', f'{label} detected', b)]
    return [Change(section, 'removed', 'WARNING', f'{label} no longer detected', f'was {a}')]


def _diff_versions(section: str, label: str, a: dict, b: dict) -> List[Change]:
    """Resolved versions (pip list, package-lock): upgrades are INFO, downgrades WARNING."""
    changes = []
    for k in sorted(b.keys() - a.keys()):
        changes.append(Change(section, 'added', 'INFO', f'{label}: {k} added', b[k] or None))
    for k in sorted(a.keys() - b.keys()):
        changes.append(Change(section, 'removed', 'WARNING', f'{label}: {k} removed',
                              f'was {a[k]}' if a[k] else None))
    for k in sorted(a.keys() & b.keys()):
        if a[k] == b[k]:
            continue
        order = compare_versions(str(a[k]), str(b[k]))
        if order is not None and order < 0:
            changes.append(Change(section, 'changed', 'INFO', f'{label}: {k} upgraded', f'{a[k]} → {b[k]}'))
        elif order is not None and order > 0:
            changes.append(Change(section, 'changed', 'WARNING', f'{label}: {k} downgraded', f'{a[k]} → {b[k]}'))
        else:
            changes.append(Change(section, 'changed', 'WARNING', f'{label}: {k} version changed',
                                  f'{a[k]} → {b[k]}'))
    return changes


def _diff_declared(section: str, label: str, a: dict, b: dict) -> List[Change]:
    """Declared constraints (requirements.txt, pyproject, package.json): any change is a WARNING."""
    changes = []
    for k in sorted(b.keys() - a.keys()):
        changes.append(Change(section, 'added', 'INFO', f'{label}: {k} added', b[k] or None))
    for k in sorted(a.keys() - b.keys()):
        changes.append(Change(section, 'removed', 'WARNING', f'{label}: {k} removed',
                              f'was {a[k]}' if a[k] else None))
    for k in sorted(a.keys() & b.keys()):
        if a[k] != b[k]:
            changes.append(Change(section, 'changed', 'WARNING', f'{label}: {k} constraint changed',
                                  f'{a[k] or "(any)"} → {b[k] or "(any)"}'))
    return changes


def _diff_list(section: str, label: str, a: list, b: list) -> List[Change]:
    changes = [Change(section, 'added', 'INFO', f'{label}: {x} added') for x in sorted(set(b) - set(a))]
    changes += [Change(section, 'removed', 'WARNING', f'{label}: {x} removed') for x in sorted(set(a) - set(b))]
    return changes


def _diff_env_vars(a: dict, b: dict) -> List[Change]:
    skip = {'PATH'}   # too noisy / session-specific
    a = {k: v for k, v in a.items() if k not in skip}
    b = {k: v for k, v in b.items() if k not in skip}
    changes = [Change('env_vars', 'added', 'INFO', f'Env var added: {k}', b[k]) for k in sorted(b.keys() - a.keys())]
    changes += [Change('env_vars', 'removed', 'WARNING', f'Env var removed: {k}') for k in sorted(a.keys() - b.keys())]
    changes += [Change('env_vars', 'changed', 'WARNING', f'Env var changed: {k}', f'{a[k][:60]} → {b[k][:60]}')
                for k in sorted(a.keys() & b.keys()) if a[k] != b[k]]
    return changes

# ── Entry point ───────────────────────────────────────────────────────────────

def diff_snapshots(snap_a, snap_b) -> EnvDriftReport:
    report = EnvDriftReport(baseline_meta=snap_a.meta, current_meta=snap_b.meta)
    ch = report.changes
    py_a, py_b = snap_a.python, snap_b.python
    nd_a, nd_b = snap_a.node, snap_b.node
    sy_a, sy_b = snap_a.system, snap_b.system

    def pkgs(env: dict, key: str) -> dict:
        return env.get('packages', {}).get(key, {}) or {}

    # Python
    ch += _diff_runtime('Python', 'python.runtime', py_a.get('python_version'),
                        py_b.get('python_version'), critical_on_minor=True)
    ch += _diff_versions('python.packages', 'pip', pkgs(py_a, 'pip_installed'), pkgs(py_b, 'pip_installed'))
    ch += _diff_declared('python.packages', 'requirements.txt',
                         pkgs(py_a, 'requirements_txt'), pkgs(py_b, 'requirements_txt'))
    ch += _diff_declared('python.packages', 'pyproject',
                         pkgs(py_a, 'pyproject_deps'), pkgs(py_b, 'pyproject_deps'))
    ch += _diff_list('lockfiles', 'Python lockfile', py_a.get('lockfiles', []), py_b.get('lockfiles', []))

    # Node
    ch += _diff_runtime('Node.js', 'node.runtime', nd_a.get('node_version'),
                        nd_b.get('node_version'), critical_on_minor=True)
    ch += _diff_declared('node.packages', 'npm dep', pkgs(nd_a, 'dependencies'), pkgs(nd_b, 'dependencies'))
    ch += _diff_declared('node.packages', 'npm devDep',
                         pkgs(nd_a, 'devDependencies'), pkgs(nd_b, 'devDependencies'))
    ch += _diff_versions('node.packages', 'npm locked', pkgs(nd_a, 'locked'), pkgs(nd_b, 'locked'))
    ch += _diff_list('lockfiles', 'Node lockfile', nd_a.get('lockfiles', []), nd_b.get('lockfiles', []))

    # System (python/node runtimes are already covered above)
    rt_a, rt_b = sy_a.get('runtimes', {}), sy_b.get('runtimes', {})
    for name in sorted((rt_a.keys() | rt_b.keys()) - {'python', 'node'}):
        ch += _diff_runtime(name.capitalize(), 'system.runtime', rt_a.get(name), rt_b.get(name),
                            critical_on_minor=False)
    ch += _diff_runtime('OS', 'system.os', sy_a.get('os'), sy_b.get('os'), critical_on_minor=False)
    ch += _diff_runtime('Architecture', 'system.os', sy_a.get('arch'), sy_b.get('arch'),
                        critical_on_minor=False)
    ch += _diff_env_vars(sy_a.get('env_vars', {}), sy_b.get('env_vars', {}))

    return report
