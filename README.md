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
- Implemented specs: [`SPEC-001`](docs/specs/implemented/SPEC-001-f1-analysis-framework.md),
  [`SPEC-002`](docs/specs/implemented/SPEC-002-v2-plugin-preview-workbench.md),
  [`SPEC-003`](docs/specs/implemented/SPEC-003-v2-tailwind-ui-system.md),
  [`SPEC-004`](docs/specs/implemented/SPEC-004-v2-analysis-workbench-pipeline.md),
  [`SPEC-005`](docs/specs/implemented/SPEC-005-v2-chart-templates-and-presets.md),
  [`SPEC-006`](docs/specs/implemented/SPEC-006-analyst-grade-chart-parameters.md),
  and [`SPEC-007`](docs/specs/implemented/SPEC-007-track-map-range-and-race-playback.md).
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
python scripts/benchmark_mvp.py
python scripts/benchmark_v1.py
cd frontend
pnpm build
cd ..
python scripts/validate_governance.py
python scripts/validate_specs.py
python scripts/validate_drift.py
```

With a populated FastF1 smoke cache, the cache-only data-load benchmark is:

```powershell
python scripts/benchmark_fastf1_cache.py --cache-dir .cache\fastf1-smoke
```

Launch the local V2 preview UI for a generated package:

```powershell
python -m f1_telemetry_charts preview runs\2023-bahrain-race --no-browser
```

## Usage Docs

- [User manual](docs/usage/user-manual.md)
- [Configuration](docs/usage/configuration.md)
- [Data gateway](docs/usage/data-gateway.md)
- [Charts](docs/usage/charts.md)
- [Package generation](docs/usage/generation.md)
- [LLM contract](docs/usage/llm-contract.md)

## Manual Setup

Branch protection, required checks, and security features are not configured by
the repository itself. See
[`docs/workflow/REPOSITORY_ADMIN_SETUP.md`](docs/workflow/REPOSITORY_ADMIN_SETUP.md).
