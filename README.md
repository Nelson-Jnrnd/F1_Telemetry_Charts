# F1 Telemetry Charts

This repository uses specification-first, AI-agent-led development. The
authoritative product scope lives in approved specs under `docs/specs/`.

## How This Project Works

- Features start with written, verifiable specifications under `docs/specs/`.
- Implementation starts only after spec approval.
- PRs must reference specs and requirement IDs.
- Governance checks protect spec consistency and documentation drift.

This README is derived documentation. If it conflicts with an approved spec, the
approved spec wins. See
[`docs/workflow/DOCUMENTATION_AUTHORITY.md`](docs/workflow/DOCUMENTATION_AUTHORITY.md).

## Start Here

- Agents: read [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md).
- Current spec: [`SPEC-001`](docs/specs/approved/SPEC-001-f1-analysis-framework.md).
- Workflow: [`AGENT_WORKFLOW.md`](docs/workflow/AGENT_WORKFLOW.md).
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Project Stack

- Distribution package: `f1-telemetry-charts`
- Import package: `f1_telemetry_charts`
- Minimum Python: 3.11
- Configuration formats currently supported: TOML and JSON
- Test runner: standard-library `unittest`

## Build And Test

```powershell
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_governance.py
python scripts/validate_specs.py
python scripts/validate_drift.py
```

## Manual Setup

Branch protection, required checks, and security features are not configured by
the repository itself. See
[`docs/workflow/REPOSITORY_ADMIN_SETUP.md`](docs/workflow/REPOSITORY_ADMIN_SETUP.md).
