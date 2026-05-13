# envlock

[![PyPI version](https://badge.fury.io/py/env-drift.svg)](https://badge.fury.io/py/env-drift)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Freeze your environment. Detect when it drifts.

**envlock** snapshots your Python packages, Node.js dependencies, and system runtimes, then tells you exactly what changed — so "works on my machine" stops being an excuse.

---

## ✨ What it tracks

| Layer | What's captured |
|-------|----------------|
| **Python** | Runtime version, all installed packages (pip), `requirements.txt`, `pyproject.toml` dependencies |
| **Node.js** | Runtime version, npm version, `package.json` deps + devDeps, `package-lock.json` locked versions |
| **System** | OS, architecture, language runtimes (Go, Ruby, Java, Rust…), key env vars |

### Severity levels

| Severity | Examples |
|----------|----------|
| ⛔ **CRITICAL** | Python/Node runtime version changed, OS changed |
| ⚠️ **WARNING** | Package removed, version downgraded, env var removed |
| ℹ️ **INFO** | Package added or upgraded |

---

## 📥 Installation

```bash
pip install env-drift
```

---

## 🛠 Usage

### 1 — Take a baseline snapshot

```bash
envlock snapshot
```

Saves `.envlock.json` in the current directory.

```bash
# Scan a specific project directory
envlock snapshot --path /srv/myapp

# Custom output path
envlock snapshot --output /opt/locks/prod-2026-05-12.json
```

### 2 — Check for drift

```bash
envlock check
```

```bash
# JSON output (for CI scripts)
envlock check --format json

# Markdown report to file
envlock check --format markdown --output env-drift.md

# Against a specific baseline
envlock check --baseline /opt/locks/prod-2026-05-12.json
```

### 3 — Diff any two snapshots

```bash
envlock diff before.json after.json
envlock diff staging.json production.json --format markdown
```

---

## 📋 Options

### `envlock snapshot`
| Option | Description |
|--------|-------------|
| `--path DIR` | Project directory to scan (default: `.`) |
| `--output FILE` | Where to save the baseline (default: `.envlock.json`) |

### `envlock check`
| Option | Description |
|--------|-------------|
| `--baseline FILE` | Baseline to compare against (default: `.envlock.json`) |
| `--path DIR` | Project directory to scan (default: `.`) |
| `--format` | `terminal` (default), `json`, or `markdown` |
| `--output FILE` | Save report to file (markdown only) |

### `envlock diff`
| Option | Description |
|--------|-------------|
| `BASELINE` | First snapshot file |
| `CURRENT` | Second snapshot file |
| `--format` | `terminal` (default), `json`, or `markdown` |
| `--output FILE` | Save report to file (markdown only) |

---

## 📄 Example output

```
  ╔═══════════════════════════════════════════════╗
  ║  envlock  ·  environment drift report         ║
  ╚═══════════════════════════════════════════════╝

  Baseline   2026-05-10 09:00:00  (dev-laptop)  /srv/myapp
  Current    2026-05-12 14:22:18  (dev-laptop)  /srv/myapp

  ── Python Runtime ─────────────────────────────────────
  ⛔ ~  Python version changed  3.11.4 → 3.12.0

  ── Python Packages ────────────────────────────────────
  ⚠  ~  pip: requests version changed  2.28.0 → 2.31.0
  ·  +  pip: httpx added  0.25.0
  ⚠  -  pip: urllib3 removed  was 1.26.18

  ── Node.js Packages ───────────────────────────────────
  ·  +  npm dep: lodash added  ^4.17.21

  ────────────────────────────────────────────────────────
  5 changes detected  (1 critical, 2 warnings, 2 info)
```

---

## 🔁 Use in CI

```bash
# Fail the build on environment drift
envlock check --format json | jq '.summary.critical > 0'
```

```yaml
# GitHub Actions example
- name: Check environment drift
  run: envlock check --format json --output env-drift.json
  continue-on-error: false
```

---

## 📝 License

MIT — see [LICENSE](LICENSE).

## 🌐 Connect

[![GitHub](https://img.shields.io/badge/GitHub-@serber1990-181717?style=flat-square&logo=github)](https://github.com/serber1990)
