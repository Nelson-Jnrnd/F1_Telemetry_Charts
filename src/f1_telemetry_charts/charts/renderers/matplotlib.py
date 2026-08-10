"""Matplotlib chart renderer."""

from __future__ import annotations

from pathlib import Path

from f1_telemetry_charts.charts.artifacts import ChartArtifact, write_metadata
from f1_telemetry_charts.charts.models import ChartSpec, PanelSpec
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

        if spec.panels:
            return self._render_panels(
                spec,
                theme=theme,
                image_path=image_path,
                metadata_path=metadata_path,
                artifact_id=artifact_id,
            )

        figure, axis = plt.subplots(
            figsize=(theme.figure_width, theme.figure_height),
            dpi=theme.dpi,
        )
        figure.patch.set_facecolor(theme.background_color)
        axis.set_facecolor(theme.background_color)
        excluded_axis = None
        excluded_series = [
            series for series in spec.series if series.render_mode == "excluded_strip"
        ]
        title_axis = axis
        if excluded_series:
            from mpl_toolkits.axes_grid1 import make_axes_locatable

            excluded_axis = make_axes_locatable(axis).append_axes(
                "top",
                size="7%",
                pad=0.08,
                sharex=axis,
            )
            excluded_axis.set_facecolor("#F3F4F6")
            excluded_axis.set_ylim(-0.75, max(series.y[0] for series in excluded_series) + 0.75)
            excluded_axis.set_yticks([])
            excluded_axis.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
            excluded_axis.grid(False)
            excluded_axis.text(
                -0.01,
                0.5,
                "Excluded laps",
                transform=excluded_axis.transAxes,
                ha="right",
                va="center",
                fontsize=7,
                color=theme.foreground_color,
                clip_on=False,
            )
            title_axis = excluded_axis
        title_axis.set_title(
            spec.title,
            color=theme.foreground_color,
            pad=26 if spec.subtitle else 6,
        )
        if spec.subtitle:
            title_axis.text(
                0.5,
                1.01,
                spec.subtitle,
                transform=title_axis.transAxes,
                ha="center",
                va="bottom",
                fontsize=9,
                color=theme.foreground_color,
            )
        axis.set_xlabel(spec.x_label, color=theme.foreground_color)
        axis.set_ylabel(spec.y_label, color=theme.foreground_color)
        axis.tick_params(colors=theme.foreground_color)
        if theme.grid:
            axis.set_axisbelow(True)
            axis.grid(True, color="#d9e2ec", linewidth=0.8)

        for bar in spec.horizontal_bars:
            axis.barh(
                bar.y,
                bar.x_end - bar.x_start,
                left=bar.x_start,
                label=bar.label,
                color=bar.color,
                alpha=bar.alpha,
                height=bar.height,
                edgecolor=bar.edge_color,
                hatch=bar.hatch,
            )

        for summary in spec.box_summaries:
            from matplotlib.patches import Rectangle

            axis.add_patch(
                Rectangle(
                    (summary.x - summary.width / 2, summary.q1),
                    summary.width,
                    summary.q3 - summary.q1,
                    facecolor=summary.face_color,
                    edgecolor=summary.edge_color,
                    alpha=summary.alpha,
                    linewidth=1.4,
                    zorder=3,
                )
            )
            axis.hlines(
                summary.median,
                summary.x - summary.width / 2,
                summary.x + summary.width / 2,
                color=summary.edge_color,
                linewidth=2.2,
                zorder=4,
            )

        for region in spec.shaded_regions:
            axis.axvspan(
                region.x_start,
                region.x_end,
                color=region.color,
                alpha=region.alpha,
                label=region.label,
            )
            if region.annotation:
                axis.text(
                    (region.x_start + region.x_end) / 2,
                    0.98,
                    region.annotation,
                    transform=axis.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize=8,
                    fontweight="bold",
                    color=theme.foreground_color,
                )

        for marker in spec.horizontal_markers:
            axis.axhline(
                marker.y,
                color=marker.color or theme.foreground_color,
                alpha=marker.alpha,
                linestyle=marker.line_style,
                linewidth=marker.line_width,
                label=marker.label,
            )

        for series in spec.series:
            if series.render_mode == "excluded_strip":
                if excluded_axis is not None:
                    excluded_axis.scatter(
                        series.x,
                        series.y,
                        label=series.label,
                        edgecolors=series.color,
                        facecolors="none",
                        marker=series.marker or "o",
                        linewidths=1.4,
                        s=series.marker_size,
                    )
                continue
            if series.render_mode == "step":
                axis.step(
                    series.x,
                    series.y,
                    where="post",
                    label=series.label,
                    color=series.color,
                    linestyle=series.line_style,
                    marker=series.marker,
                    markersize=series.marker_size ** 0.5,
                )
            elif series.render_mode == "scatter":
                axis.scatter(
                    series.x,
                    series.y,
                    label=series.label,
                    color=series.color,
                    edgecolors=series.edge_color,
                    linewidths=1.0 if series.edge_color else None,
                    marker=series.marker or "o",
                    s=series.marker_size,
                )
            elif series.render_mode == "excluded":
                axis.scatter(
                    series.x,
                    series.y,
                    label=series.label,
                    color=series.color,
                    marker="x",
                    alpha=0.7,
                    s=series.marker_size,
                )
            else:
                axis.plot(
                    series.x,
                    series.y,
                    label=series.label,
                    color=series.color,
                    linestyle=series.line_style,
                    marker=series.marker,
                    markersize=series.marker_size ** 0.5,
                )

        for marker in spec.vertical_markers:
            axis.axvline(
                marker.x,
                color=marker.color or theme.foreground_color,
                alpha=marker.alpha,
                linestyle=marker.line_style,
                label=marker.label,
            )

        for annotation in spec.annotations:
            axis.text(
                annotation.x,
                annotation.y,
                annotation.text,
                color=annotation.color,
                fontsize=annotation.font_size,
                fontweight=annotation.font_weight,
                ha=annotation.horizontal_alignment,
                va="center",
            )

        if spec.x_axis_inverted:
            axis.invert_xaxis()
        if spec.x_limits is not None:
            axis.set_xlim(*spec.x_limits)
        if spec.y_limits is not None:
            axis.set_ylim(*spec.y_limits)
        _apply_x_tick_labels(axis, spec.x_tick_labels)
        _apply_y_tick_labels(axis, spec.y_tick_labels)
        if spec.y_axis_inverted:
            axis.invert_yaxis()

        handles, labels = _deduplicated_legend(
            axis,
            spec.legend_order,
            additional_axes=[excluded_axis] if excluded_axis is not None else None,
        )
        if handles:
            axis.legend(
                handles,
                labels,
                ncol=min(5, len(handles)),
                fontsize=8,
                loc=spec.legend_location,
            )
        if spec.summary_lines:
            axis.text(
                0.015,
                0.975,
                "\n".join(spec.summary_lines),
                transform=axis.transAxes,
                ha="left",
                va="top",
                fontsize=8,
                color=theme.foreground_color,
                bbox={
                    "boxstyle": "round,pad=0.45",
                    "facecolor": theme.background_color,
                    "edgecolor": "#CBD5E1",
                    "alpha": 0.94,
                },
            )
        figure.tight_layout()
        figure.savefig(image_path)
        plt.close(figure)

        metadata = {
            "artifact_id": artifact_id,
            "recipe_id": spec.recipe_id,
            "title": spec.title,
            "subtitle": spec.subtitle,
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
            "horizontal_markers": [
                marker.model_dump(mode="json") for marker in spec.horizontal_markers
            ],
            "shaded_regions": [
                region.model_dump(mode="json") for region in spec.shaded_regions
            ],
            "horizontal_bars": [
                bar.model_dump(mode="json") for bar in spec.horizontal_bars
            ],
            "box_summaries": [
                summary.model_dump(mode="json") for summary in spec.box_summaries
            ],
            "annotations": [
                annotation.model_dump(mode="json") for annotation in spec.annotations
            ],
            "x_tick_labels": spec.x_tick_labels,
            "y_tick_labels": spec.y_tick_labels,
            "summary_lines": spec.summary_lines,
            "x_limits": spec.x_limits,
            "y_limits": spec.y_limits,
            "legend_order": spec.legend_order,
            "legend_location": spec.legend_location,
            **spec.metadata,
        }
        write_metadata(metadata_path, metadata)

        return ChartArtifact(
            artifact_id=artifact_id,
            image_path=image_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )

    def _render_panels(
        self,
        spec: ChartSpec,
        *,
        theme: ThemeConfig,
        image_path: Path,
        metadata_path: Path,
        artifact_id: str,
    ) -> ChartArtifact:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        figure, axes = plt.subplots(
            nrows=len(spec.panels),
            ncols=1,
            figsize=(theme.figure_width, theme.figure_height),
            dpi=theme.dpi,
            squeeze=False,
            gridspec_kw={
                "height_ratios": [panel.height_ratio for panel in spec.panels]
            },
        )
        figure.patch.set_facecolor(theme.background_color)
        figure.suptitle(spec.title, color=theme.foreground_color, y=0.98)
        if spec.subtitle:
            figure.text(
                0.5,
                0.945,
                spec.subtitle,
                ha="center",
                va="top",
                fontsize=9,
                color=theme.foreground_color,
            )
        for axis, panel in zip(axes[:, 0], spec.panels):
            axis.set_facecolor(theme.background_color)
            axis.set_title(panel.title, color=theme.foreground_color, loc="left", fontsize=10)
            axis.set_xlabel(panel.x_label, color=theme.foreground_color)
            axis.set_ylabel(panel.y_label, color=theme.foreground_color)
            axis.tick_params(colors=theme.foreground_color)
            if theme.grid:
                axis.set_axisbelow(True)
                axis.grid(True, color="#d9e2ec", linewidth=0.8)
            _draw_panel(axis, panel, theme.foreground_color)
            if panel.x_limits is not None:
                axis.set_xlim(*panel.x_limits)
            if panel.y_limits is not None:
                axis.set_ylim(*panel.y_limits)
            _apply_x_tick_labels(axis, panel.x_tick_labels)
            _apply_y_tick_labels(axis, panel.y_tick_labels)
            if panel.y_axis_inverted:
                axis.invert_yaxis()
            handles, labels = _deduplicated_legend(axis)
            if handles:
                axis.legend(handles, labels, fontsize=7, ncol=min(5, len(handles)))
            if panel.summary_lines:
                axis.text(
                    0.015,
                    0.975,
                    "\n".join(panel.summary_lines),
                    transform=axis.transAxes,
                    ha="left",
                    va="top",
                    fontsize=7,
                    color=theme.foreground_color,
                    bbox={
                        "boxstyle": "round,pad=0.4",
                        "facecolor": theme.background_color,
                        "edgecolor": "#CBD5E1",
                        "alpha": 0.94,
                    },
                )
            if not panel.show_axes:
                axis.set_axis_off()
        figure.tight_layout(rect=(0, 0, 1, 0.91 if spec.subtitle else 0.95))
        figure.savefig(image_path)
        plt.close(figure)
        metadata = {
            "artifact_id": artifact_id,
            "recipe_id": spec.recipe_id,
            "title": spec.title,
            "subtitle": spec.subtitle,
            "source_session": spec.source_session,
            "selected_drivers": spec.selected_drivers,
            "series_count": sum(len(panel.series) for panel in spec.panels),
            "warnings": spec.warnings,
            "renderer": "matplotlib",
            "panel_count": len(spec.panels),
            "panels": [panel.model_dump(mode="json") for panel in spec.panels],
            **spec.metadata,
        }
        write_metadata(metadata_path, metadata)
        return ChartArtifact(
            artifact_id=artifact_id,
            image_path=image_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )


