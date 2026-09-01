from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.findings import EditorialField, PublicationEditorial
from f1_telemetry_charts.analysis.workspace import (
    AnalysisService,
    recipe_parameter_schema,
)
from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import (
    ChartRecipeConfig,
    DataCacheConfig,
    SessionConfig,
    ThemeConfig,
)
from f1_telemetry_charts.data import (
    DriverMetadata,
    LapRecord,
    SessionDataset,
    SessionMetadata,
    SourceProvenance,
    TimingAppRecord,
    TimingStreamRecord,
)
from f1_telemetry_charts.recipes.registry import default_recipe_registry
from f1_telemetry_charts.llm import inspect_analysis
from f1_telemetry_charts.strategy import (
    StrategyExclusionPolicy,
    compare_compounds,
    compare_pit_cycle,
    derive_strategy_analysis,
    descriptive_statistics,
    race_time_delta,
    type7_quantile,
)


class StrategyAnalysisTests(unittest.TestCase):
    def test_shared_laps_stints_statistics_and_fit_are_deterministic(self) -> None:
        dataset = _strategy_dataset()
        first = derive_strategy_analysis(dataset)
        second = derive_strategy_analysis(dataset)

        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))
        ver_first = next(lap for lap in first.laps if lap.driver == "VER" and lap.lap_number == 1)
        self.assertFalse(ver_first.is_representative_for_pace)
        self.assertEqual(ver_first.pace_exclusion_reasons, ["first_race_lap"])
        ver_pit = next(lap for lap in first.laps if lap.driver == "VER" and lap.lap_number == 7)
        self.assertIn("pit_in_lap", ver_pit.pace_exclusion_reasons)
        self.assertIn("pit_in", ver_pit.context_classifications)
        neutralized = next(lap for lap in first.laps if lap.driver == "VER" and lap.lap_number == 11)
        self.assertIn("non_green_track_status", neutralized.pace_exclusion_reasons)
        self.assertIn("neutralized", neutralized.context_classifications)

        ver_stints = [stint for stint in first.stints if stint.driver == "VER"]
        self.assertEqual(len(ver_stints), 2)
        self.assertEqual(ver_stints[0].representative_lap_count, 5)
        self.assertEqual(ver_stints[0].pace_evolution.status, "available")
        self.assertEqual(ver_stints[0].pace_evolution.quality, "provisional")
        self.assertAlmostEqual(ver_stints[0].pace_evolution.slope or 0.0, 0.1)
        self.assertEqual(ver_stints[0].statistics.trim_count_per_tail, 0)

    def test_type7_quantiles_and_ten_percent_trim(self) -> None:
        self.assertEqual(type7_quantile([1, 2, 3, 4], 0.25), 1.75)
        five = descriptive_statistics([1, 2, 3, 4, 100])
        self.assertEqual(five.trim_count_per_tail, 0)
        self.assertEqual(five.trimmed_mean, 22.0)
        ten = descriptive_statistics(range(1, 11))
        self.assertEqual(ten.trim_count_per_tail, 1)
        self.assertEqual(ten.effective_count, 8)
        self.assertEqual(ten.trimmed_mean, 5.5)

    def test_complete_sector_override_and_missing_status_behavior(self) -> None:
        dataset = _strategy_dataset()
        laps = list(dataset.laps)
        target_index = next(
            index
            for index, lap in enumerate(laps)
            if lap.driver == "VER" and lap.lap_number == 2
        )
        laps[target_index] = laps[target_index].model_copy(
            update={"sector_2_time_seconds": None, "track_status": None}
        )
        partial = dataset.model_copy(update={"laps": laps}, deep=True)
        default = derive_strategy_analysis(partial)
        target = next(lap for lap in default.laps if lap.driver == "VER" and lap.lap_number == 2)
        self.assertTrue(target.is_representative_for_pace)
        self.assertIn("missing_track_status", target.context_classifications)
        complete = derive_strategy_analysis(
            partial,
            StrategyExclusionPolicy(require_complete_sectors=True),
        )
        target = next(lap for lap in complete.laps if lap.driver == "VER" and lap.lap_number == 2)
        self.assertIn("incomplete_sectors", target.pace_exclusion_reasons)

    def test_compound_modes_keep_stints_independent(self) -> None:
        analysis = derive_strategy_analysis(_strategy_dataset())
        within = compare_compounds(
            analysis,
            mode="within_driver",
            compounds=["SOFT", "HARD"],
            drivers=["VER"],
            lap_range=(1, 14),
        )
        self.assertEqual(within.status, "available")
        self.assertEqual(within.result_kind, "descriptive_within_driver_difference")
        self.assertIsNotNone(within.scalar_difference_seconds)
        self.assertTrue(all(":S" in key for key in within.sample_counts))

        unrestricted = compare_compounds(
            analysis,
            mode="unrestricted_distribution",
            compounds=["SOFT", "HARD"],
            drivers=["VER", "PER"],
        )
        self.assertIsNone(unrestricted.scalar_difference_seconds)
        self.assertEqual(unrestricted.result_kind, "unrestricted_descriptive_distribution")

    def test_measured_derived_and_pit_cycle_results_remain_distinct(self) -> None:
        dataset = _strategy_dataset()
        analysis = derive_strategy_analysis(dataset)
        measured = race_time_delta(
            dataset,
            analysis,
            mode="measured_gap_change",
            focal_driver="PER",
            benchmark="VER",
        )
        derived = race_time_delta(
            dataset,
            analysis,
            mode="derived_cumulative_pace_delta",
            focal_driver="PER",
            benchmark="VER",
        )
        self.assertEqual(measured.value_category, "measured")
        self.assertTrue(measured.direct_gap_points)
        self.assertEqual(measured.direct_gap_points[0].value_seconds, 1.1)
        self.assertEqual(derived.value_category, "derived")
        self.assertEqual(derived.points[0].value_seconds, 0.0)
        self.assertGreater(derived.overall_change_seconds or 0.0, 0.0)
        self.assertIn(11, derived.excluded_laps)

        pit = compare_pit_cycle(
            dataset,
            analysis,
            focal_driver="VER",
            rival_driver="PER",
            pit_in_lap=7,
        )
        self.assertEqual(pit.status, "confounded")
        self.assertTrue(pit.rival_stopped_in_window)
        self.assertTrue(pit.neutralized_in_window)
        self.assertEqual(pit.pit_lane_duration_seconds, 40.0)
        self.assertEqual(pit.estimated_values_reserved, {})
        self.assertIsNotNone(pit.rejoin_context)
        self.assertIsNotNone(pit.execution_breakdown)
        assert pit.execution_breakdown is not None
        self.assertEqual(pit.execution_breakdown.comparison_source, "PER Stop 1")
        self.assertEqual(pit.execution_breakdown.comparison_duration_seconds, 40.0)
        self.assertEqual(pit.execution_breakdown.signed_duration_delta_seconds, 0.0)
        self.assertFalse(pit.execution_breakdown.ranking_allowed)

        asynchronous = dataset.model_copy(
            update={
                "timing": [
                    record.model_copy(
                        update={"session_time_seconds": record.session_time_seconds + 0.25}
                    )
                    if record.driver == "PER"
                    else record
                    for record in dataset.timing
                ]
            },
            deep=True,
        )
        asynchronous_pit = compare_pit_cycle(
            asynchronous,
            derive_strategy_analysis(asynchronous),
            focal_driver="VER",
            rival_driver="PER",
            pit_in_lap=7,
        )
        self.assertIsNotNone(asynchronous_pit.pre_direct_gap_seconds)
        self.assertIsNotNone(asynchronous_pit.post_direct_gap_seconds)
        self.assertIsNotNone(asynchronous_pit.measured_gap_change_seconds)

    def test_all_seven_templates_discover_build_and_render(self) -> None:
        dataset = _strategy_dataset()
        registry = default_recipe_registry()
        strategy_ids = [
            "tyre_strategy",
            "stint_pace",
            "pace_evolution",
            "compound_comparison",
            "race_time_delta_evolution",
            "pit_cycle_comparison",
            "driver_battle",
        ]
        self.assertTrue(set(strategy_ids).issubset(registry.list_recipe_ids()))
        configs = {
            "tyre_strategy": _parameters(["VER", "PER"]),
            "stint_pace": _parameters(["VER"], selection_extra={"stints": ["VER:1", "VER:2"]}),
            "pace_evolution": _parameters(["VER"], selection_extra={"stints": ["VER:1", "VER:2"]}),
            "compound_comparison": _parameters(
                ["VER"],
                analysis={"comparison_mode": "within_driver", "compounds": ["SOFT", "HARD"]},
                lap_range={"start": 1, "end": 14},
            ),
            "race_time_delta_evolution": _parameters(
                ["VER", "PER"],
                selection_extra={"focal_driver": "PER"},
                analysis={"delta_mode": "derived_cumulative_pace_delta", "reference_driver": "VER"},
            ),
            "pit_cycle_comparison": _parameters(
                ["VER", "PER"],
                selection_extra={"focal_driver": "VER", "rival_driver": "PER"},
                analysis={"pit_stop_lap": 7, "post_stop_window": 3},
            ),
            "driver_battle": _parameters(["VER", "PER"]),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for recipe_id in strategy_ids:
                schema = recipe_parameter_schema(recipe_id)
                self.assertIn("strategy_exclusion_policy", {field.name for field in schema.fields})
                spec = registry.create(recipe_id).build_spec(
                    dataset,
                    ChartRecipeConfig(recipe_id=recipe_id, parameters=configs[recipe_id]),
                )
                self.assertEqual(spec.metadata["strategy_analysis_schema_version"], 1)
                self.assertIn("analytical_basis", spec.metadata)
                self.assertTrue(spec.title.startswith("2026 Synthetic GP "))
                if recipe_id == "tyre_strategy":
                    self.assertEqual(spec.title, "2026 Synthetic GP Race Strategy")
                artifact = MatplotlibRenderer().render(
                    spec,
                    theme=ThemeConfig(dpi=72),
                    output_dir=Path(temp_dir),
                    artifact_id=recipe_id,
                )
                self.assertTrue(artifact.image_path.exists())
                self.assertTrue(artifact.metadata_path.exists())

    def test_strategy_timeline_uses_driver_rows_compact_legend_and_local_pit_marks(self) -> None:
        dataset = _strategy_dataset()
        dataset = dataset.model_copy(
            update={
                "laps": [
                    lap.model_copy(update={"track_status": "6"})
                    if lap.lap_number == 12
                    else lap
                    for lap in dataset.laps
                ]
            },
            deep=True,
        )
        spec = default_recipe_registry().create("tyre_strategy").build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="tyre_strategy",
                parameters=_parameters(["VER", "PER"]),
            ),
        )

        self.assertEqual(spec.y_tick_labels, {0.0: "VER", 1.0: "PER"})
        self.assertTrue(spec.y_axis_inverted)
        self.assertEqual(spec.vertical_markers, [])
        self.assertEqual(len(spec.series), 1)
        self.assertEqual(spec.series[0].label, "Pit stop")
        self.assertEqual(spec.series[0].marker, "v")
        self.assertEqual(spec.metadata["pit_marker_laps"], {"PER": [10], "VER": [7]})
        self.assertEqual(
            {bar.label for bar in spec.horizontal_bars if bar.label},
            {"Soft", "Hard"},
        )
        self.assertFalse(
            any("pit" in (bar.label or "").lower() for bar in spec.horizontal_bars)
        )
        self.assertEqual(
            [(region.label, region.x_start, region.x_end) for region in spec.shaded_regions],
            [("Safety Car", 11.0, 12.0), ("VSC", 12.0, 13.0)],
        )
        self.assertEqual([region.annotation for region in spec.shaded_regions], ["SC", "VSC"])
        hard = next(bar for bar in spec.horizontal_bars if bar.label == "Hard")
        self.assertEqual(hard.color, "#CBD5E1")
        self.assertEqual(spec.panels, [])
        self.assertEqual(
            spec.metadata["effective_configuration"]["analysis"]["context_layer"],
            "race_context",
        )

    def test_pace_evolution_distinguishes_drivers_and_reports_observed_fits(self) -> None:
        dataset = _strategy_dataset().model_copy(update={"timing_app": []}, deep=True)
        spec = default_recipe_registry().create("pace_evolution").build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="pace_evolution",
                parameters=_parameters(
                    ["VER", "PER"],
                    selection_extra={"stints": ["VER:1", "PER:1"]},
                ),
            ),
        )

        self.assertEqual(spec.x_label, "Stint progress lap")
        self.assertIn(
            "Tyre age unavailable; evolution shown against stint progress.",
            spec.subtitle or "",
        )
        self.assertIn("Markers = representative samples; lines = observed fits.", spec.subtitle or "")
        samples = [series for series in spec.series if series.render_mode == "scatter"]
        fits = [series for series in spec.series if series.render_mode == "line"]
        self.assertTrue(all(series.label is None for series in samples))
        self.assertTrue(all(series.label is None for series in fits))
        self.assertEqual(spec.legend_order, [])
        self.assertEqual(samples[0].color, fits[0].color)
        self.assertEqual(samples[1].color, fits[1].color)
        self.assertNotEqual(samples[0].marker, samples[1].marker)
        self.assertNotEqual(fits[0].line_style, fits[1].line_style)
        self.assertEqual({annotation.text.strip() for annotation in spec.annotations}, {"VER", "PER"})
        self.assertTrue(any(line.startswith("VER: +0.100 s/lap, n=5, quality=") for line in spec.summary_lines))
        self.assertTrue(any(line.startswith("PER: +0.120 s/lap, n=8, quality=") for line in spec.summary_lines))
        for sample, fit in zip(samples, fits, strict=True):
            self.assertEqual(fit.x, [min(sample.x), max(sample.x)])
        self.assertEqual(spec.y_label, "Representative lap time (s)")
        self.assertFalse(hasattr(spec, "confidence_bands"))

    def test_sector_pace_evolution_shows_driver_fits_summaries_and_shared_scale(self) -> None:
        base = _strategy_dataset()
        dataset = base.model_copy(
            update={
                "drivers": [
                    driver.model_copy(update={"team_color": "#3671C6"})
                    for driver in base.drivers
                ]
            },
            deep=True,
        )
        spec = default_recipe_registry().create("pace_evolution").build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="pace_evolution",
                parameters=_parameters(
                    ["VER", "PER"],
                    selection_extra={"stints": ["VER:1", "PER:1"]},
                    analysis={"evolution_mode": "sector_evolution"},
                ),
            ),
        )

        self.assertEqual(len(spec.panels), 3)
        self.assertIn("VER S1 vs PER S1, Soft, tyre-age basis.", spec.subtitle or "")
        self.assertIn(
            "Delta normalized to each driver's first representative sector sample.",
            spec.subtitle or "",
        )
        self.assertEqual(len({panel.y_limits for panel in spec.panels}), 1)
        self.assertEqual(len({panel.x_limits for panel in spec.panels}), 1)
        for panel in spec.panels:
            samples = [series for series in panel.series if series.render_mode == "scatter"]
            fits = [series for series in panel.series if series.render_mode == "line"]
            self.assertEqual(len(samples), 2)
            self.assertEqual(len(fits), 2)
            self.assertTrue(all(series.label is None for series in panel.series))
            self.assertEqual(samples[0].color, samples[1].color)
            self.assertEqual(samples[0].color, fits[0].color)
            self.assertEqual(samples[1].color, fits[1].color)
            self.assertEqual([series.marker for series in samples], ["o", "s"])
            self.assertEqual([series.line_style for series in fits], ["-", "--"])
            self.assertEqual(
                {annotation.text.strip() for annotation in panel.annotations},
                {"VER", "PER"},
            )
            self.assertEqual(len(panel.summary_lines), 2)
            self.assertTrue(panel.summary_lines[0].startswith("VER: +"))
            self.assertTrue(panel.summary_lines[1].startswith("PER: +"))
            self.assertTrue(all("s/lap, n=" in line and "quality=" in line for line in panel.summary_lines))
            self.assertEqual(
                panel.y_label,
                "Normalized sector-time delta (s)",
            )
            for sample, fit in zip(samples, fits, strict=True):
                self.assertEqual(fit.x, [min(sample.x), max(sample.x)])

    def test_strategy_timeline_distinguishes_unknown_compound_and_retirement(self) -> None:
        dataset = _strategy_dataset()
        laps = [
            lap.model_copy(update={"compound": None})
            if lap.driver == "VER" and lap.lap_number == 3
            else lap
            for lap in dataset.laps
            if lap.driver != "VER" or lap.lap_number <= 10
        ]
        drivers = [
            driver.model_copy(
                update={
                    "classification_position": 2,
                    "grid_position": 2,
                    "result_status": "Accident",
                }
            )
            if driver.abbreviation == "VER"
            else driver.model_copy(
                update={
                    "classification_position": 1,
                    "grid_position": 1,
                    "result_status": "Finished",
                }
            )
            for driver in dataset.drivers
        ]
        partial = dataset.model_copy(update={"laps": laps, "drivers": drivers}, deep=True)
        spec = default_recipe_registry().create("tyre_strategy").build_spec(
            partial,
            ChartRecipeConfig(
                recipe_id="tyre_strategy",
                parameters=_parameters(["VER", "PER"]),
            ),
        )

        self.assertEqual(spec.selected_drivers, ["PER", "VER"])
        unknown = next(bar for bar in spec.horizontal_bars if bar.label == "Unknown compound")
        retired = next(bar for bar in spec.horizontal_bars if bar.hatch == "\\\\")
        self.assertEqual(unknown.hatch, "///")
        self.assertEqual(unknown.color, "#B8BEC5")
        self.assertEqual(retired.hatch, "\\\\")
        self.assertEqual((retired.x_start, retired.x_end), (11.0, 15.0))
        self.assertEqual(
            [(annotation.text, annotation.x, annotation.y) for annotation in spec.annotations],
            [("RET", 11.15, 1.0)],
        )

    def test_strategy_titles_are_session_first_and_compound_legend_is_ordered(self) -> None:
        dataset = _strategy_dataset()
        dataset = dataset.model_copy(
            update={
                "metadata": dataset.metadata.model_copy(
                    update={"season": 2023, "event": "Bahrain Grand Prix"}
                )
            },
            deep=True,
        )
        spec = default_recipe_registry().create("tyre_strategy").build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="tyre_strategy",
                parameters=_parameters(["VER", "PER"]),
            ),
        )
        self.assertEqual(spec.title, "2023 Bahrain GP Race Strategy")

        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        from f1_telemetry_charts.charts.renderers.matplotlib import (
            _deduplicated_legend,
        )

        figure, axis = plt.subplots()
        axis.barh(0, 1, label="Hard")
        axis.barh(1, 1, label="Soft")
        axis.barh(2, 1, label="Medium")
        axis.scatter([1], [1], label="Pit stop", marker="v")
        _, labels = _deduplicated_legend(axis)
        plt.close(figure)
        self.assertEqual(labels, ["Soft", "Medium", "Hard", "Pit stop"])

    def test_stint_pace_focuses_selected_stints_and_exposes_head_to_head_summary(self) -> None:
        dataset = _strategy_dataset()
        dataset = dataset.model_copy(
            update={
                "laps": [
                    lap.model_copy(update={"is_accurate": False})
                    if lap.driver == "VER" and lap.lap_number == 4
                    else lap
                    for lap in dataset.laps
                ]
            },
            deep=True,
        )
        parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"stints": ["VER:1", "PER:1"]},
        )
        spec = default_recipe_registry().create("stint_pace").build_spec(
            dataset,
            ChartRecipeConfig(recipe_id="stint_pace", parameters=parameters),
        )

        self.assertEqual(spec.x_label, "Stint lap")
        self.assertEqual(spec.subtitle, "Soft compound")
        self.assertEqual(spec.shaded_regions, [])
        self.assertIsNotNone(spec.x_limits)
        assert spec.x_limits is not None
        self.assertLess(spec.x_limits[1], 12)
        representative = [
            series for series in spec.series if series.render_mode == "line"
        ]
        self.assertEqual(
            {series.label for series in representative if series.label},
            {"VER S1", "PER S1"},
        )
        first_by_driver = {
            series.label: series
            for series in representative
            if series.label in {"VER S1", "PER S1"}
        }
        self.assertNotEqual(
            first_by_driver["VER S1"].line_style,
            first_by_driver["PER S1"].line_style,
        )
        self.assertNotEqual(
            first_by_driver["VER S1"].marker,
            first_by_driver["PER S1"].marker,
        )
        self.assertTrue(all(series.marker for series in representative))
        excluded = [series for series in spec.series if series.render_mode == "excluded_strip"]
        self.assertEqual(len(excluded), 2)
        self.assertEqual(excluded[0].label, "Hollow marker = excluded lap")
        self.assertIsNone(excluded[1].label)
        self.assertEqual(excluded[0].marker, first_by_driver["VER S1"].marker)
        self.assertEqual(excluded[1].marker, first_by_driver["PER S1"].marker)
        self.assertNotEqual(excluded[0].marker, excluded[1].marker)
        self.assertEqual(set(excluded[0].y), {0.0})
        self.assertEqual(set(excluded[1].y), {1.0})
        self.assertEqual(
            spec.legend_order,
            ["VER S1", "PER S1", "Hollow marker = excluded lap"],
        )
        self.assertEqual(spec.legend_location, "upper right")
        self.assertEqual(spec.panels, [])
        self.assertEqual(spec.vertical_markers, [])
        self.assertEqual(spec.horizontal_bars, [])
        self.assertEqual(
            {annotation.text.strip() for annotation in spec.annotations},
            {"VER S1", "PER S1"},
        )
        self.assertTrue(any("representative laps" in line for line in spec.summary_lines))
        self.assertTrue(any("median" in line and "IQR" in line for line in spec.summary_lines))
        self.assertTrue(
            any(line.startswith("VER median advantage:") for line in spec.summary_lines)
        )
        self.assertIn("inaccurate_lap", spec.metadata["excluded_lap_numbers_by_reason"])
        self.assertNotIn("inaccurate_lap", " ".join(spec.summary_lines))
        self.assertEqual(
            spec.metadata["effective_configuration"]["presentation"]["x_axis_basis"],
            "stint_progress",
        )

        race_lap_parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"stints": ["VER:1", "PER:1"]},
        )
        race_lap_parameters["presentation"] = {"x_axis_basis": "race_lap"}
        race_lap_spec = default_recipe_registry().create("stint_pace").build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="stint_pace",
                parameters=race_lap_parameters,
            ),
        )
        self.assertEqual(race_lap_spec.x_label, "Race lap")
        self.assertEqual(race_lap_spec.shaded_regions, [])

    def test_stint_pace_summary_uses_labelled_faster_first_rows_and_compact_encoding_key(self) -> None:
        dataset = _strategy_dataset()
        parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"stints": ["VER:1", "PER:1"]},
        )
        parameters["presentation"] = {"presentation_mode": "consistency_summary"}
        spec = default_recipe_registry().create("stint_pace").build_spec(
            dataset,
            ChartRecipeConfig(recipe_id="stint_pace", parameters=parameters),
        )

        rows = spec.metadata["analytical_results"]["comparison_summary"]["stints"]
        expected_labels = {
            float(index): row["label"]
            for index, row in enumerate(
                sorted(rows, key=lambda row: row["median_seconds"])
            )
        }
        self.assertEqual(spec.title, "2026 Synthetic GP Race Stint Pace Summary")
        self.assertEqual(spec.x_label, "Representative lap time (s)")
        self.assertEqual(spec.y_label, "")
        self.assertEqual(spec.y_tick_labels, expected_labels)
        self.assertTrue(spec.y_axis_inverted)
        self.assertEqual(spec.y_limits, (-0.35, 1.35))
        self.assertEqual(
            spec.legend_order,
            ["dot = median", "dark band = IQR", "light band = min/max"],
        )
        self.assertEqual(
            [series.label for series in spec.series],
            ["dot = median", None],
        )
        self.assertTrue(all(series.marker_size == 110 for series in spec.series))
        self.assertEqual(
            [bar.label for bar in spec.horizontal_bars],
            ["light band = min/max", "dark band = IQR", None, None],
        )
        self.assertEqual(
            [bar.alpha for bar in spec.horizontal_bars],
            [0.12, 0.62, 0.12, 0.62],
        )
        self.assertEqual(
            [bar.height for bar in spec.horizontal_bars],
            [0.06, 0.12, 0.06, 0.12],
        )
        self.assertTrue(any("representative laps" in line for line in spec.summary_lines))
        self.assertTrue(any("median advantage" in line for line in spec.summary_lines))

    def test_race_time_delta_requires_explicit_comparator_and_has_one_series_identity(self) -> None:
        dataset = _strategy_dataset()
        recipe = default_recipe_registry().create("race_time_delta_evolution")
        missing_comparator = _parameters(
            ["VER", "PER"],
            selection_extra={"focal_driver": "VER"},
            analysis={"delta_mode": "derived_cumulative_pace_delta"},
        )
        with self.assertRaisesRegex(ValueError, "explicit comparator driver"):
            recipe.build_spec(
                dataset,
                ChartRecipeConfig(
                    recipe_id="race_time_delta_evolution",
                    parameters=missing_comparator,
                ),
            )

        parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"focal_driver": "VER"},
            analysis={
                "delta_mode": "derived_cumulative_pace_delta",
                "reference_driver": "PER",
            },
        )
        spec = recipe.build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="race_time_delta_evolution",
                parameters=parameters,
            ),
        )

        self.assertEqual(
            spec.title,
            "2026 Synthetic GP Race-Time Delta: VER vs PER",
        )
        self.assertEqual(spec.y_label, "VER − PER race-time delta (s)")
        self.assertIn("Cumulative pace difference", spec.subtitle or "")
        self.assertIn(
            f"normalized to zero at lap {spec.metadata['analytical_results']['start_lap']}",
            spec.subtitle or "",
        )
        self.assertIn("negative = VER ahead", spec.subtitle or "")
        line_series = [series for series in spec.series if series.render_mode == "line"]
        self.assertEqual(
            [series.label for series in line_series if series.label],
            ["VER vs PER"],
        )
        self.assertFalse(
            any("segment" in (series.label or "").lower() for series in spec.series)
        )
        self.assertEqual(
            spec.metadata["analytical_results"]["points"][0]["value_seconds"],
            0.0,
        )
        self.assertTrue(
            any(region.label in {"Safety Car", "VSC"} for region in spec.shaded_regions)
        )
        self.assertEqual(
            {series.label for series in spec.series if series.render_mode == "scatter"},
            {"VER pit stop", "PER pit stop"},
        )
        self.assertEqual(
            spec.legend_order,
            ["VER vs PER", "VER pit stop", "PER pit stop"],
        )
        self.assertEqual(len(spec.horizontal_markers), 1)
        self.assertEqual(spec.horizontal_markers[0].y, 0.0)
        self.assertIsNone(spec.horizontal_markers[0].label)
        pit_markers = [
            series for series in spec.series if series.render_mode == "scatter"
        ]
        self.assertTrue(all(series.marker_size == 30 for series in pit_markers))
        self.assertTrue(all(series.color == "#64748B" for series in pit_markers))
        breaks = spec.metadata["comparison_breaks"]
        self.assertEqual(len(breaks), len(line_series) - 1)
        self.assertTrue(all(item["laps"] for item in breaks))
        self.assertTrue(
            all(
                set(item["reason_categories"])
                <= {"coverage_loss", "excluded_comparison_window"}
                for item in breaks
            )
        )
        schema = recipe_parameter_schema("race_time_delta_evolution")
        comparator = next(field for field in schema.fields if field.name == "reference_driver")
        self.assertTrue(comparator.required)

    def test_pit_cycle_is_an_explicit_window_or_typed_unavailable_state(self) -> None:
        dataset = _strategy_dataset()
        recipe = default_recipe_registry().create("pit_cycle_comparison")
        missing_stop = _parameters(
            ["VER", "PER"],
            selection_extra={"focal_driver": "VER", "rival_driver": "PER"},
            analysis={"post_stop_window": 3},
        )
        with self.assertRaisesRegex(ValueError, "explicit focal pit-in lap"):
            recipe.build_spec(
                dataset,
                ChartRecipeConfig(
                    recipe_id="pit_cycle_comparison",
                    parameters=missing_stop,
                ),
            )

        parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"focal_driver": "VER", "rival_driver": "PER"},
            analysis={"pit_stop_lap": 7, "post_stop_window": 3},
        )
        spec = recipe.build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="pit_cycle_comparison",
                parameters=parameters,
            ),
        )
        result = spec.metadata["analytical_results"]
        self.assertEqual(spec.title, "2026 Synthetic GP Race Pit Cycle: VER Stop 1 vs PER")
        self.assertIn("Pre L6", spec.subtitle or "")
        self.assertIn("Post L9", spec.subtitle or "")
        self.assertIn("VER gained 0.300 s relative to PER", spec.subtitle or "")
        self.assertNotIn("confounded", spec.subtitle or "")
        self.assertEqual(result["focal_stop_number"], 1)
        self.assertEqual(result["pre_reference_lap"], 6)
        self.assertEqual(result["post_reference_lap"], 9)
        self.assertEqual(len(spec.panels), 2)
        primary, window = spec.panels
        self.assertEqual(len(primary.series), 2)
        self.assertEqual(primary.series[0].line_style, ":")
        self.assertIsNone(primary.series[0].label)
        self.assertEqual(primary.series[1].render_mode, "scatter")
        self.assertIsNone(primary.series[1].label)
        self.assertIsNotNone(primary.y_limits)
        assert primary.y_limits is not None
        self.assertLess(primary.y_limits[0], min(primary.series[1].y))
        self.assertGreater(primary.y_limits[1], max(primary.series[1].y))
        self.assertLess(primary.y_limits[1], 0.0)
        self.assertIsNone(primary.state_message)
        self.assertEqual(primary.horizontal_markers[0].y, 0.0)
        self.assertEqual(
            {marker.annotation for marker in primary.vertical_markers},
            {"Pre ref L6", "Pit-in L7", "Pit-out L8", "Post ref L9"},
        )
        pit_region = next(
            region for region in primary.shaded_regions if region.annotation == "Pit interval"
        )
        pit_in_marker = next(
            marker for marker in primary.vertical_markers if marker.annotation == "Pit-in L7"
        )
        pit_out_marker = next(
            marker for marker in primary.vertical_markers if marker.annotation == "Pit-out L8"
        )
        self.assertEqual(pit_region.x_start, pit_in_marker.x)
        self.assertEqual(pit_region.x_end, pit_out_marker.x)
        self.assertIn("rival stopped", " ".join(result["warnings"]).lower())
        self.assertEqual(window.y_tick_labels, {0.0: "VER", 1.0: "PER"})
        self.assertTrue(window.y_axis_inverted)
        self.assertTrue(all(bar.height == 0.6 for bar in window.horizontal_bars))
        bar_labels = {bar.label for bar in window.horizontal_bars if bar.label}
        self.assertEqual(bar_labels, {"Soft", "Hard"})
        self.assertFalse(any("S1" in label or "S2" in label for label in bar_labels))
        self.assertTrue(
            all(marker.annotation is None for marker in window.vertical_markers)
        )
        self.assertTrue(
            all(region.annotation is None for region in window.shaded_regions)
        )
        assert primary.x_limits is not None
        self.assertTrue(
            all(
                primary.x_limits[0] <= region.x_start <= region.x_end <= primary.x_limits[1]
                for region in primary.shaded_regions
            )
        )

        advanced_parameters = _parameters(
            ["VER", "PER"],
            selection_extra={"focal_driver": "VER", "rival_driver": "PER"},
            analysis={"pit_stop_lap": 7, "post_stop_window": 3},
        )
        advanced_parameters["presentation"] = {
            "show_rejoin_context": True,
            "show_execution_breakdown": True,
        }
        same_compound_dataset = dataset.model_copy(
            update={
                "laps": [
                    lap.model_copy(update={"compound": "SOFT"})
                    for lap in dataset.laps
                ]
            },
            deep=True,
        )
        advanced = recipe.build_spec(
            same_compound_dataset,
            ChartRecipeConfig(
                recipe_id="pit_cycle_comparison",
                parameters=advanced_parameters,
            ),
        )
        self.assertEqual(advanced.subtitle, "VER gained 0.300 s relative to PER")
        self.assertEqual(len(advanced.panels), 3)
        advanced_primary, _, context_strip = advanced.panels
        self.assertEqual(len(advanced_primary.annotations), 2)
        self.assertEqual(context_strip.title, "Additional context")
        self.assertFalse(context_strip.show_axes)
        self.assertLess(context_strip.height_ratio, advanced.panels[1].height_ratio)
        self.assertEqual(len(context_strip.info_blocks), 2)
        rejoin_text, execution_text = [
            block.text for block in context_strip.info_blocks
        ]
        self.assertIn("REJOIN CONTEXT", rejoin_text)
        self.assertIn("VER rejoined", rejoin_text)
        self.assertIn("PER next stop: within", rejoin_text)
        self.assertNotIn("Relative position after 3 laps", rejoin_text)
        self.assertIn("VER Stop 1", execution_text)
        self.assertIn("pit-in to pit-out", execution_text)
        self.assertIn("Stationary time", execution_text)
        self.assertNotIn("PER Stop 1", execution_text)
        advanced_window = advanced.panels[1]
        self.assertTrue(
            all(marker.annotation is None for marker in advanced_window.vertical_markers)
        )
        self.assertTrue(
            all(region.annotation is None for region in advanced_window.shaded_regions)
        )
        self.assertFalse(
            any(bar.label for bar in advanced_window.horizontal_bars)
        )
        self.assertEqual(
            advanced.metadata["timing_state_resolution"]["method"],
            "as_of_source_state",
        )

        unavailable_dataset = dataset.model_copy(update={"timing": []}, deep=True)
        unavailable = recipe.build_spec(
            unavailable_dataset,
            ChartRecipeConfig(
                recipe_id="pit_cycle_comparison",
                parameters=parameters,
            ),
        )
        unavailable_result = unavailable.metadata["analytical_results"]
        self.assertEqual(unavailable_result["status"], "unavailable")
        self.assertFalse(unavailable.panels[0].series)
        self.assertIn("unavailable", unavailable.panels[0].state_message or "")
        self.assertTrue(unavailable_result["unavailable_reasons"])
        schema = recipe_parameter_schema("pit_cycle_comparison")
        pit_stop = next(field for field in schema.fields if field.name == "pit_stop_lap")
        self.assertTrue(pit_stop.required)

    def test_driver_battle_uses_direct_gap_summary_labels_and_compact_context(self) -> None:
        dataset = _strategy_dataset()
        recipe = default_recipe_registry().create("driver_battle")
        parameters = _parameters(["VER", "PER"])
        spec = recipe.build_spec(
            dataset,
            ChartRecipeConfig(recipe_id="driver_battle", parameters=parameters),
        )
        self.assertEqual(spec.title, "2026 Synthetic GP Driver Battle: VER vs PER")
        self.assertIn("Start L1: -1.100 s", spec.subtitle or "")
        self.assertIn("End L14: -2.400 s", spec.subtitle or "")
        self.assertIn("VER gained 1.300 s relative to PER", spec.subtitle or "")
        self.assertNotIn("Observed:", spec.subtitle or "")
        self.assertEqual(len(spec.panels), 3)
        pace, gap, context = spec.panels
        self.assertEqual([series.label for series in pace.series], ["VER", "PER"])
        self.assertEqual({annotation.text.strip() for annotation in pace.annotations}, {"VER", "PER"})
        self.assertEqual(gap.title, "Direct gap: VER vs PER")
        self.assertTrue(gap.series)
        self.assertFalse(any("Position" in (series.label or "") for series in gap.series))
        self.assertAlmostEqual(gap.series[0].y[0], -1.1)
        self.assertAlmostEqual(gap.series[-1].y[-1], -2.4)
        self.assertIn("negative = VER ahead", gap.y_label)
        self.assertEqual(context.y_tick_labels, {0.0: "VER", 1.0: "PER"})
        self.assertTrue(context.y_axis_inverted)
        self.assertEqual(
            {bar.label for bar in context.horizontal_bars if bar.label},
            {"Soft", "Hard"},
        )
        self.assertTrue(all(region.label is None for region in context.shaded_regions))
        self.assertTrue(any("age" in annotation.text for annotation in context.annotations))
        expected_pits = {"VER pit L7", "PER pit L10"}
        for panel in spec.panels:
            self.assertEqual(
                {marker.annotation for marker in panel.vertical_markers},
                expected_pits,
            )
            self.assertEqual(panel.x_limits, (0.5, 14.5))
        results = spec.metadata["analytical_results"]
        self.assertAlmostEqual(results["battle_summary"]["observed_change_seconds"], -1.3)

        unavailable_dataset = dataset.model_copy(update={"timing": []}, deep=True)
        unavailable = recipe.build_spec(
            unavailable_dataset,
            ChartRecipeConfig(recipe_id="driver_battle", parameters=parameters),
        )
        self.assertFalse(unavailable.panels[1].series)
        self.assertIn("unavailable", unavailable.panels[1].state_message or "")
        self.assertNotIn("Position fallback", unavailable.panels[1].title)

    def test_compound_comparison_uses_categories_samples_and_guarded_summary(self) -> None:
        dataset = _strategy_dataset()
        recipe = default_recipe_registry().create("compound_comparison")
        comparable = recipe.build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="compound_comparison",
                parameters=_parameters(
                    ["VER"],
                    analysis={
                        "comparison_mode": "within_driver",
                        "compounds": ["HARD", "SOFT"],
                    },
                    lap_range={"start": 1, "end": 14},
                ),
            ),
        )
        self.assertEqual(comparable.x_label, "Compound")
        self.assertEqual(comparable.x_tick_labels, {0.0: "Hard", 1.0: "Soft"})
        self.assertNotIn("Descriptive only", comparable.subtitle or "")
        self.assertIn("n=", comparable.subtitle or "")
        self.assertTrue(comparable.series)
        self.assertTrue(all(series.label is None for series in comparable.series))
        self.assertFalse(any(":S" in (series.label or "") for series in comparable.series))
        self.assertEqual(len(comparable.box_summaries), 2)
        self.assertTrue(
            all(summary.q1 <= summary.median <= summary.q3 for summary in comparable.box_summaries)
        )
        self.assertEqual(comparable.x_limits, (-0.55, 1.55))
        self.assertIsNotNone(comparable.y_limits)
        assert comparable.y_limits is not None
        sample_values = [value for series in comparable.series if series.render_mode == "scatter" for value in series.y]
        observed_span = max(sample_values) - min(sample_values)
        self.assertLessEqual(
            comparable.y_limits[1] - comparable.y_limits[0],
            observed_span + max(observed_span * 0.2, 0.3) + 1e-9,
        )
        annotation_text = " ".join(annotation.text for annotation in comparable.annotations)
        self.assertIn("n=", annotation_text)
        self.assertIn("median", annotation_text)
        self.assertIn("IQR", annotation_text)
        count_annotations = [
            annotation for annotation in comparable.annotations if annotation.text.startswith("n=")
        ]
        self.assertEqual(
            {(annotation.x, annotation.horizontal_alignment) for annotation in count_annotations},
            {(0.0, "center"), (1.0, "center")},
        )
        summaries = comparable.metadata["compound_summaries"]
        self.assertEqual(set(summaries), {"HARD", "SOFT"})
        self.assertTrue(all(summary["n"] > 0 for summary in summaries.values()))

        descriptive = recipe.build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="compound_comparison",
                parameters=_parameters(
                    ["VER", "PER"],
                    analysis={
                        "comparison_mode": "unrestricted_distribution",
                        "compounds": ["HARD", "SOFT"],
                    },
                ),
            ),
        )
        self.assertTrue((descriptive.subtitle or "").startswith("Descriptive only"))
        self.assertIsNone(
            descriptive.metadata["analytical_results"]["scalar_difference_seconds"]
        )

    def test_legacy_tyre_strategy_workspace_migrates_to_schema_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AnalysisService(Path(temp_dir))
            analysis = service.create("Migration")
            raw = analysis.model_dump(mode="json")
            raw["charts"] = [
                {
                    "chart_instance_id": "legacy",
                    "recipe_id": "tyre_strategy",
                    "name": "Legacy",
                    "target_session_ids": ["session"],
                    "parameters": {"analysis": {"layout": "stint_bars"}},
                    "parameter_hash": "legacy",
                    "schema_version": 1,
                    "order": 0,
                }
            ]
            (Path(temp_dir) / "analysis.json").write_text(
                __import__("json").dumps(raw), encoding="utf-8"
            )
            migrated = service.open()
        self.assertEqual(migrated.charts[0].schema_version, 2)
        self.assertEqual(
            migrated.charts[0].parameters["diagnostics"]["migration"]["status"],
            "mapped",
        )

    def test_workspace_diagnostics_generation_export_and_llm_cover_all_templates(self) -> None:
        dataset = _strategy_dataset()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            fixture_path = Path(temp_dir) / "strategy-dataset.json"
            fixture_path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
            service = AnalysisService(root)
            analysis = service.create("Strategy lifecycle")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(season=2026, event="Synthetic GP", session="Race"),
                drivers=["VER", "PER"],
                data_cache=DataCacheConfig(fixture_path=fixture_path),
            )
            session_id = analysis.sessions[0].session_id
            configurations = {
                "tyre_strategy": _parameters(["VER", "PER"]),
                "stint_pace": _parameters(["VER"], selection_extra={"stints": ["VER:1", "VER:2"]}),
                "pace_evolution": _parameters(["VER"], selection_extra={"stints": ["VER:1", "VER:2"]}),
                "compound_comparison": _parameters(
                    ["VER"],
                    analysis={"comparison_mode": "within_driver", "compounds": ["SOFT", "HARD"]},
                    lap_range={"start": 1, "end": 14},
                ),
                "race_time_delta_evolution": _parameters(
                    ["VER", "PER"],
                    selection_extra={"focal_driver": "PER"},
                    analysis={"delta_mode": "derived_cumulative_pace_delta", "reference_driver": "VER"},
                ),
                "pit_cycle_comparison": _parameters(
                    ["VER", "PER"],
                    selection_extra={"focal_driver": "VER", "rival_driver": "PER"},
                    analysis={"pit_stop_lap": 7, "post_stop_window": 3},
                ),
                "driver_battle": _parameters(["VER", "PER"]),
            }
            for recipe_id, parameters in configurations.items():
                diagnostics = service.resolve_chart_diagnostics(
                    analysis,
                    recipe_id=recipe_id,
                    target_session_ids=[session_id],
                    parameters=parameters,
                )
                self.assertEqual(diagnostics.status, "valid", recipe_id)
                self.assertIn("representative_sample_count", diagnostics.analytical_basis)
                analysis = service.add_chart(
                    analysis,
                    recipe_id=recipe_id,
                    target_session_ids=[session_id],
                    parameters=parameters,
                )
            analysis = service.generate_charts(analysis)
            self.assertTrue(all(chart.generation_state == "generated" for chart in analysis.charts))
            analysis = service.refresh_observations(analysis)
            self.assertIsNotNone(analysis.report_content)
            self.assertEqual(len(analysis.report_content.results), 10)
            self.assertTrue(
                {
                    "race_classification",
                    "neutralisation_periods",
                    "retirement_status",
                }
                <= {item.result_type for item in analysis.report_content.results}
            )
            self.assertTrue(
                {
                    "grid_to_finish_movement",
                    "pit_stop_sequence",
                    "position_change_interval",
                }.isdisjoint(
                    {item.result_type for item in analysis.report_content.results}
                )
            )
            with self.assertRaisesRegex(ValueError, "Review included report claims"):
                service.export_package(analysis)
            publication_plan = analysis.report_content.publication_plan.model_copy(
                update={
                    "charts": [
                        chart.model_copy(
                            update={
                                "caption": EditorialField(value="The selected comparison highlights the main pace difference across the reviewed interval."),
                                "alt_text": EditorialField(value="Line chart with two driver traces plotted across the reviewed race interval and labelled at their endpoints."),
                            },
                            deep=True,
                        )
                        for chart in analysis.report_content.publication_plan.charts
                    ]
                },
                deep=True,
            )
            analysis = service.update_publication(
                analysis,
                plan=publication_plan,
                editorial=PublicationEditorial(
                    headline=EditorialField(value="Verstappen leads Bahrain as the field order changes"),
                    standfirst=EditorialField(value="Verstappen led the Bahrain finish while the reviewed chronology and pace evidence defined the main race story."),
                    section_ledes={
                        "how_the_race_developed": EditorialField(value="The classified order, field recovery and neutralised phase establish the race chronology."),
                        "pace_and_strategy": EditorialField(value="The representative-lap comparisons then show how the leading pair differed on pace."),
                    },
                    conclusion=EditorialField(value="The reviewed chronology and representative pace evidence support this final account."),
                ),
                evidence_fingerprint=analysis.report_content.evidence_fingerprint,
            )
            for claim in [
                *analysis.report_content.findings,
                *analysis.report_content.conclusions,
            ]:
                analysis = service.review_report_item(
                    analysis,
                    item_id=claim.finding_id,
                    review_status="accepted",
                    evidence_fingerprint=claim.evidence_fingerprint,
                )
            analysis = service.regenerate_report_draft(analysis)
            analysis = service.export_package(analysis)
            self.assertTrue((root / "package" / "manifest.json").exists())
            inspected = inspect_analysis(
                {"contract_version": "1.0", "analysis_path": str(root)}
            )
            self.assertEqual(inspected["status"], "succeeded")
            self.assertEqual(len(inspected["strategy_summaries"]), 7)
            self.assertIsNotNone(inspected["report_summary"])
            self.assertEqual(
                inspected["report_summary"]["target_session_id"], session_id
            )
            self.assertNotIn("payload", inspected["report_summary"])
            self.assertNotIn("report_content", inspected["analysis"])
            self.assertTrue(
                all("strategy_laps" not in summary for summary in inspected["strategy_summaries"])
            )


