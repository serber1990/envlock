from envlock.diff import diff_snapshots
from envlock.snapshot import EnvSnapshot


def changes(a, b):
    report = diff_snapshots(EnvSnapshot(a), EnvSnapshot(b))
    return {(c.description, c.severity) for c in report.changes}, report


def test_identical_snapshots_are_clean(base):
    _, report = changes(base, base)
    assert report.is_clean and not report.has_at_least("INFO")


def test_package_upgrade_downgrade_add_remove(base):
    cur = __import__("copy").deepcopy(base)
    pip = cur["python"]["packages"]["pip_installed"]
    pip["requests"] = "2.32.0"      # upgrade
    pip["urllib3"] = "1.26.18"      # downgrade
    del pip["flask"]                # removed
    pip["httpx"] = "0.27.0"         # added
    found, report = changes(base, cur)
    assert ("pip: requests upgraded", "INFO") in found
    assert ("pip: urllib3 downgraded", "WARNING") in found
    assert ("pip: flask removed", "WARNING") in found
    assert ("pip: httpx added", "INFO") in found
    assert report.has_at_least("WARNING") and not report.has_at_least("CRITICAL")


def test_runtime_minor_is_critical_patch_is_warning(base):
    cur = __import__("copy").deepcopy(base)
    cur["python"]["python_version"] = "3.12.4"
    assert ("Python version changed", "WARNING") in changes(base, cur)[0]
    cur["python"]["python_version"] = "3.13.0"
    assert ("Python version changed", "CRITICAL") in changes(base, cur)[0]


def test_declared_constraints_and_lockfile(base):
    cur = __import__("copy").deepcopy(base)
    cur["python"]["packages"]["pyproject_deps"]["flask"] = ">=3.1"
    cur["node"]["packages"]["locked"]["lodash"] = "4.17.20"
    cur["node"]["lockfiles"].remove("package-lock.json")
    found, _ = changes(base, cur)
    assert ("pyproject: flask constraint changed", "WARNING") in found
    assert ("npm locked: lodash downgraded", "WARNING") in found
    assert ("Node lockfile: package-lock.json removed", "WARNING") in found


def test_os_and_arch_are_critical(base):
    cur = __import__("copy").deepcopy(base)
    cur["system"]["os"] = "Ubuntu 26.04"
    cur["system"]["arch"] = "aarch64"
    found, _ = changes(base, cur)
    assert ("OS version changed", "CRITICAL") in found
    assert ("Architecture version changed", "CRITICAL") in found


def test_path_is_ignored_other_env_vars_tracked(base):
    cur = __import__("copy").deepcopy(base)
    cur["system"]["env_vars"]["PATH"] = "/opt/bin:/usr/bin"
    cur["system"]["env_vars"]["NODE_ENV"] = "development"
    found, _ = changes(base, cur)
    assert found == {("Env var changed: NODE_ENV", "WARNING")}


def test_old_snapshots_without_new_fields(base):
    old = {"meta": {}, "python": {"python_version": "3.12.1"}, "node": {}, "system": {}}
    _, report = changes(old, base)
    assert report.changes  # no KeyError, differences reported