def _draw_panel(axis, panel: PanelSpec, foreground_color: str) -> None:
    for bar in panel.horizontal_bars:
        axis.barh(
            bar.y,
            bar.x_end - bar.x_start,
            left=bar.x_start,
            label=bar.label,
            color=bar.color,
            alpha=bar.alpha,
            height=bar.height,
            edgecolor=bar.edge_color,
            hatch=bar.hatch,
        )
    for summary in panel.box_summaries:
        from matplotlib.patches import Rectangle

        axis.add_patch(
            Rectangle(
                (summary.x - summary.width / 2, summary.q1),
                summary.width,
                summary.q3 - summary.q1,
                facecolor=summary.face_color,
                edgecolor=summary.edge_color,
                alpha=summary.alpha,
                linewidth=1.4,
                zorder=3,
            )
        )
        axis.hlines(
            summary.median,
            summary.x - summary.width / 2,
            summary.x + summary.width / 2,
            color=summary.edge_color,
            linewidth=2.2,
            zorder=4,
        )
    for region in panel.shaded_regions:
        axis.axvspan(
            region.x_start,
            region.x_end,
            color=region.color,
            alpha=region.alpha,
            label=region.label,
        )
        if region.annotation:
            axis.text(
                (region.x_start + region.x_end) / 2,
                0.98,
                region.annotation,
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
                fontweight="bold",
                color=foreground_color,
            )
    for marker in panel.horizontal_markers:
        axis.axhline(
            marker.y,
            color=marker.color or foreground_color,
            alpha=marker.alpha,
            linestyle=marker.line_style,
            linewidth=marker.line_width,
            label=marker.label,
        )
    for series in panel.series:
        if series.render_mode == "step":
            axis.step(
                series.x,
                series.y,
                where="post",
                label=series.label,
                color=series.color,
                linestyle=series.line_style,
                marker=series.marker,
                markersize=series.marker_size ** 0.5,
            )
        elif series.render_mode == "scatter":
            axis.scatter(
                series.x,
                series.y,
                label=series.label,
                color=series.color,
                edgecolors=series.edge_color,
                linewidths=1.0 if series.edge_color else None,
                marker=series.marker or "o",
                s=series.marker_size,
            )
        elif series.render_mode == "excluded":
            axis.scatter(
                series.x,
                series.y,
                label=series.label,
                color=series.color,
                marker="x",
                alpha=0.7,
                s=series.marker_size,
            )
        else:
            axis.plot(
                series.x,
                series.y,
                label=series.label,
                color=series.color,
                linestyle=series.line_style,
                marker=series.marker,
                markersize=series.marker_size ** 0.5,
            )
    for marker in panel.vertical_markers:
        axis.axvline(
            marker.x,
            color=marker.color or foreground_color,
            alpha=marker.alpha,
            linestyle=marker.line_style,
            label=marker.label,
        )
        if marker.annotation:
            axis.text(
                marker.x,
                0.98,
                marker.annotation,
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=7,
                fontweight="bold",
                color=marker.color or foreground_color,
            )
    if panel.state_message:
        axis.text(
            0.5,
            0.5,
            panel.state_message,
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color=foreground_color,
            bbox={
                "boxstyle": "round,pad=0.6",
                "facecolor": "#F8FAFC",
                "edgecolor": "#CBD5E1",
                "alpha": 0.95,
            },
        )
    for block in panel.info_blocks:
        axis.text(
            block.x,
            block.y,
            block.text,
            transform=axis.transAxes,
            ha=block.horizontal_alignment,
            va="center",
            fontsize=block.font_size,
            color=foreground_color,
            bbox={
                "boxstyle": "round,pad=0.5",
                "facecolor": "#F8FAFC",
                "edgecolor": "#CBD5E1",
                "alpha": 0.95,
            },
        )
    for annotation in panel.annotations:
        axis.text(
            annotation.x,
            annotation.y,
            annotation.text,
            color=annotation.color,
            fontsize=annotation.font_size,
            fontweight=annotation.font_weight,
            ha=annotation.horizontal_alignment,
            va="center",
        )


