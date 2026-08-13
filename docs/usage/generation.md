# Package Generation Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md` and
`docs/specs/approved/SPEC-010-publication-ready-race-session-reports.md`.

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

The Analysis working package adds internal review artifacts:

- `draft.md`: clean reader-facing publication Markdown.
- `analyst-report.md`: the internal evidence-oriented rendering.
- `publication-plan.json`: deterministic claim and chart placement metadata.
- `evidence.json`: machine-readable results, assessments, findings, and review.
- web-ready chart assets referenced by package-relative paths.

The manifest records publication readiness and package-relative paths for both
renderings and the evidence sidecar.

The separate publication export is the clean web handoff and contains only:

- `article.md`: the exact reader-facing Markdown.
- `article.json`: the same selected article structure in machine-readable form;
  each published claim paragraph and At a Glance item carries its canonical
  `claim_id`.
- `evidence.json`: results, assessments, findings, reviews, and the explicit
  `publication_placements` bridge back from the article to those findings.
  Selected chart evidence uses `reference_scope: package` and resolvable
  `assets/` paths. Evidence retained only from the Analysis workspace uses
  `reference_scope: source_analysis` with explicit `source_*_path` fields.
- `manifest.json`: selected-asset integrity and publication readiness.
- `assets/`: only the selected web-oriented chart images and metadata.
