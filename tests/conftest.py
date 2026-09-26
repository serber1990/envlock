import copy

import pytest

BASE = {
    "meta": {"captured_at": "2026-05-10T09:00:00+00:00", "hostname": "dev", "project_path": "/srv/app"},
    "python": {
        "python_version": "3.12.1",
        "packages": {
            "pip_installed": {"requests": "2.31.0", "urllib3": "2.0.7", "flask": "3.0.0"},
            "requirements_txt": {"requests": ">=2.28"},
            "pyproject_deps": {"flask": ">=3"},
        },
        "lockfiles": ["requirements.txt", "pyproject.toml"],
    },
    "node": {
        "node_version": "20.11.1",
        "packages": {"dependencies": {"lodash": "^4.17.21"}, "locked": {"lodash": "4.17.21"}},
        "lockfiles": ["package.json", "package-lock.json"],
    },
    "system": {
        "os": "Ubuntu 24.04", "arch": "x86_64",
        "runtimes": {"go": "go version go1.22.1 linux/amd64"},
        "env_vars": {"NODE_ENV": "production", "PATH": "/usr/bin"},
    },
}


@pytest.fixture
def base():
    return copy.deepcopy(BASE)
