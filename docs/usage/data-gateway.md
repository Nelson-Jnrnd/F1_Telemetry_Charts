# Data Gateway Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md`.

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

FastF1-backed loading is covered by mocked unit tests and can be used for live
or cache-only smoke checks. The repository remains testable without network
access because the default unit tests use fixtures and mocked FastF1-shaped
objects.

Cache-only FastF1 loading enables FastF1 offline mode for the duration of the
gateway call. The canonical 2023 Bahrain Race for VER and PER measured 9.0840
seconds on 2026-07-10 with `fetched_from_network=false`, which satisfies the
current SPEC-001 NFR-110 maximum of 10 seconds.