def _apply_y_tick_labels(axis, labels: dict[float, str]) -> None:
    if not labels:
        return
    positions = sorted(labels)
    axis.set_yticks(positions, [labels[position] for position in positions])


def _apply_x_tick_labels(axis, labels: dict[float, str]) -> None:
    if not labels:
        return
    positions = sorted(labels)
    axis.set_xticks(positions, [labels[position] for position in positions])


def _deduplicated_legend(
    axis,
    preferred_order: list[str] | None = None,
    additional_axes: list | None = None,
):
    handles, labels = axis.get_legend_handles_labels()
    for additional_axis in additional_axes or []:
        additional_handles, additional_labels = additional_axis.get_legend_handles_labels()
        handles.extend(additional_handles)
        labels.extend(additional_labels)
    unique: dict[str, object] = {}
    for handle, label in zip(handles, labels):
        if not label or label.startswith("_") or label in unique:
            continue
        unique[label] = handle
    priority = {
        "Soft": 10,
        "Medium": 20,
        "Hard": 30,
        "Intermediate": 40,
        "Wet": 50,
        "Unknown compound": 60,
        "Pit stop": 70,
        "Safety Car": 80,
        "VSC": 90,
        "Red flag": 100,
    }
    insertion_order = {label: index for index, label in enumerate(unique)}
    preferred = {
        label: index for index, label in enumerate(preferred_order or [])
    }
    ordered = sorted(
        unique.items(),
        key=lambda item: (
            preferred.get(item[0], len(preferred))
            if preferred
            else priority.get(item[0], 1000),
            insertion_order[item[0]],
        ),
    )
    return [handle for _, handle in ordered], [label for label, _ in ordered]