def _parameters(
    drivers: list[str],
    *,
    selection_extra: dict | None = None,
    analysis: dict | None = None,
    lap_range: dict | None = None,
) -> dict:
    selection = {
        "driver_selection_mode": "selected",
        "drivers": drivers,
        **(selection_extra or {}),
    }
    if lap_range is not None:
        selection["laps"] = {"range": lap_range}
    return {"selection": selection, "analysis": analysis or {}}


def _strategy_dataset() -> SessionDataset:
    laps: list[LapRecord] = []
    timing: list[TimingStreamRecord] = []
    timing_app: list[TimingAppRecord] = []
    for lap_number in range(1, 15):
        start = float((lap_number - 1) * 100)
        end = float(lap_number * 100)
        track_status = "4" if lap_number == 11 else "1"
        for driver, offset in (("VER", 0.0), ("PER", 1.0)):
            if driver == "VER":
                stint = 1 if lap_number <= 7 else 2
                compound = "SOFT" if stint == 1 else "HARD"
                is_pit_in = lap_number == 7
                is_pit_out = lap_number == 8
                pit_in = 680.0 if is_pit_in else None
                pit_out = 720.0 if is_pit_out else None
            else:
                stint = 1 if lap_number <= 10 else 2
                compound = "SOFT" if stint == 1 else "HARD"
                is_pit_in = lap_number == 10
                is_pit_out = lap_number == 11
                pit_in = 980.0 if is_pit_in else None
                pit_out = 1020.0 if is_pit_out else None
            age = lap_number if stint == 1 else lap_number - (7 if driver == "VER" else 10)
            slope = 0.1 if driver == "VER" else 0.12
            lap_time = 90.0 + offset + slope * age
            laps.append(
                LapRecord(
                    driver=driver,
                    lap_number=lap_number,
                    lap_start_time_seconds=start,
                    lap_end_time_seconds=end,
                    lap_time_seconds=lap_time,
                    compound=compound,
                    stint=stint,
                    position=1 if driver == "VER" else 2,
                    is_pit_in_lap=is_pit_in,
                    is_pit_out_lap=is_pit_out,
                    pit_in_time_seconds=pit_in,
                    pit_out_time_seconds=pit_out,
                    is_accurate=True,
                    sector_1_time_seconds=30.0 + slope * age / 3,
                    sector_2_time_seconds=36.0 + slope * age / 3,
                    sector_3_time_seconds=24.0 + slope * age / 3,
                    track_status=track_status,
                )
            )
            timing_app.append(
                TimingAppRecord(
                    driver=driver,
                    session_time_seconds=end,
                    lap_number=lap_number,
                    stint=stint,
                    total_laps=float(age),
                    compound=compound,
                    start_laps=1.0,
                )
            )
        timing.extend(
            [
                TimingStreamRecord(
                    driver="VER",
                    session_time_seconds=end,
                    position=1,
                    gap_to_leader_seconds=0.0,
                    gap_parse_status="leader",
                    interval_parse_status="leader",
                ),
                TimingStreamRecord(
                    driver="PER",
                    session_time_seconds=end,
                    position=2,
                    gap_to_leader_seconds=1.0 + 0.1 * lap_number,
                    interval_to_ahead_seconds=1.0 + 0.1 * lap_number,
                    gap_parse_status="parsed",
                    interval_parse_status="parsed",
                ),
            ]
        )
    return SessionDataset(
        metadata=SessionMetadata(season=2026, event="Synthetic GP", session="Race"),
        drivers=[
            DriverMetadata(abbreviation="VER", team_name="Red Bull Racing"),
            DriverMetadata(abbreviation="PER", team_name="Red Bull Racing"),
        ],
        laps=laps,
        timing=timing,
        timing_app=timing_app,
        provenance=SourceProvenance(provider="synthetic", cache_status="fixture"),
    )


if __name__ == "__main__":
    unittest.main()
