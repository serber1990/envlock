"""
Diff two EnvSnapshots and produce a structured DriftReport.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
        return len(self.changes) == 0

    @property
    def critical(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'CRITICAL']

    @property
    def warnings(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'WARNING']

    @property
    def info(self) -> List[Change]:
        return [c for c in self.changes if c.severity == 'INFO']


# ── Severity matrix ───────────────────────────────────────────────────────────

def _sev(section: str, kind: str) -> str:
    matrix = {
        # Python runtime change is critical
        ('python.runtime',  'changed'): 'CRITICAL',
        # Node runtime change is critical
        ('node.runtime',    'changed'): 'CRITICAL',
        # OS / arch change is critical
        ('system.runtime',  'changed'): 'CRITICAL',
        # Package removed — may break reproducibility
        ('python.packages', 'removed'): 'WARNING',
        ('node.packages',   'removed'): 'WARNING',
        # Package added
        ('python.packages', 'added'):   'INFO',
        ('node.packages',   'added'):   'INFO',
        # Package version changed
        ('python.packages', 'changed'): 'WARNING',
        ('node.packages',   'changed'): 'WARNING',
        # New lockfile
        ('lockfiles',       'added'):   'INFO',
        ('lockfiles',       'removed'): 'WARNING',
        # Env var changes
        ('env_vars',        'added'):   'INFO',
        ('env_vars',        'removed'): 'WARNING',
        ('env_vars',        'changed'): 'WARNING',
    }
    return matrix.get((section, kind), 'INFO')


# ── Per-section diffing ───────────────────────────────────────────────────────

def _diff_runtime(label: str, section: str, val_a, val_b) -> List[Change]:
    if val_a == val_b or (not val_a and not val_b):
        return []
    if val_a and val_b:
        return [Change(
            section=section, kind='changed',
            severity=_sev(section, 'changed'),
            description=f'{label} version changed',
            detail=f'{val_a} → {val_b}',
        )]
    if not val_a and val_b:
        return [Change(section=section, kind='added',
                       severity='INFO', description=f'{label} detected: {val_b}')]
    return [Change(section=section, kind='removed',
                   severity='WARNING', description=f'{label} no longer detected (was {val_a})')]


def _diff_pkg_map(section: str, label: str, map_a: dict, map_b: dict) -> List[Change]:
    changes = []
    keys_a, keys_b = set(map_a), set(map_b)

    for k in sorted(keys_b - keys_a):
        changes.append(Change(
            section=section, kind='added',
            severity=_sev(section, 'added'),
            description=f'{label}: {k} added',
            detail=map_b[k] or None,
        ))
    for k in sorted(keys_a - keys_b):
        changes.append(Change(
            section=section, kind='removed',
            severity=_sev(section, 'removed'),
            description=f'{label}: {k} removed',
            detail=f'was {map_a[k]}' if map_a[k] else None,
        ))
    for k in sorted(keys_a & keys_b):
        if map_a[k] != map_b[k]:
            changes.append(Change(
                section=section, kind='changed',
                severity=_sev(section, 'changed'),
                description=f'{label}: {k} version changed',
                detail=f'{map_a[k]} → {map_b[k]}',
            ))
    return changes


def _diff_list(section: str, label: str, list_a: list, list_b: list) -> List[Change]:
    a, b = set(list_a), set(list_b)
    changes = []
    for item in sorted(b - a):
        changes.append(Change(section=section, kind='added',
                              severity=_sev(section, 'added'),
                              description=f'{label}: {item} added'))
    for item in sorted(a - b):
        changes.append(Change(section=section, kind='removed',
                              severity=_sev(section, 'removed'),
                              description=f'{label}: {item} removed'))
    return changes


def _diff_env_vars(map_a: dict, map_b: dict) -> List[Change]:
    changes = []
    # Skip PATH — too noisy / session-specific
    _SKIP = {'PATH'}
    a = {k: v for k, v in map_a.items() if k not in _SKIP}
    b = {k: v for k, v in map_b.items() if k not in _SKIP}

    for k in sorted(set(b) - set(a)):
        changes.append(Change(section='env_vars', kind='added',
                              severity=_sev('env_vars', 'added'),
                              description=f'Env var added: {k}',
                              detail=b[k]))
    for k in sorted(set(a) - set(b)):
        changes.append(Change(section='env_vars', kind='removed',
                              severity=_sev('env_vars', 'removed'),
                              description=f'Env var removed: {k}'))
    for k in sorted(set(a) & set(b)):
        if a[k] != b[k]:
            changes.append(Change(section='env_vars', kind='changed',
                                  severity=_sev('env_vars', 'changed'),
                                  description=f'Env var changed: {k}',
                                  detail=f'{a[k][:60]} → {b[k][:60]}'))
    return changes


# ── Entry point ───────────────────────────────────────────────────────────────

def diff_snapshots(snap_a, snap_b) -> EnvDriftReport:
    report = EnvDriftReport(
        baseline_meta=snap_a.meta,
        current_meta=snap_b.meta,
    )
    changes = report.changes

    # ── Python runtime
    changes.extend(_diff_runtime(
        'Python', 'python.runtime',
        snap_a.python.get('python_version'),
        snap_b.python.get('python_version'),
    ))

    # ── Python packages — compare pip_installed (authoritative)
    pip_a = snap_a.python.get('packages', {}).get('pip_installed', {})
    pip_b = snap_b.python.get('packages', {}).get('pip_installed', {})
    changes.extend(_diff_pkg_map('python.packages', 'pip', pip_a, pip_b))

    # ── requirements.txt declared versions
    req_a = snap_a.python.get('packages', {}).get('requirements_txt', {})
    req_b = snap_b.python.get('packages', {}).get('requirements_txt', {})
    changes.extend(_diff_pkg_map('python.packages', 'requirements.txt', req_a, req_b))

    # ── Python lockfiles list
    changes.extend(_diff_list(
        'lockfiles', 'Python lockfile',
        snap_a.python.get('lockfiles', []),
        snap_b.python.get('lockfiles', []),
    ))

    # ── Node runtime
    changes.extend(_diff_runtime(
        'Node.js', 'node.runtime',
        snap_a.node.get('node_version'),
        snap_b.node.get('node_version'),
    ))

    # ── Node dependencies
    deps_a = snap_a.node.get('packages', {}).get('dependencies', {})
    deps_b = snap_b.node.get('packages', {}).get('dependencies', {})
    changes.extend(_diff_pkg_map('node.packages', 'npm dep', deps_a, deps_b))

    dev_a = snap_a.node.get('packages', {}).get('devDependencies', {})
    dev_b = snap_b.node.get('packages', {}).get('devDependencies', {})
    changes.extend(_diff_pkg_map('node.packages', 'npm devDep', dev_a, dev_b))

    # ── Node lockfiles
    changes.extend(_diff_list(
        'lockfiles', 'Node lockfile',
        snap_a.node.get('lockfiles', []),
        snap_b.node.get('lockfiles', []),
    ))

    # ── System runtimes (python already covered; check others)
    sys_runtimes_a = snap_a.system.get('runtimes', {})
    sys_runtimes_b = snap_b.system.get('runtimes', {})
    for name in sorted(set(sys_runtimes_a) | set(sys_runtimes_b)):
        if name == 'python':
            continue  # already covered
        changes.extend(_diff_runtime(
            name.capitalize(), 'system.runtime',
            sys_runtimes_a.get(name),
            sys_runtimes_b.get(name),
        ))

    # ── OS
    changes.extend(_diff_runtime(
        'OS', 'system.runtime',
        snap_a.system.get('os'),
        snap_b.system.get('os'),
    ))

    # ── Architecture
    changes.extend(_diff_runtime(
        'Arch', 'system.runtime',
        snap_a.system.get('arch'),
        snap_b.system.get('arch'),
    ))

    # ── Env vars
    changes.extend(_diff_env_vars(
        snap_a.system.get('env_vars', {}),
        snap_b.system.get('env_vars', {}),
    ))

    return report
