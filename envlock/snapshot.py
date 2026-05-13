"""
EnvSnapshot — captures, saves, and loads an environment state.
"""
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .collectors import collect_all

VERSION = "1.0.0"
DEFAULT_PATH = Path('.envlock.json')


class EnvSnapshot:
    def __init__(self, data: dict):
        self._data = data

    @property
    def meta(self) -> dict:
        return self._data.get('meta', {})

    @property
    def python(self) -> dict:
        return self._data.get('python', {})

    @property
    def node(self) -> dict:
        return self._data.get('node', {})

    @property
    def system(self) -> dict:
        return self._data.get('system', {})

    def to_dict(self) -> dict:
        return self._data

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path: Path) -> 'EnvSnapshot':
        path = Path(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        return cls(data)


def take_snapshot(path: str = '.', verbose: bool = False) -> EnvSnapshot:
    _v = print if verbose else lambda *_: None

    _v('  Collecting Python environment...')
    env = collect_all(path)

    env['meta'] = {
        'captured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'hostname': socket.gethostname(),
        'project_path': str(Path(path).resolve()),
        'envlock_version': VERSION,
    }

    return EnvSnapshot(env)
