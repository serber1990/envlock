# envlock

[![CI](https://github.com/serber1990/envlock/actions/workflows/ci.yml/badge.svg)](https://github.com/serber1990/envlock/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/envlock-cli.svg)](https://badge.fury.io/py/envlock-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Freeze your environment. Detect when it drifts.

**envlock** snapshots a project's Python packages, Node.js dependencies and system runtimes, then tells you
exactly what changed — so "works on my machine" stops being an excuse. Use it locally, in CI, or to compare
staging with production.

---

## ✨ What it tracks

| Layer | What's captured |
|-------|----------------|
| **Python** | Interpreter and version (the project's `.venv` / `venv` / `env`, or the active virtualenv), installed packages, `requirements.txt`, `pyproject.toml` dependencies |
| **Node.js** | Node and npm versions, `package.json` dependencies + devDependencies, `package-lock.json` resolved versions, `yarn.lock` presence |
| **System** | OS, architecture, Go / Ruby / Java / Rust versions, relevant env vars (`VIRTUAL_ENV`, `NODE_ENV`, `JAVA_HOME`…) |

### Severity levels

| Severity | Examples |
|----------|----------|
| ⛔ **CRITICAL** | Python/Node major or minor version changed (3.12 → 3.13), OS or architecture changed |
| ⚠️ **WARNING** | Package removed or downgraded, declared constraint changed, runtime patch release, lockfile or env var removed |
| ℹ️ **INFO** | Package added or upgraded, new lockfile or env var |

---

## 📥 Installation

```bash
pip install envlock-cli     # the command is `envlock`
```

---

## 🛠 Usage

### 1 — Take a baseline snapshot

```bash
envlock snapshot                          # saves .envlock.json in the current directory
envlock snapshot --path /srv/myapp        # scan another project
envlock snapshot --output locks/prod.json # custom location
```

### 2 — Check for drift

```bash
envlock check                                        # terminal report
envlock check --format json | jq .summary            # JSON on stdout (progress goes to stderr)
envlock check --format markdown -o drift-report.md      # Markdown report file
envlock check --baseline locks/prod.json --fail-on critical
```

### 3 — Diff any two snapshots

```bash
envlock diff staging.json production.json
envlock diff before.json after.json --format markdown -o drift.md
```

---

## 📄 Example output

```
  ╔════════════════════════════════════════╗
  ║  envlock  ·  environment drift report  ║
  ╚════════════════════════════════════════╝

  Baseline   2026-05-10T09:00:00+00:00  (dev-laptop)  /srv/app
  Current    2026-05-12T14:22:18+00:00  (dev-laptop)  /srv/app


  ── Python Runtime ────────────────────────────
  ⛔ ~  Python version changed  3.12.1 → 3.13.0

  ── Python Packages ───────────────────────────
  · +  pip: httpx added  0.27.0
  · ~  pip: requests upgraded  2.31.0 → 2.32.3
  ⚠  ~  pip: urllib3 downgraded  2.0.7 → 1.26.18

  ── Node.js Packages ──────────────────────────
  · +  npm dep: express added  ^4.19.2

  ────────────────────────────────────────────
  5 changes detected  (1 critical, 1 warning, 3 info)
```

---

## 🔁 Use in CI

The exit code tells your pipeline what happened:

| Exit code | Meaning |
|-----------|---------|
| `0` | No drift at or above `--fail-on` |
| `1` | Drift detected |
| `2` | Error (missing or invalid baseline, unreadable path) |

```yaml
# GitHub Actions — fail only on critical drift, keep the report as an artifact
- name: Check environment drift
  run: envlock check --baseline .envlock.json --fail-on critical --format markdown -o drift-report.md
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: drift-report
    path: drift-report.md
```

---

## 📋 Options

### `envlock snapshot`
| Option | Description |
|--------|-------------|
| `-p`, `--path DIR` | Project directory to scan (default: `.`) |
| `-o`, `--output FILE` | Where to save the baseline (default: `.envlock.json`) |

### `envlock check` / `envlock diff BASELINE CURRENT`
| Option | Description |
|--------|-------------|
| `-b`, `--baseline FILE` | *(check)* Baseline to compare against (default: `.envlock.json`) |
| `-p`, `--path DIR` | *(check)* Project directory to scan (default: `.`) |
| `-f`, `--format` | `terminal` (default), `json` or `markdown` |
| `-o`, `--output FILE` | Write the report to a file (JSON or Markdown) |
| `--fail-on LEVEL` | `info` (default: any change), `warning`, `critical` or `never` |

---

## 🧪 Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.

---

## 📝 License

MIT — see [LICENSE](LICENSE).

## 🌐 Connect

[![GitHub](https://img.shields.io/badge/GitHub-@serber1990-181717?style=flat-square&logo=github)](https://github.com/serber1990)
