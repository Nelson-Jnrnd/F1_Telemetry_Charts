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
    TrackGeometry,
    TrackGeometryBounds,
    TrackGeometryPoint,
)
from f1_telemetry_charts.analysis.track_map import build_track_map_payload
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.track_geometry import (
    derive_canonical_track_geometry,
    ensure_track_geometry,
)


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
                _sample("VER", 1, 200, 0, 0),
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

    def test_median_geometry_weights_drivers_equally_and_closes_seam(self) -> None:
        laps = [
            LapRecord(driver="VER", lap_number=1, lap_time_seconds=90),
            LapRecord(driver="VER", lap_number=2, lap_time_seconds=91),
            LapRecord(driver="PER", lap_number=1, lap_time_seconds=92),
        ]
        telemetry = [
            *_trace("VER", 1, length=100, middle_y=0, finish_x=10),
            *_trace("VER", 2, length=100, middle_y=2, finish_x=10),
            *_trace("PER", 1, length=100, middle_y=10, finish_x=10),
        ]

        dataset = _dataset(telemetry=telemetry, laps=laps)
        geometry = derive_canonical_track_geometry(dataset, max_points=3)
        repeated = derive_canonical_track_geometry(dataset, max_points=3)

        assert geometry is not None
        self.assertEqual(geometry.algorithm_version, 2)
        self.assertEqual(
            geometry.aggregation_method,
            "per_driver_then_session_coordinate_median",
        )
        self.assertIsNone(geometry.source_driver)
        self.assertIsNone(geometry.source_lap)
        self.assertEqual(geometry.contributing_driver_count, 2)
        self.assertEqual(geometry.contributing_lap_count, 3)
        self.assertAlmostEqual(geometry.points[1].y, 5.5)
        self.assertEqual(geometry.points[0].x, geometry.points[-1].x)
        self.assertEqual(geometry.points[0].y, geometry.points[-1].y)
        self.assertAlmostEqual(geometry.original_closure_gap, 10.0)
        self.assertTrue(geometry.closure_adjusted)
        self.assertEqual(geometry, repeated)

    def test_median_geometry_normalizes_unequal_lap_lengths(self) -> None:
        laps = [
            LapRecord(driver="VER", lap_number=1, lap_time_seconds=90),
            LapRecord(driver="PER", lap_number=1, lap_time_seconds=91),
        ]
        telemetry = [
            *[
                sample.model_copy(update={"distance_m": sample.distance_m + 5})
                for sample in _trace("VER", 1, length=100, middle_y=4, finish_x=0)
            ],
            *[
                sample.model_copy(update={"distance_m": sample.distance_m + 7})
                for sample in _trace("PER", 1, length=102, middle_y=4, finish_x=0)
            ],
        ]

        geometry = derive_canonical_track_geometry(
            _dataset(telemetry=telemetry, laps=laps),
            max_points=3,
        )

        assert geometry is not None
        self.assertEqual([point.distance_m for point in geometry.points], [6, 56.5, 107])
        self.assertAlmostEqual(geometry.points[1].x, 50)
        self.assertAlmostEqual(geometry.points[1].y, 4)

    def test_median_geometry_filters_bad_laps(self) -> None:
        good_laps = [
            LapRecord(driver=driver, lap_number=1, lap_time_seconds=90 + index)
            for index, driver in enumerate(["VER", "PER", "ALO"])
        ]
        bad_laps = [
            LapRecord(driver="VER", lap_number=2, lap_time_seconds=90, is_pit_in_lap=True),
            LapRecord(driver="PER", lap_number=2, lap_time_seconds=90, is_pit_out_lap=True),
            LapRecord(driver="ALO", lap_number=2, lap_time_seconds=90, is_deleted=True),
            LapRecord(driver="VER", lap_number=3, lap_time_seconds=90, is_generated=True),
            LapRecord(driver="PER", lap_number=3, lap_time_seconds=90, is_accurate=False),
            LapRecord(driver="ALO", lap_number=3, lap_time_seconds=90, track_status="2"),
            LapRecord(driver="VER", lap_number=4, lap_time_seconds=90),
        ]
        telemetry = [
            *[
                sample
                for lap in good_laps
                for sample in _trace(lap.driver, lap.lap_number, length=100, middle_y=0, finish_x=0)
            ],
            *[
                sample
                for lap in bad_laps[:-1]
                for sample in _trace(lap.driver, lap.lap_number, length=100, middle_y=100, finish_x=0)
            ],
            *_trace("VER", 4, length=50, middle_y=100, finish_x=0),
        ]

        geometry = derive_canonical_track_geometry(
            _dataset(telemetry=telemetry, laps=[*good_laps, *bad_laps]),
            max_points=3,
        )

        assert geometry is not None
        self.assertEqual(geometry.contributing_lap_count, 3)
        self.assertAlmostEqual(geometry.points[1].y, 0)

    def test_median_geometry_admits_non_green_lap_when_preferred_set_is_small(self) -> None:
        laps = [
            LapRecord(driver="VER", lap_number=1, lap_time_seconds=90, track_status="1"),
            LapRecord(driver="PER", lap_number=1, lap_time_seconds=91, track_status="2"),
        ]
        telemetry = [
            *_trace("VER", 1, length=100, middle_y=0, finish_x=0),
            *_trace("PER", 1, length=100, middle_y=4, finish_x=0),
        ]

        geometry = derive_canonical_track_geometry(
            _dataset(telemetry=telemetry, laps=laps),
            max_points=3,
        )

        assert geometry is not None
        self.assertEqual(geometry.contributing_lap_count, 2)
        self.assertAlmostEqual(geometry.points[1].y, 2)

    def test_legacy_geometry_rebuilds_from_snapshot_telemetry(self) -> None:
        laps = [
            LapRecord(driver="VER", lap_number=1, lap_time_seconds=90),
            LapRecord(driver="PER", lap_number=1, lap_time_seconds=91),
        ]
        telemetry = [
            *_trace("VER", 1, length=100, middle_y=0, finish_x=0),
            *_trace("PER", 1, length=100, middle_y=2, finish_x=0),
        ]
        legacy = _legacy_geometry()

        rebuilt = ensure_track_geometry(
            _dataset(telemetry=telemetry, laps=laps).model_copy(
                update={"track_geometry": legacy}, deep=True
            )
        )
        preserved = ensure_track_geometry(
            _dataset(telemetry=[]).model_copy(update={"track_geometry": legacy}, deep=True)
        )

        assert rebuilt.track_geometry is not None
        assert preserved.track_geometry is not None
        self.assertEqual(rebuilt.track_geometry.algorithm_version, 2)
        self.assertEqual(preserved.track_geometry.algorithm_version, 1)


