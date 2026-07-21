# User Manual

This page is derived documentation. Authoritative requirements live in
`docs/specs/approved/SPEC-001-f1-analysis-framework.md`.

## What You Can Test

The current application is a local command-line chart and report package
generator. It is not a hosted web application. A test run validates a
configuration, loads the included Bahrain race fixture, renders the four core
chart recipes, extracts observations, writes review metadata, and creates a
portable Markdown draft under `runs/`.

## Quick Test

From the repository root, run:

```powershell
.\scripts\deploy_local_mvp.ps1
```

To open the generated output folder automatically:

```powershell
.\scripts\deploy_local_mvp.ps1 -Open
```

The script prints:

- the validation result
- the generation result
- the output directory
- the `manifest.json` path
- the `charts` directory path
- the `observations.json` path
- the `review.json` path
- the `draft.md` path

## Output Package

The demo configuration writes to:

```text
runs\2023-bahrain-race\2023-bahrain-race-15f7c590
```

The package contains:

- `manifest.json`: run status, session identity, recipe outcomes, artifact
  paths, report paths, warnings, and errors.
- `charts\*.png`: rendered chart images.
- `charts\*.json`: chart-level metadata for each PNG.
- `observations.json`: generated observations with evidence links, metrics,
  confidence, limitations, and review status.
- `review.json`: editable review metadata for generated observations.
- `draft.md`: portable Markdown draft for human editing.

Manifest artifact paths are package-relative, so the package can be moved as a
folder without rewriting metadata.

## Included Charts

The example configuration renders:

- `lap_time_delta`: lap-time comparison across selected drivers.
- `telemetry_trace`: speed trace from normalized telemetry samples.
- `tyre_strategy`: stint and tyre compound progression.
- `position_progression`: race-position progression by lap.

## Configuration

The default demo config is:

```text
configs\bahrain-race.toml
```

Important fields:

- `project_id`: controls the package name prefix.
- `output_dir`: controls where generated packages are written.
- `session`: season, event, and session identity.
- `driver_selection.drivers`: selected driver abbreviations.
- `data_cache.fixture_path`: points to the included offline fixture.
- `recipes`: chart recipe IDs to generate.
- `theme`: figure size, DPI, colors, and grid setting.

After changing the config, rerun:

```powershell
.\scripts\deploy_local_mvp.ps1 -ConfigPath configs\bahrain-race.toml
```

## Direct CLI Commands

The helper script runs these commands for you:

```powershell
python -m f1_telemetry_charts config validate configs\bahrain-race.toml --json
python -m f1_telemetry_charts generate configs\bahrain-race.toml --json
```

On this machine, `python` may resolve to the Windows Store alias. If that
happens, use the bundled runtime:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m f1_telemetry_charts generate configs\bahrain-race.toml --json
```

## Reviewing Observations

Open `observations.json` to inspect generated claims, evidence links, metrics,
confidence, and limitations. Open `review.json` to track whether each
observation is `unreviewed`, `accepted`, `edited`, or `rejected`.

The generated `draft.md` includes unreviewed, accepted, and edited
observations. Rejected observations are excluded when a draft is regenerated
through the report helpers.

## Troubleshooting

- If PowerShell blocks the script, run:

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_local_mvp.ps1
  ```

- If generation fails with a validation error, inspect the path-specific error
  in the JSON output and fix the referenced config field.
- If no charts appear, open `manifest.json` and check `status`, `errors`, and
  per-recipe entries.
- The fixture-backed demo does not require network access.
- Live FastF1 loading requires a populated or writable FastF1 cache and may be
  slower than the fixture demo.
