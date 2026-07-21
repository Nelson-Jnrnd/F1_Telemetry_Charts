import type {
  HistoryItem,
  PackageView,
  PluginStatus,
  ProjectConfigForm,
  ReviewStatus,
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
