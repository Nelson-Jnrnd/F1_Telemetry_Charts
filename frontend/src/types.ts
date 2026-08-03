export type Page = "workbench" | "plugins" | "history";
export type HealthStatus = "healthy" | "warning" | "unhealthy";
export type ReviewStatus = "accepted" | "rejected" | "edited" | "unreviewed";

export type Finding = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  path?: string | null;
};

export type Artifact = {
  artifact_id: string;
  recipe_id: string;
  title?: string | null;
  image_path?: string | null;
  metadata_path?: string | null;
  [key: string]: unknown;
};

export type Manifest = {
  project_id?: string;
  created_at?: string;
  artifacts: Artifact[];
  markdown_path?: string | null;
  observations_path?: string | null;
  review_path?: string | null;
  [key: string]: unknown;
};

export type Observation = {
  observation_id: string;
  review_status: ReviewStatus;
  text: string;
  edited_text?: string | null;
  confidence?: string | number | null;
  evidence_artifact_ids?: string[];
  limitations?: string[];
  [key: string]: unknown;
};

export type PackageView = {
  package_path: string;
  manifest: Manifest | null;
  health: { status: HealthStatus; findings: Finding[] };
  observations: Observation[];
  review: unknown[];
  draft_markdown?: string | null;
};

export type PluginRecipe = {
  recipe_id: string;
  display_name: string;
  required_dataset_fields: string[];
  factory: string;
  output_artifact_types: string[];
};

export type PluginStatus = {
  plugin_id: string;
  display_name?: string | null;
  version?: string | null;
  provider?: string | null;
  source_type: "local_path" | "entry_point";
  source_location: string;
  status: "valid" | "invalid";
  recipes: PluginRecipe[];
  warnings: string[];
  errors: string[];
};

export type HistoryItem = {
  package_path: string;
  action: string;
  [key: string]: string;
};

export type ValidationResponse = {
  status: "valid" | "invalid" | "saved";
  config?: ProjectConfigForm | null;
  issues: { path: string; message: string }[];
};

export type SelectedDetail =
  | { kind: "observation"; value: Observation }
  | { kind: "finding"; value: Finding }
  | { kind: "plugin"; value: PluginStatus }
  | { kind: "recipe"; value: PluginRecipe & { plugin_id?: string; source?: string } }
  | { kind: "history"; value: HistoryItem }
  | { kind: "draft"; value: { markdownPath?: string | null; reviewCount: number } };

export type ParameterField = {
  name: string;
  label: string;
  field_type: "text" | "number" | "checkbox" | "select" | "multi_select" | "driver_selector" | "lap_range" | "color" | "color_map" | "numeric_range" | "object";
  required: boolean;
  default?: unknown;
  options: string[];
  minimum?: number | null;
  maximum?: number | null;
  group?: string | null;
  order: number;
  mode: "basic" | "advanced";
  visible_when: Record<string, unknown>;
  enabled_when: Record<string, unknown>;
  required_when: Record<string, unknown>;
  reset_group?: string | null;
};

export type RecipeParameterSchema = {
  recipe_id: string;
  schema_version: number;
  fields: ParameterField[];
};

export type AnalysisSession = {
  session_id: string;
  name: string;
  session: { season: number; event: string; session: string };
  drivers: string[];
  available_teams: string[];
  data_cache: { directory: string; mode: "cache-or-fetch" | "cache-only"; fixture_path: string | null };
  load_state: "not_loaded" | "loading" | "loaded" | "failed" | "stale";
  snapshot?: { snapshot_id: string; dataset_hash: string; dataset_path: string; snapshot_path: string } | null;
  stale: boolean;
  errors: string[];
};

export type ChartInstance = {
  chart_instance_id: string;
  recipe_id: string;
  name: string;
  target_session_ids: string[];
  enabled: boolean;
  parameters: Record<string, unknown>;
  parameter_hash: string;
  schema_version: number;
  preset_id?: string | null;
  order: number;
  generation_state: "not_generated" | "generated" | "failed" | "stale";
  artifact_id?: string | null;
  image_path?: string | null;
  metadata_path?: string | null;
  stale: boolean;
  observations_stale: boolean;
  errors: string[];
};

export type ParameterDiagnostics = {
  status: "valid" | "invalid";
  recipe_id: string;
  schema_version: number;
  parameters: Record<string, unknown>;
  errors: Array<{ field: string; message: string }>;
  warnings: Array<{ field: string; message: string }>;
  active_filter_summary: string[];
  exclusion_counts: Record<string, number>;
  effective_configuration: Record<string, unknown>;
  coverage_bounds: Record<string, unknown>;
  style_sources: Record<string, unknown>;
};

export type TrackMapPoint = {
  distance_m: number;
  x: number;
  y: number;
  display_x: number;
  display_y: number;
};

export type TrackMapMarker = {
  distance_m: number;
  display_x: number;
  display_y: number;
};

export type TrackMapSegment = {
  start_distance_m: number;
  end_distance_m: number;
  source: string;
  start_marker: TrackMapMarker;
  end_marker: TrackMapMarker;
  corner?: Record<string, unknown> | null;
};

export type TrackMapCorner = {
  label: string;
  number: number;
  letter?: string | null;
  distance_m?: number | null;
  display_x?: number | null;
  display_y?: number | null;
  source_x: number;
  source_y: number;
  source_distance_m?: number | null;
  projection_status: "fastf1_distance" | "nearest_geometry" | "unavailable";
  projection_error?: number | null;
};