def _dataset(
    *,
    telemetry: list[TelemetrySample],
    laps: list[LapRecord] | None = None,
) -> SessionDataset:
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
        laps=laps or [
            LapRecord(driver="VER", lap_number=1),
            LapRecord(driver="VER", lap_number=2),
            LapRecord(driver="PER", lap_number=1),
        ],
        telemetry=telemetry,
        provenance=SourceProvenance(provider="fixture", cache_status="fixture"),
    )


def _trace(
    driver: str,
    lap_number: int,
    *,
    length: float,
    middle_y: float,
    finish_x: float,
) -> list[TelemetrySample]:
    return [
        _sample(driver, lap_number, 0, 0, 0),
        _sample(driver, lap_number, length / 2, 50, middle_y),
        _sample(driver, lap_number, length, finish_x, 0),
    ]


def _legacy_geometry() -> TrackGeometry:
    return TrackGeometry(
        source="telemetry_position",
        reason="best_positioned_lap_by_distance_span",
        source_driver="VER",
        source_lap=1,
        points=[
            TrackGeometryPoint(distance_m=0, x=0, y=0),
            TrackGeometryPoint(distance_m=100, x=0, y=0),
        ],
        original_sample_count=2,
        point_count=2,
        distance_bounds=TrackGeometryBounds(minimum=0, maximum=100),
        x_bounds=TrackGeometryBounds(minimum=0, maximum=0),
        y_bounds=TrackGeometryBounds(minimum=0, maximum=0),
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
