import type {
  AnalysisView,
  HistoryItem,
  PackageView,
  ParameterDiagnostics,
  PlaybackPayload,
  PluginStatus,
  ProjectConfigForm,
  ReportPlan,
  ReviewStatus,
  TrackMapPayload,
  ValidationResponse
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null && "detail" in payload ? String(payload.detail) : String(payload);
    throw new ApiError(message || "Request failed", response.status);
  }
  return payload as T;
}

const jsonHeaders = { "Content-Type": "application/json" };

export function getPackage() {
  return request<PackageView>("/api/package");
}

export function openPackage(path: string) {
  return request<PackageView>("/api/package/open", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ path })
  });
}

export function updateObservationReview(observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) {
  return request<PackageView>(`/api/package/observations/${observationId}/review`, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify({ review_status: reviewStatus, edited_text: editedText ?? null })
  });
}

export function regenerateDraft() {
  return request<PackageView>("/api/package/draft/regenerate", { method: "POST" });
}

export function validateConfig(config: ProjectConfigForm) {
  return request<ValidationResponse>("/api/config/validate", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ config })
  });
}

export function saveConfig(path: string, config: ProjectConfigForm) {
  return request<ValidationResponse>("/api/config/save", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ path, config })
  });
}

export function runConfig(config: ProjectConfigForm) {
  return request<{ status: string; output_dir: string; manifest_path: string; package: PackageView } | ValidationResponse>("/api/config/run", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ config })
  });
}

export function validatePlugins(enabled: boolean, localPaths: string[], entryPointsEnabled: boolean) {
  return request<PluginStatus[]>("/api/plugins/validate", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ enabled, local_paths: localPaths, entry_points_enabled: entryPointsEnabled })
  });
}

export function getHistory() {
  return request<HistoryItem[]>("/api/history");
}

export function clearHistory() {
  return request<{ status: string }>("/api/history", { method: "DELETE" });
}

export function getAnalysis() {
  return request<AnalysisView>("/api/analysis");
}

export function getAnalysisCoverage() {
  return request<Record<string, unknown>>("/api/analysis/coverage");
}

export function createAnalysis(path: string, name: string) {
  return request<AnalysisView>("/api/analysis/create", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ path, name })
  });
}

export function openAnalysis(path: string) {
  return request<AnalysisView>("/api/analysis/open", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ path })
  });
}

export function pickAnalysisDirectory(initialPath?: string | null) {
  return request<{ status: "selected" | "cancelled" | "unavailable"; path?: string | null; message?: string | null }>("/api/analysis/pick-directory", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ initial_path: initialPath ?? null })
  });
}

export function saveAnalysis() {
  return request<AnalysisView>("/api/analysis/save", { method: "POST" });
}

export function addAnalysisSession(payload: {
  name?: string | null;
  session: { season: number; event: string; session: string };
  drivers: string[];
  data_cache: { directory?: string; mode?: "cache-or-fetch" | "cache-only"; fixture_path?: string | null };
  load?: boolean;
}) {
  return request<AnalysisView>("/api/analysis/sessions", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function loadAnalysisSession(sessionId: string) {
  return request<AnalysisView>(`/api/analysis/sessions/${sessionId}/load`, { method: "POST" });
}

export function removeAnalysisSession(sessionId: string, confirmDeleteDependents: boolean) {
  return request<AnalysisView>(`/api/analysis/sessions/${sessionId}?confirm_delete_dependents=${confirmDeleteDependents}`, { method: "DELETE" });
}

export function addAnalysisChart(payload: { template_id: string; recipe_id?: string; target_session_ids: string[]; name?: string | null; parameters?: Record<string, unknown>; preset_id?: string | null }) {
  return request<AnalysisView>("/api/analysis/charts", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function updateAnalysisChart(chartId: string, payload: { name?: string | null; target_session_ids?: string[]; parameters?: Record<string, unknown>; preset_id?: string | null }) {
  return request<AnalysisView>(`/api/analysis/charts/${chartId}`, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function removeAnalysisChart(chartId: string) {
  return request<AnalysisView>(`/api/analysis/charts/${chartId}`, { method: "DELETE" });
}

export function generateAnalysisCharts(chartIds?: string[]) {
  return request<AnalysisView>("/api/analysis/charts/generate", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ chart_ids: chartIds ?? null })
  });
}

export function resolveAnalysisChartDiagnostics(payload: { template_id: string; recipe_id?: string; target_session_ids: string[]; parameters?: Record<string, unknown> }) {
  return request<ParameterDiagnostics>("/api/analysis/charts/diagnostics", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function getAnalysisTrackMap(payload: { template_id: string; recipe_id?: string; target_session_ids: string[]; parameters?: Record<string, unknown>; max_points?: number }) {
  return request<TrackMapPayload>("/api/analysis/track-map", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function getAnalysisPlayback(payload: {
  session_id: string;
  mode?: "time" | "lap";
  cursor?: number | null;
  start_lap?: number | null;
  end_lap?: number | null;
  selected_drivers?: string[] | null;
  max_frames?: number;
  max_markers?: number;
  max_points?: number;
  maximum_sample_gap_seconds?: number;
  maximum_timing_sample_age_seconds?: number;
}) {
  return request<PlaybackPayload>("/api/analysis/playback", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function refreshAnalysisReview() {
  return request<AnalysisView>("/api/analysis/review/refresh", { method: "POST" });
}

export function reviewAnalysisReportItem(
  itemId: string,
  payload: {
    review_status: "pending" | "accepted" | "edited" | "rejected";
    evidence_fingerprint: string;
    edited_text?: string | null;
  }
) {
  return request<AnalysisView>(`/api/analysis/report/items/${encodeURIComponent(itemId)}/review`, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function updateAnalysisReportPlan(plan: ReportPlan, evidenceFingerprint: string) {
  return request<AnalysisView>("/api/analysis/report/plan", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify({ plan, evidence_fingerprint: evidenceFingerprint })
  });
}

export function updateAnalysisPublication(
  plan: import("./types").PublicationPlan,
  editorial: import("./types").PublicationEditorial,
  evidenceFingerprint: string
) {
  return request<AnalysisView>("/api/analysis/publication", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify({ plan, editorial, evidence_fingerprint: evidenceFingerprint })
  });
}

export function regenerateAnalysisReportDraft() {
  return request<AnalysisView>("/api/analysis/report/draft/regenerate", { method: "POST" });
}

export function exportAnalysis() {
  return request<AnalysisView>("/api/analysis/export", { method: "POST" });
}

export function saveAnalysisPreset(payload: { template_id: string; recipe_id?: string; display_name: string; parameters: Record<string, unknown>; scope: "analysis" | "global"; notes?: string | null; replace_existing?: boolean }) {
  return request<AnalysisView>("/api/analysis/presets", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function updateAnalysisPreset(presetId: string, payload: { display_name?: string | null; parameters?: Record<string, unknown> | null; replace_existing?: boolean }) {
  return request<AnalysisView>(`/api/analysis/presets/${presetId}`, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  });
}

export function deleteAnalysisPreset(presetId: string) {
  return request<AnalysisView>(`/api/analysis/presets/${presetId}`, { method: "DELETE" });
}
