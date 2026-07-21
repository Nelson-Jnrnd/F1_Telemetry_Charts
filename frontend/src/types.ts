export type Page = "preview" | "workbench" | "plugins" | "history";
export type PreviewTab = "charts" | "observations" | "draft" | "integrity";
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
