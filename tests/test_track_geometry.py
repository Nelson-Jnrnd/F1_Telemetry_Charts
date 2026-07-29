from __future__ import annotations

import unittest

from f1_telemetry_charts.data import (
    CircuitCorner,
    CircuitInfo,
    DriverMetadata,
    LapRecord,
    SessionDataset,
    SessionMetadata,
    SourceProvenance,
    TelemetrySample,
)
from f1_telemetry_charts.analysis.track_map import build_track_map_payload
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.track_geometry import derive_canonical_track_geometry


class TrackGeometryTests(unittest.TestCase):
    def test_canonical_geometry_uses_best_session_trace(self) -> None:
        dataset = _dataset(
            telemetry=[
                _sample("PER", 1, 0, 0, 0),
                _sample("PER", 1, 200, 20, 20),
                _sample("VER", 2, 0, 0, 0),
                _sample("VER", 2, 125, 10, 20),
                _sample("VER", 2, 250, 20, 0),
            ]
        )

        geometry = derive_canonical_track_geometry(dataset)

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry.source_driver, "VER")
        self.assertEqual(geometry.source_lap, 2)
        self.assertEqual(geometry.original_sample_count, 3)
        self.assertEqual(geometry.point_count, 3)
        self.assertEqual(geometry.distance_bounds.maximum, 250)

    def test_canonical_geometry_downsamples_with_stable_endpoints(self) -> None:
        dataset = _dataset(
            telemetry=[
                _sample("VER", 1, distance, float(distance), float(distance % 3))
                for distance in range(5)
            ]
        )

        geometry = derive_canonical_track_geometry(dataset, max_points=3)

        self.assertIsNotNone(geometry)
        assert geometry is not None
        self.assertEqual(geometry.original_sample_count, 5)
        self.assertEqual(geometry.point_count, 3)
        self.assertTrue(geometry.downsampled)
        self.assertEqual([point.distance_m for point in geometry.points], [0, 2, 4])

    def test_track_map_projects_corner_without_fastf1_distance_by_geometry(self) -> None:
        dataset = _dataset(
            telemetry=[
                _sample("VER", 1, 0, 0, 0),
                _sample("VER", 1, 100, 10, 0),
                _sample("VER", 1, 200, 20, 0),
            ]
        )
        geometry = derive_canonical_track_geometry(dataset)
        assert geometry is not None
        dataset = dataset.model_copy(
            update={
                "track_geometry": geometry,
                "circuit_info": CircuitInfo(
                    source="fastf1_circuit_info",
                    reason="unit_test",
                    rotation_degrees=0,
                    corners=[
                        CircuitCorner(
                            number=1,
                            label="1",
                            x=10.4,
                            y=0,
                            angle_degrees=0,
                        )
                    ],
                ),
            },
            deep=True,
        )

        payload = build_track_map_payload(
            dataset,
            ChartRecipeConfig(
                recipe_id="telemetry_trace",
                parameters={
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": ["VER"],
                    }
                },
            ),
        )

        self.assertEqual(payload.status, "available")
        self.assertEqual(len(payload.corners), 1)
        self.assertEqual(payload.corners[0].projection_status, "nearest_geometry")
        self.assertEqual(payload.corners[0].distance_m, 100)
        self.assertGreater(payload.corners[0].projection_error or 0, 0)


def _dataset(*, telemetry: list[TelemetrySample]) -> SessionDataset:
    return SessionDataset(
        metadata=SessionMetadata(
            season=2023,
            event="Bahrain Grand Prix",
            session="Race",
        ),
        drivers=[
            DriverMetadata(abbreviation="VER"),
            DriverMetadata(abbreviation="PER"),
        ],
        laps=[
            LapRecord(driver="VER", lap_number=1),
            LapRecord(driver="VER", lap_number=2),
            LapRecord(driver="PER", lap_number=1),
        ],
        telemetry=telemetry,
        provenance=SourceProvenance(provider="fixture", cache_status="fixture"),
    )


def _sample(
    driver: str,
    lap_number: int,
    distance_m: float,
    x: float,
    y: float,
) -> TelemetrySample:
    return TelemetrySample(
        driver=driver,
        lap_number=lap_number,
        distance_m=distance_m,
        x=x,
        y=y,
    )


if __name__ == "__main__":
    unittest.main()
