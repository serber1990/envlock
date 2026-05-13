"""
Environment collectors — Python, Node, and system-level dependencies.
Each collector returns a plain dict ready for JSON serialisation.
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def _run(cmd: list, cwd: str = None, timeout: int = 20) -> str:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return ''


# ── Python ────────────────────────────────────────────────────────────────────

def collect_python(path: str = '.') -> Dict:
    """
    Collects Python environment info for the given project path:
    - python version
    - pip packages (from pip list, requirements.txt, or pyproject.toml)
    - virtual env info if detected
    """
    result: Dict = {'python_version': None, 'packages': {}, 'lockfiles': [], 'venv': None}

    # Python version
    ver = _run(['python3', '--version'])
    if not ver:
        ver = _run(['python', '--version'])
    if ver:
        result['python_version'] = ver.strip().split()[-1]

    # detect venv
    venv_dirs = [Path(path) / d for d in ('.venv', 'venv', 'env') if (Path(path) / d).is_dir()]
    if venv_dirs:
        result['venv'] = str(venv_dirs[0])

    # installed packages via pip
    out = _run(['pip3', 'list', '--format=json'])
    if not out:
        out = _run(['pip', 'list', '--format=json'])
    if out:
        try:
            result['packages']['pip_installed'] = {
                p['name']: p['version'] for p in json.loads(out)
            }
        except (json.JSONDecodeError, KeyError):
            pass

    # requirements.txt
    req = Path(path) / 'requirements.txt'
    if req.is_file():
        result['lockfiles'].append('requirements.txt')
        pkgs = {}
        for line in req.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*([=<>!~]+.*)?$', line)
                if m:
                    pkgs[m.group(1)] = (m.group(2) or '').strip()
        if pkgs:
            result['packages']['requirements_txt'] = pkgs

    # pyproject.toml dependencies
    ppt = Path(path) / 'pyproject.toml'
    if ppt.is_file():
        result['lockfiles'].append('pyproject.toml')
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # fallback
            except ImportError:
                tomllib = None
        if tomllib:
            try:
                data = tomllib.loads(ppt.read_text())
                deps = data.get('project', {}).get('dependencies', [])
                pkgs = {}
                for dep in deps:
                    m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*([>=<!\~].*)?$', dep)
                    if m:
                        pkgs[m.group(1)] = (m.group(2) or '').strip()
                if pkgs:
                    result['packages']['pyproject_deps'] = pkgs
            except Exception:
                pass

    return result


# ── Node / npm ────────────────────────────────────────────────────────────────

def collect_node(path: str = '.') -> Dict:
    """
    Collects Node.js environment info:
    - node/npm versions
    - package.json dependencies + devDependencies
    - package-lock.json / yarn.lock presence and locked versions
    """
    result: Dict = {
        'node_version': None,
        'npm_version': None,
        'packages': {},
        'lockfiles': [],
    }

    ver = _run(['node', '--version'])
    if ver:
        result['node_version'] = ver.strip().lstrip('v')

    ver = _run(['npm', '--version'])
    if ver:
        result['npm_version'] = ver.strip()

    # package.json
    pkg_json = Path(path) / 'package.json'
    if pkg_json.is_file():
        result['lockfiles'].append('package.json')
        try:
            data = json.loads(pkg_json.read_text())
            if 'dependencies' in data:
                result['packages']['dependencies'] = data['dependencies']
            if 'devDependencies' in data:
                result['packages']['devDependencies'] = data['devDependencies']
        except json.JSONDecodeError:
            pass

    # package-lock.json — extract resolved versions
    lock = Path(path) / 'package-lock.json'
    if lock.is_file():
        result['lockfiles'].append('package-lock.json')
        try:
            data = json.loads(lock.read_text())
            locked = {}
            for name, info in data.get('packages', {}).items():
                if name.startswith('node_modules/'):
                    pkg = name[len('node_modules/'):]
                    locked[pkg] = info.get('version', '?')
            if locked:
                result['packages']['locked'] = locked
        except json.JSONDecodeError:
            pass

    # yarn.lock presence
    yarn = Path(path) / 'yarn.lock'
    if yarn.is_file():
        result['lockfiles'].append('yarn.lock')

    return result


# ── System ────────────────────────────────────────────────────────────────────

def collect_system() -> Dict:
    """
    Collects system-level language runtimes and env vars relevant to reproducibility.
    """
    result: Dict = {
        'os': None,
        'arch': None,
        'env_vars': {},
        'runtimes': {},
    }

    # OS info
    try:
        info = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                info[k] = v.strip().strip('"')
        result['os'] = f"{info.get('NAME', '?')} {info.get('VERSION_ID', '')}".strip()
    except Exception:
        pass

    arch = _run(['uname', '-m'])
    if arch:
        result['arch'] = arch.strip()

    # Runtimes
    for name, cmd in [
        ('python', ['python3', '--version']),
        ('node',   ['node', '--version']),
        ('ruby',   ['ruby', '--version']),
        ('go',     ['go', 'version']),
        ('java',   ['java', '-version']),
        ('rustc',  ['rustc', '--version']),
    ]:
        out = _run(cmd)
        if out:
            result['runtimes'][name] = out.strip().split('\n')[0]

    # Relevant env vars
    _ENV_KEYS = [
        'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV', 'NVM_DIR', 'NODE_ENV',
        'PYTHONPATH', 'GOPATH', 'JAVA_HOME', 'PATH',
    ]
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
