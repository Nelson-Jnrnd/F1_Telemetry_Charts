# Package Generation Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md`.

## Generate A Fixture-Backed Package

```powershell
python -m f1_telemetry_charts generate configs/bahrain-race.toml --json
```

The local package path loads the configured fixture dataset, runs each
configured recipe independently, writes successful chart artifacts, extracts
structured observations, writes review metadata, and writes a portable Markdown
draft into the deterministic output package directory. The example configuration
renders all four core recipes.

## Manifest Shape

The manifest includes:

- run ID and status
- framework version
- configuration hash
- source session identity
- requested recipe IDs
- produced artifacts with package-relative paths
- per-recipe produced or failed status
- package-relative observations, review, and Markdown draft paths
- warnings and errors

## Report Files

A successful package includes:

- `observations.json`: structured observations with evidence links, metric
  values, confidence, limitations, and review status.
- `review.json`: editable review metadata for generated observations.
- `draft.md`: a portable Markdown draft that references package-relative chart
  paths and excludes rejected observations.

Generated observations are descriptive. They do not make causal claims unless a
future observation rule explicitly supports that stronger interpretation.
