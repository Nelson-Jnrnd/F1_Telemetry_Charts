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

        for series in spec.series:
            axis.plot(series.x, series.y, label=series.label, color=series.color)

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
            **spec.metadata,
        }
        write_metadata(metadata_path, metadata)

        return ChartArtifact(
            artifact_id=artifact_id,
            image_path=image_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )
