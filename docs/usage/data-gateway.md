# Data Gateway Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/approved/SPEC-001-f1-analysis-framework.md`.

## Fixture Gateway

The fixture gateway provides deterministic offline data for tests and examples.

```python
from pathlib import Path

from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FixtureSessionGateway

gateway = FixtureSessionGateway(Path("tests/fixtures/2023_bahrain_race_dataset.json"))
dataset = gateway.load_session(
    SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=["VER", "PER"],
    )
)
```

The returned `SessionDataset` contains normalized metadata, drivers, laps,
telemetry samples, weather samples, source provenance, and missing-data entries.

## FastF1 Gateway

`FastF1SessionGateway` is a lazy dependency boundary. Importing framework data
models, recipes, or config modules does not import FastF1. FastF1 is imported
only when `FastF1SessionGateway.load_session(...)` is called.

FastF1-backed loading is intentionally not used by the default unit tests, so
the repository remains testable without network access.
