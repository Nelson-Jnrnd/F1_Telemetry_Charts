"""Matplotlib chart renderer."""

from __future__ import annotations

from pathlib import Path

from f1_telemetry_charts.charts.artifacts import ChartArtifact, write_metadata
from f1_telemetry_charts.charts.models import ChartSpec
from f1_telemetry_charts.config.models import ThemeConfig


class MatplotlibRenderer:
    def render(
        self,
        spec: ChartSpec,
        *,
        theme: ThemeConfig,
        output_dir: Path,
        artifact_id: str,
    ) -> ChartArtifact:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{artifact_id}.png"
        metadata_path = output_dir / f"{artifact_id}.json"

        figure, axis = plt.subplots(
            figsize=(theme.figure_width, theme.figure_height),
            dpi=theme.dpi,
        )
        figure.patch.set_facecolor(theme.background_color)
        axis.set_facecolor(theme.background_color)
        axis.set_title(spec.title, color=theme.foreground_color)
        axis.set_xlabel(spec.x_label, color=theme.foreground_color)
        axis.set_ylabel(spec.y_label, color=theme.foreground_color)
        axis.tick_params(colors=theme.foreground_color)
        if theme.grid:
            axis.grid(True, color="#d9e2ec", linewidth=0.8)

        for region in spec.shaded_regions:
            axis.axvspan(
                region.x_start,
                region.x_end,
                color=region.color,
                alpha=region.alpha,
                label=region.label,
            )

        for bar in spec.horizontal_bars:
            axis.barh(
                bar.y,
                bar.x_end - bar.x_start,
                left=bar.x_start,
                label=bar.label,
                color=bar.color,
                alpha=bar.alpha,
            )

        for series in spec.series:
            if series.render_mode == "step":
                axis.step(
                    series.x,
                    series.y,
                    where="post",
                    label=series.label,
                    color=series.color,
                )
            else:
                axis.plot(series.x, series.y, label=series.label, color=series.color)

        for marker in spec.vertical_markers:
            axis.axvline(
                marker.x,
                color=marker.color or theme.foreground_color,
                alpha=marker.alpha,
                linestyle=marker.line_style,
                label=marker.label,
            )

        if spec.x_axis_inverted:
            axis.invert_xaxis()
        if spec.y_axis_inverted:
            axis.invert_yaxis()

        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend()
        figure.tight_layout()
        figure.savefig(image_path)
        plt.close(figure)

        metadata = {
            "artifact_id": artifact_id,
            "recipe_id": spec.recipe_id,
            "title": spec.title,
            "source_session": spec.source_session,
            "selected_drivers": spec.selected_drivers,
            "series_count": len(spec.series),
            "warnings": spec.warnings,
            "renderer": "matplotlib",
            "x_axis_inverted": spec.x_axis_inverted,
            "y_axis_inverted": spec.y_axis_inverted,
            "vertical_markers": [
                marker.model_dump(mode="json") for marker in spec.vertical_markers
            ],
            "shaded_regions": [
                region.model_dump(mode="json") for region in spec.shaded_regions
            ],
            "horizontal_bars": [
                bar.model_dump(mode="json") for bar in spec.horizontal_bars
            ],
            **spec.metadata,
        }
        write_metadata(metadata_path, metadata)

        return ChartArtifact(
            artifact_id=artifact_id,
            image_path=image_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )
