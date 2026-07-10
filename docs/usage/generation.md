# Package Generation Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/approved/SPEC-001-f1-analysis-framework.md`.

## Generate A Fixture-Backed Package

```powershell
python -m f1_telemetry_charts generate configs/bahrain-race.toml --json
```

The current MVP path loads the configured fixture dataset, runs each configured
recipe independently, writes successful chart artifacts, and writes a
`manifest.json` file into the deterministic output package directory. The
example configuration renders all four MVP recipes.

## Manifest Shape

The manifest includes:

- run ID and status
- framework version
- configuration hash
- source session identity
- requested recipe IDs
- produced artifacts with package-relative paths
- per-recipe produced or failed status
- warnings and errors
