import json
import os
import sys

import pytest

from envlock import collectors
from envlock.collectors import collect_node, find_python, normalize_name, parse_requirement


@pytest.mark.parametrize("line, expected", [
    ("requests==2.31.0", ("requests", "==2.31.0")),
    ("Django >= 4.2, <5", ("django", ">= 4.2, <5")),
    ("requests[socks]>=2.31 ; python_version > '3.8'", ("requests", ">=2.31")),
    ("PyYAML", ("pyyaml", "")),
    ("typing_extensions~=4.0  # pinned for py3.8", ("typing-extensions", "~=4.0")),
    ("# a comment", None),
    ("-r base.txt", None),
    ("-e git+https://github.com/x/y.git#egg=y", None),
    ("", None),
])
def test_parse_requirement(line, expected):
    assert parse_requirement(line) == expected


def test_normalize_name():
    assert normalize_name("Py_YAML.Extra") == "py-yaml-extra"


def test_find_python_prefers_project_venv(tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n")
    py.chmod(0o755)
    assert find_python(str(tmp_path)) == str(py)


def test_collect_python_uses_project_interpreter(tmp_path, monkeypatch):
    monkeypatch.setattr(collectors, "find_python", lambda path: sys.executable)
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n-r other.txt\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["rich>=13"]\n')
    info = collectors.collect_python(str(tmp_path))
    assert info["interpreter"] == sys.executable
    assert info["python_version"] == ".".join(map(str, sys.version_info[:3]))
    assert info["packages"]["requirements_txt"] == {"flask": "==3.0.0"}
    if sys.version_info >= (3, 11):
        assert info["packages"]["pyproject_deps"] == {"rich": ">=13"}
    assert "pytest" in info["packages"]["pip_installed"]


def test_collect_node_lockfile_v3_and_v1(tmp_path, monkeypatch):
    monkeypatch.setattr(collectors, "_run", lambda *a, **k: "")
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4.17.21"}}))
    (tmp_path / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": {
        "": {}, "node_modules/lodash": {"version": "4.17.21"},
        "node_modules/a/node_modules/b": {"version": "1.0.0"},   # nested copies are ignored
    }}))
    info = collect_node(str(tmp_path))
    assert info["packages"]["dependencies"] == {"lodash": "^4.17.21"}
    assert info["packages"]["locked"] == {"lodash": "4.17.21"}

    (tmp_path / "package-lock.json").write_text(json.dumps({"lockfileVersion": 1, "dependencies": {
        "express": {"version": "4.18.2"}}}))
    assert collect_node(str(tmp_path))["packages"]["locked"] == {"express": "4.18.2"}


def test_java_version_is_read_from_stderr(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[0] == "java":
            return 'openjdk version "21.0.2" 2024-01-16\n' if kwargs.get("stderr") else ""
        return ""
    monkeypatch.setattr(collectors, "_run", fake_run)
    assert collectors.collect_system()["runtimes"] == {"java": 'openjdk version "21.0.2" 2024-01-16'}


def test_env_vars(monkeypatch):
    monkeypatch.setattr(collectors, "_run", lambda *a, **k: "")
    monkeypatch.setenv("NODE_ENV", "production")
    assert collectors.collect_system()["env_vars"]["NODE_ENV"] == "production"
    assert os.environ["PATH"] == collectors.collect_system()["env_vars"]["PATH"]
