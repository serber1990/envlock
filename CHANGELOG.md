# Changelog

## 1.1.0

### Fixed
- `envlock check --format json` printed progress messages on stdout, so the output was not valid JSON
  (the README's `| jq` example failed). Progress and errors now go to stderr.
- `--output` was silently ignored for JSON reports.
- Packages were read from the global `pip3`, not from the project: the project's `.venv`/`venv`/`env`
  (or the active `$VIRTUAL_ENV`) is now used.
- Java was never detected (`java -version` prints to stderr).
- `pyproject.toml` dependencies and `package-lock.json` resolved versions were collected but never compared.
- Severities did not match the documentation: upgrades are now INFO and downgrades WARNING.
- `requirements.txt` lines with extras, environment markers or inline comments were dropped.
- Terminal colors are disabled when the output is piped or `NO_COLOR` is set.

### Added
- `--fail-on info|warning|critical|never` to choose which drift fails a CI job.
- Exit code 2 for errors (missing or invalid baseline), distinct from 1 = drift detected.
- Runtime changes are graded: Python/Node major.minor change is CRITICAL, a patch release is WARNING.
- `package-lock.json` v1 support and yarn.lock detection.
- `python -m envlock`.
- Test suite and GitHub Actions CI.

### Changed
- Package names are normalised (PEP 503) so `PyYAML` and `pyyaml` compare equal.
- Requires Python 3.9+ (`tomli` is installed automatically on 3.9/3.10 for `pyproject.toml` parsing).

## 1.0.0

- Initial release (published on PyPI as `env-drift`; the `envlock` name was taken).
