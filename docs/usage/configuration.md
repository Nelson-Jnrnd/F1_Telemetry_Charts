# Configuration Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/approved/SPEC-001-f1-analysis-framework.md`.

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
