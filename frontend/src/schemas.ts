import { z } from "zod";
import type { ProjectConfigForm } from "./types";

export const coreRecipes = [
  { recipe_id: "lap_time_delta", display_name: "Lap time delta" },
  { recipe_id: "position_progression", display_name: "Position progression" },
  { recipe_id: "telemetry_trace", display_name: "Telemetry trace" },
  { recipe_id: "tyre_strategy", display_name: "Tyre strategy" }
] as const;

export const configSchema = z.object({
  schema_version: z.literal(1),
  project_id: z.string().trim().min(1, "Project ID is required."),
  output_dir: z.string().trim().min(1, "Output directory is required."),
  session: z.object({
    season: z.coerce.number().int().min(1950, "Season must be 1950 or later."),
    event: z.string().trim().min(1, "Event is required."),
    session: z.string().trim().min(1, "Session is required.")
  }),
  driver_selection: z.object({
    drivers: z.array(z.string().trim().min(1)).min(1, "Add at least one driver.")
  }),
  data_cache: z.object({
    directory: z.string().trim().min(1, "Cache directory is required."),
    mode: z.enum(["cache-or-fetch", "cache-only"]),
    fixture_path: z.string().trim().nullable()
  }),
  recipes: z
    .array(
      z.object({
        recipe_id: z.string().trim().min(1),
        enabled: z.boolean(),
        title: z.string().trim().nullable()
      })
    )
    .min(1, "Select at least one recipe."),
  theme: z.object({
    name: z.string().trim().min(1),
    figure_width: z.coerce.number().positive(),
    figure_height: z.coerce.number().positive(),
    dpi: z.coerce.number().int().min(72).max(600),
    background_color: z.string().trim().min(1),
    foreground_color: z.string().trim().min(1),
    grid: z.boolean()
  }),
  exports: z.object({
    formats: z.array(z.enum(["png", "json"])).min(1, "Select at least one export format.")
  }),
  plugins: z.object({
    enabled: z.boolean(),
    local_paths: z.array(z.string().trim()),
    entry_points_enabled: z.boolean()
  })
});

export const defaultConfig: ProjectConfigForm = {
  schema_version: 1,
  project_id: "ui-run",
  output_dir: "runs",
  session: { season: 2023, event: "Bahrain Grand Prix", session: "Race" },
  driver_selection: { drivers: ["VER", "PER"] },
  data_cache: {
    directory: ".cache/fastf1",
    mode: "cache-or-fetch",
    fixture_path: "tests/fixtures/2023_bahrain_race_dataset.json"
  },
  recipes: [{ recipe_id: "lap_time_delta", enabled: true, title: null }],
  theme: {
    name: "technical_editorial",
    figure_width: 16,
    figure_height: 9,
    dpi: 300,
    background_color: "#ffffff",
    foreground_color: "#1f2933",
    grid: true
  },
  exports: { formats: ["png", "json"] },
  plugins: { enabled: false, local_paths: [], entry_points_enabled: false }
};
