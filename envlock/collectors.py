"""
Environment collectors — Python, Node, and system-level dependencies.
Each collector returns a plain dict ready for JSON serialisation.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional


def _run(cmd: list, cwd: Optional[str] = None, timeout: int = 60, stderr: bool = False) -> str:
    """Run a command and return its stdout ('' on any failure). With stderr=True, include stderr."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return (r.stdout + r.stderr) if stderr else r.stdout


def normalize_name(name: str) -> str:
    """PEP 503 normalisation: 'PyYAML', 'pyyaml', 'py_yaml' → 'pyyaml' / 'py-yaml'."""
    return re.sub(r'[-_.]+', '-', name).lower()


_REQ_RE = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;]*)')


def parse_requirement(line: str) -> Optional[tuple]:
    """
    Parse one requirement ('requests[socks]>=2.31 ; python_version>"3.8"  # note')
    into (normalized_name, spec). Returns None for blank lines, comments and options.
    """
    line = line.split(' #', 1)[0].strip()
    if not line or line.startswith(('#', '-')) or '://' in line:
        return None
    m = _REQ_RE.match(line)
    if not m:
        return None
    return normalize_name(m.group(1)), m.group(3).strip()

# ── Python ────────────────────────────────────────────────────────────────────

def find_python(path: str = '.') -> Optional[str]:
    """
    The interpreter whose packages describe the project:
    a virtualenv inside the project, then the active $VIRTUAL_ENV, then python3 on PATH.
    """
    candidates = [Path(path) / d / 'bin' / 'python' for d in ('.venv', 'venv', 'env')]
    if os.environ.get('VIRTUAL_ENV'):
        candidates.append(Path(os.environ['VIRTUAL_ENV']) / 'bin' / 'python')
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return shutil.which('python3') or shutil.which('python')


def collect_python(path: str = '.') -> Dict:
    """
    Python environment of the project at `path`:
    interpreter + version, installed packages (pip), requirements.txt and pyproject.toml deps.
    """
    result: Dict = {'python_version': None, 'interpreter': None, 'venv': None,
                    'packages': {}, 'lockfiles': []}

    python = find_python(path)
    if python:
        result['interpreter'] = python
        venv = Path(python).parent.parent
        if (venv / 'pyvenv.cfg').is_file():
            result['venv'] = str(venv)
        ver = _run([python, '--version'], stderr=True).strip()
        if ver:
            result['python_version'] = ver.split()[-1]
        out = _run([python, '-m', 'pip', 'list', '--format=json', '--disable-pip-version-check'])
        try:
            result['packages']['pip_installed'] = {
                normalize_name(p['name']): p['version'] for p in json.loads(out)
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    req = Path(path) / 'requirements.txt'
    if req.is_file():
        result['lockfiles'].append('requirements.txt')
        pkgs = dict(filter(None, (parse_requirement(line)
                                  for line in req.read_text(errors='replace').splitlines())))
        if pkgs:
            result['packages']['requirements_txt'] = pkgs

    ppt = Path(path) / 'pyproject.toml'
    if ppt.is_file():
        result['lockfiles'].append('pyproject.toml')
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                tomllib = None
        if tomllib:
            try:
                data = tomllib.loads(ppt.read_text())
            except (tomllib.TOMLDecodeError, UnicodeDecodeError):
                data = {}
            deps = data.get('project', {}).get('dependencies', [])
            pkgs = dict(filter(None, (parse_requirement(d) for d in deps)))
            if pkgs:
                result['packages']['pyproject_deps'] = pkgs

    return result

# ── Node / npm ────────────────────────────────────────────────────────────────

def collect_node(path: str = '.') -> Dict:
    """
    Node.js environment: node/npm versions, package.json deps + devDeps,
    package-lock.json resolved versions and yarn.lock presence.
    """
    result: Dict = {'node_version': None, 'npm_version': None, 'packages': {}, 'lockfiles': []}

    ver = _run(['node', '--version']).strip()
    if ver:
        result['node_version'] = ver.lstrip('v')
    ver = _run(['npm', '--version']).strip()
    if ver:
        result['npm_version'] = ver

    pkg_json = Path(path) / 'package.json'
    if pkg_json.is_file():
        result['lockfiles'].append('package.json')
        try:
            data = json.loads(pkg_json.read_text())
            for key in ('dependencies', 'devDependencies'):
                if isinstance(data.get(key), dict):
                    result['packages'][key] = data[key]
        except json.JSONDecodeError:
            pass

    lock = Path(path) / 'package-lock.json'
    if lock.is_file():
        result['lockfiles'].append('package-lock.json')
        try:
            data = json.loads(lock.read_text())
            locked = {}
            # lockfileVersion 2/3: "packages" keyed by "node_modules/<name>"
            for name, info in data.get('packages', {}).items():
                if name.startswith('node_modules/') and '/node_modules/' not in name:
                    locked[name[len('node_modules/'):]] = info.get('version', '?')
            # lockfileVersion 1: nested "dependencies"
            if not locked:
                for name, info in data.get('dependencies', {}).items():
                    locked[name] = info.get('version', '?')
            if locked:
                result['packages']['locked'] = locked
        except json.JSONDecodeError:
            pass

    if (Path(path) / 'yarn.lock').is_file():
        result['lockfiles'].append('yarn.lock')

    return result

# ── System ────────────────────────────────────────────────────────────────────

_RUNTIMES = [
    ('python', ['python3', '--version']),
    ('node',   ['node', '--version']),
    ('ruby',   ['ruby', '--version']),
    ('go',     ['go', 'version']),
    ('java',   ['java', '-version']),     # prints to stderr
    ('rustc',  ['rustc', '--version']),
]

_ENV_KEYS = [
    'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV', 'NVM_DIR', 'NODE_ENV',
    'PYTHONPATH', 'GOPATH', 'JAVA_HOME', 'PATH',
]


def collect_system() -> Dict:
    """OS, architecture, language runtimes and environment variables relevant to reproducibility."""
    result: Dict = {'os': None, 'arch': None, 'env_vars': {}, 'runtimes': {}}

    try:
        info = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                info[k] = v.strip().strip('"')
        result['os'] = f"{info.get('NAME', '?')} {info.get('VERSION_ID', '')}".strip()
    except OSError:
        import platform
        result['os'] = f"{platform.system()} {platform.release()}".strip() or None

    arch = _run(['uname', '-m']).strip()
    if arch:
        result['arch'] = arch

    for name, cmd in _RUNTIMES:
        out = _run(cmd, stderr=True).strip()
        if out:
            result['runtimes'][name] = out.splitlines()[0]

    for k in _ENV_KEYS:
        v = os.environ.get(k)
        if v:
            result['env_vars'][k] = v

    return result

# ── Unified snapshot ──────────────────────────────────────────────────────────

def collect_all(path: str = '.') -> Dict:
    return {
        'python': collect_python(path),
        'node':   collect_node(path),
        'system': collect_system(),
    }