export type TrackMapPayload = {
  status: "available" | "unavailable" | "invalid";
  recipe_id: string;
  session_id?: string | null;
  selected_drivers: string[];
  source_driver?: string | null;
  source_lap?: number | null;
  points: TrackMapPoint[];
  corners: TrackMapCorner[];
  segment?: TrackMapSegment | null;
  bounds: Record<string, unknown>;
  point_count: number;
  original_sample_count: number;
  max_points: number;
  downsampled: boolean;
  diagnostics: Array<{ field: string; message: string }>;
};

export type PlaybackMode = "time" | "lap";

export type PlaybackModeAvailability = {
  available: boolean;
  minimum?: number | null;
  maximum?: number | null;
  default?: number | null;
  reason?: string | null;
};

export type LeaderLapMarker = {
  lap_number: number;
  session_time_seconds: number;
  leader_driver: string;
};

export type PlaybackCursor = {
  mode: PlaybackMode;
  session_time_seconds: number;
  leader_lap_number?: number | null;
  leader_driver?: string | null;
  lap_offset_seconds?: number | null;
};

export type PlaybackMarker = {
  driver: string;
  status: "active" | "stale" | "missing";
  reason?: string | null;
  distance_m?: number | null;
  display_x?: number | null;
  display_y?: number | null;
  color?: string | null;
  source_lap?: number | null;
  source_sample_count: number;
  interpolation_method: "exact" | "linear" | "nearest" | "missing";
  interpolation_status: "exact" | "interpolated" | "stale" | "missing";
  sample_gap_seconds?: number | null;
  context: {
    lap_number?: number | null;
    lap_time_seconds?: number | null;
    position?: number | null;
    compound?: string | null;
    stint?: number | null;
    tyre_age_laps?: number | null;
    last_lap_time_seconds?: number | null;
    best_lap_time_seconds?: number | null;
    last_sector_times_seconds: Array<number | null>;
    best_sector_times_seconds: Array<number | null>;
    mini_sector_states: Array<"fastest" | "faster" | "slower" | "unavailable">;
    mini_sector_groups: Array<0 | 1 | 2 | 3>;
    timing_app_source?: string | null;
    track_status?: string | null;
    pit_state: "pit_in" | "pit_out" | "pit_in_out" | "none";
    gap_to_leader_seconds?: number | null;
    interval_to_ahead_seconds?: number | null;
    gap_to_leader_laps?: number | null;
    interval_to_ahead_laps?: number | null;
    gap_source?: string | null;
    gap_inferred: boolean;
    timing_status: "fresh" | "stale" | "missing";
    timing_sample_age_seconds?: number | null;
    timing_position?: number | null;
  };
};

export type PlaybackFrame = {
  mode: PlaybackMode;
  cursor_value: number;
  cursor: PlaybackCursor;
  lap_number?: number | null;
  session_time_seconds: number;
  markers: PlaybackMarker[];
  context: Record<string, unknown>;
};

export type PlaybackPayload = {
  status: "available" | "unavailable" | "invalid";
  session_id?: string | null;
  mode: PlaybackMode;
  default_mode: PlaybackMode;
  available_modes: Record<string, PlaybackModeAvailability>;
  selected_drivers: string[];
  points: TrackMapPoint[];
  leader_lap_markers: LeaderLapMarker[];
  frames: PlaybackFrame[];
  bounds: Record<string, unknown>;
  metadata: Record<string, unknown>;
  diagnostics: Array<{ field: string; message: string }>;
};

export type ParameterPreset = {
  preset_id: string;
  recipe_id: string;
  schema_version: number;
  display_name: string;
  scope: "analysis" | "global";
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  notes?: string | null;
};

export type AnalysisWorkspace = {
  analysis_id: string;
  name: string;
  root_path: string;
  schema_version: number;
  created_at: string;
  updated_at: string;
  sessions: AnalysisSession[];
  charts: ChartInstance[];
  presets: ParameterPreset[];
  review_stale: boolean;
  exported_package_path?: string | null;
  errors: string[];
};

export type AnalysisRecipe = PluginRecipe & {
  template_id: string;
  description?: string | null;
  source_type: "built_in" | "plugin";
  source_label: string;
  supported_session_count: { minimum: number; maximum: number };
  parameter_schema_version: number;
  availability_status: "available" | "unavailable" | "error";
  diagnostics: string[];
  source: string;
  parameter_schema: RecipeParameterSchema;
};

export type AnalysisView = {
  analysis: AnalysisWorkspace;
  recipe_schemas: RecipeParameterSchema[];
  recipes: AnalysisRecipe[];
  global_presets: ParameterPreset[];
};

export type ProjectConfigForm = {
  schema_version: 1;
  project_id: string;
  output_dir: string;
  session: {
    season: number;
    event: string;
    session: string;
  };
  driver_selection: {
    drivers: string[];
  };
  data_cache: {
    directory: string;
    mode: "cache-or-fetch" | "cache-only";
    fixture_path: string | null;
  };
  recipes: {
    recipe_id: string;
    enabled: boolean;
    title: string | null;
  }[];
  theme: {
    name: string;
    figure_width: number;
    figure_height: number;
    dpi: number;
    background_color: string;
    foreground_color: string;
    grid: boolean;
  };
  exports: {
    formats: ("png" | "json")[];
  };
  plugins: {
    enabled: boolean;
    local_paths: string[];
    entry_points_enabled: boolean;
  };
};
