import json

import pytest

from envlock import cli
from envlock.snapshot import EnvSnapshot


def run(capsys, *argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(list(argv))
    out = capsys.readouterr()
    return exc.value.code, out.out, out.err


@pytest.fixture
def files(tmp_path, base):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    EnvSnapshot(base).save(a)
    base["python"]["packages"]["pip_installed"]["requests"] = "2.32.0"   # INFO only
    EnvSnapshot(base).save(b)
    return a, b


def test_diff_json_is_clean_on_stdout(capsys, files):
    code, out, err = run(capsys, "diff", *map(str, files), "--format", "json")
    data = json.loads(out)
    assert code == 1
    assert data["summary"] == {"total": 1, "critical": 0, "warnings": 0, "info": 1}


def test_fail_on_threshold(capsys, files):
    assert run(capsys, "diff", *map(str, files), "--fail-on", "warning")[0] == 0
    assert run(capsys, "diff", *map(str, files), "--fail-on", "never")[0] == 0
    assert run(capsys, "diff", *map(str, files))[0] == 1


def test_output_file_for_json_and_markdown(capsys, files, tmp_path):
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    run(capsys, "diff", *map(str, files), "-f", "json", "-o", str(out_json))
    assert json.loads(out_json.read_text())["summary"]["total"] == 1
    run(capsys, "diff", *map(str, files), "-o", str(out_md))    # format inferred from .md
    assert out_md.read_text().startswith("# envlock")


def test_terminal_report_is_plain_when_piped(capsys, files):
    code, out, _ = run(capsys, "diff", *map(str, files))
    assert "pip: requests upgraded" in out and "\033[" not in out


def test_check_uses_baseline(capsys, tmp_path, monkeypatch, base):
    baseline = tmp_path / ".envlock.json"
    EnvSnapshot(base).save(baseline)
    monkeypatch.setattr(cli, "take_snapshot", lambda path: EnvSnapshot(base))
    code, out, err = run(capsys, "check", "-b", str(baseline), "-f", "json")
    assert code == 0 and json.loads(out)["summary"]["total"] == 0
    assert "Collecting" in err


def test_snapshot_writes_file(capsys, tmp_path, monkeypatch, base):
    monkeypatch.setattr(cli, "take_snapshot", lambda path: EnvSnapshot(base))
    target = tmp_path / "locks" / "prod.json"
    code, out, _ = run(capsys, "snapshot", "-o", str(target))
    assert code == 0 and json.loads(target.read_text())["python"]["python_version"] == "3.12.1"
    assert "Python   : 3.12.1" in out


def test_errors_exit_2(capsys, tmp_path):
    code, _, err = run(capsys, "check", "-b", str(tmp_path / "missing.json"))
    assert code == 2 and "Baseline not found" in err
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    code, _, err = run(capsys, "diff", str(bad), str(bad))
    assert code == 2 and "Cannot read snapshot" in err
    code, _, err = run(capsys, "snapshot", "--path", str(tmp_path / "nope"))
    assert code == 2
