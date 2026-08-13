# LLM Contract Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md` and
`docs/specs/implemented/SPEC-004-v2-analysis-workbench-pipeline.md`.

## Contract Version

The current LLM contract version is:

```text
1.0
```

Unsupported versions return a structured compatibility error with
`error.code = "unsupported_contract_version"`.

## Generate Charts

```python
from f1_telemetry_charts.llm import generate_charts

response = generate_charts(
    {
        "contract_version": "1.0",
        "config_path": "configs/bahrain-race.toml",
    }
)
print(response["status"])
print(response["manifest_path"])
print(response["observations_path"])
print(response["markdown_path"])
```

The response uses package-relative artifact and report paths. It does not
include environment variables, raw cache internals, or unrelated filesystem
paths.

## Describe An Artifact

```python
from f1_telemetry_charts.llm import describe_artifact

response = describe_artifact(
    {
        "contract_version": "1.0",
        "manifest_path": "runs/2023-bahrain-race/2023-bahrain-race-15f7c590/manifest.json",
        "artifact_id": "lap_time_delta-15f7c590",
    }
)
print(response["artifact"]["metadata"])
```

The caller supplies the local manifest path explicitly. The returned artifact
paths remain package-relative.

## Inspect An Analysis

```python
from f1_telemetry_charts.llm import inspect_analysis

response = inspect_analysis(
    {
        "contract_version": "1.0",
        "analysis_path": "analysis/bahrain-race",
    }
)
print(response["analysis"]["sessions"])
print(response["recipe_schemas"])
```

## Update Chart Parameters

```python
from f1_telemetry_charts.llm import update_analysis_chart_parameters

response = update_analysis_chart_parameters(
    {
        "contract_version": "1.0",
        "analysis_path": "analysis/bahrain-race/analysis.json",
        "chart_instance_id": "chart-abc123",
        "parameters": {"title": "Race pace delta"},
    }
)
print(response["status"])
```

`inspect_analysis` also returns bounded `strategy_summaries` for generated
strategy charts. They contain the schema version, analytical basis, headline
result fields, warnings, and limitations without returning unbounded lap or
timing streams. Value categories distinguish measured, derived, descriptive,
and reserved estimated values.

When report evidence exists, `report_summary.publication` exposes only bounded,
read-only readiness, selection-policy counts, section order, and editorial-field
presence. It does not expose raw result payloads or provide publication
mutation operations.
