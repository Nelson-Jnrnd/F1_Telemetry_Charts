import { useEffect, useMemo, useState } from "react";
import * as api from "./api";
import { AppShell } from "./components/AppShell";
import { ChartLightbox } from "./components/ChartLightbox";
import { DetailPanel } from "./components/DetailPanel";
import { ToastRegion, type AppToast } from "./components/ui/Toast";
import { PackagePreviewPage } from "./pages/PackagePreviewPage";
import { PluginsPage } from "./pages/PluginsPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import type {
  Artifact,
  HistoryItem,
  Observation,
  PackageView,
  Page,
  PluginStatus,
  PreviewTab,
  ProjectConfigForm,
  ReviewStatus,
  SelectedDetail,
  ValidationResponse
} from "./types";

export function App() {
  const [page, setPage] = useState<Page>("preview");
  const [tab, setTab] = useState<PreviewTab>("charts");
  const [packagePath, setPackagePath] = useState("");
  const [view, setView] = useState<PackageView | null>(null);
  const [selected, setSelected] = useState<SelectedDetail | null>(null);
  const [overlayArtifact, setOverlayArtifact] = useState<Artifact | null>(null);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [toasts, setToasts] = useState<AppToast[]>([]);

  useEffect(() => {
    loadInitialPackage();
    refreshHistory();
  }, []);

  const healthLabel = useMemo(() => view?.health.status ?? "no package", [view]);

  function notify(title: string, description?: string, tone: AppToast["tone"] = "info") {
    setToasts((current) => [...current, { id: Date.now() + Math.random(), title, description, tone }]);
  }

  async function loadInitialPackage() {
    try {
      const payload = await api.getPackage();
      setView(payload);
      setPackagePath(payload.package_path);
      setPage("preview");
      setSelected(null);
    } catch {
      setPage("workbench");
    }
  }

  async function refreshHistory() {
    try {
      setHistory(await api.getHistory());
    } catch {
      setHistory([]);
    }
  }

  async function openPackageAt(path = packagePath) {
    try {
      const payload = await api.openPackage(path);
      setView(payload);
      setPackagePath(payload.package_path);
      setSelected(null);
      setPage("preview");
      notify("Package opened", payload.package_path, "success");
      await refreshHistory();
    } catch (error) {
      notify("Package open failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function updateObservation(observation: Observation, status: ReviewStatus, editedText?: string | null) {
    try {
      const payload = await api.updateObservationReview(observation.observation_id, status, editedText);
      setView(payload);
      const updated = payload.observations.find((item) => item.observation_id === observation.observation_id);
      if (updated) setSelected({ kind: "observation", value: updated });
      notify("Review saved", `${observation.observation_id} is now ${status}.`, "success");
    } catch (error) {
      notify("Review update failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function regenerateDraft() {
    try {
      const payload = await api.regenerateDraft();
      setView(payload);
      setSelected({ kind: "draft", value: { markdownPath: payload.manifest?.markdown_path, reviewCount: payload.review.length } });
      notify("Draft regenerated", "draft.md was rebuilt from saved review state.", "success");
    } catch (error) {
      notify("Draft regeneration failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function validateConfig(config: ProjectConfigForm) {
    try {
      const payload = await api.validateConfig(config);
      setValidation(payload);
      notify(payload.status === "valid" ? "Config valid" : "Config invalid", `${payload.issues.length} backend issue(s).`, payload.status === "valid" ? "success" : "warning");
    } catch (error) {
      notify("Config validation failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function saveConfig(path: string, config: ProjectConfigForm) {
    try {
      const payload = await api.saveConfig(path, config);
      setValidation(payload);
      notify(payload.status === "saved" ? "Config saved" : "Config not saved", path, payload.status === "saved" ? "success" : "warning");
    } catch (error) {
      notify("Config save failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function runConfig(config: ProjectConfigForm) {
    try {
      const payload = await api.runConfig(config);
      if ("package" in payload) {
        setView(payload.package);
        setPackagePath(payload.output_dir);
        setSelected(null);
        setPage("preview");
        notify("Analysis run finished", payload.output_dir, "success");
        await refreshHistory();
      } else {
        setValidation(payload);
        notify("Analysis run blocked", `${payload.issues.length} validation issue(s).`, "warning");
      }
    } catch (error) {
      notify("Analysis run failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function validatePlugins(enabled: boolean, localPaths: string[], entryPointsEnabled: boolean) {
    try {
      const payload = await api.validatePlugins(enabled, localPaths, entryPointsEnabled);
      setPlugins(payload);
      notify("Plugins validated", `${payload.length} plugin result(s).`, payload.some((plugin) => plugin.status === "invalid") ? "warning" : "success");
    } catch (error) {
      notify("Plugin validation failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  async function clearHistory() {
    try {
      await api.clearHistory();
      await refreshHistory();
      notify("History cleared", "Package and config files were not deleted.", "success");
    } catch (error) {
      notify("History clear failed", error instanceof Error ? error.message : String(error), "error");
    }
  }

  return (
    <>
      <AppShell
        page={page}
        setPage={setPage}
        packagePath={packagePath}
        healthStatus={healthLabel}
        detail={<DetailPanel selected={selected} />}
      >
        {page === "preview" && (
          <PackagePreviewPage
            view={view}
            tab={tab}
            setTab={setTab}
            packagePath={packagePath}
            setPackagePath={setPackagePath}
            openPackage={() => openPackageAt()}
            setSelected={setSelected}
            setOverlayArtifact={setOverlayArtifact}
            regenerateDraft={regenerateDraft}
            updateObservation={updateObservation}
          />
        )}
        {page === "workbench" && (
          <WorkbenchPage validation={validation} plugins={plugins} onValidate={validateConfig} onSave={saveConfig} onRun={runConfig} setSelected={setSelected} />
        )}
        {page === "plugins" && <PluginsPage plugins={plugins} validatePlugins={validatePlugins} setSelected={setSelected} />}
        {page === "history" && <RunHistoryPage history={history} clearHistory={clearHistory} setSelected={setSelected} openHistoryPackage={openPackageAt} />}
      </AppShell>
      <ChartLightbox artifact={overlayArtifact} onOpenChange={(open) => !open && setOverlayArtifact(null)} />
      <ToastRegion toasts={toasts} dismiss={(id) => setToasts((current) => current.filter((toast) => toast.id !== id))} />
    </>
  );
}
