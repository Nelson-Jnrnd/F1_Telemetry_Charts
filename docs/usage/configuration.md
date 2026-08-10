# Configuration Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md`.

## Validate a configuration

```powershell
python -m f1_telemetry_charts config validate configs/bahrain-race.toml
python -m f1_telemetry_charts config validate configs/bahrain-race.toml --json
```

The MVP scaffold supports `.toml` and `.json` configuration files. YAML support
is intentionally deferred until the project adds a YAML parser dependency.

## Minimal Python usage

```python
from f1_telemetry_charts import load_config

config = load_config("configs/bahrain-race.toml")
print(config.project_id)
```

Strategy templates use the same normalized `chart`, `selection`, `filters`,
`analysis`, and `presentation` parameter sections as existing charts. Their
shared `strategy_exclusion_policy` defaults to excluding race lap 1, pit-in/
out, deleted, generated, explicitly inaccurate, and non-green laps. Missing
track-status coverage keeps otherwise valid laps eligible with a warning.
`require_complete_sectors` is an optional advanced override. Requested and
effective policy values are persisted in every strategy artifact.
