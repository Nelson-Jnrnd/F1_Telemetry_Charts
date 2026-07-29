import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import { AppShell, type SidebarRenderer } from "./components/AppShell";
import { ChartLightbox } from "./components/ChartLightbox";
import { DetailPanel } from "./components/DetailPanel";
import { ToastRegion, type AppToast } from "./components/ui/Toast";
import { AnalysisWorkbenchPage } from "./pages/AnalysisWorkbenchPage";
import { PluginsPage } from "./pages/PluginsPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import type {
  Artifact,
  HistoryItem,
  Page,
  PluginStatus,
  SelectedDetail
} from "./types";

export function App() {
  const [page, setPage] = useState<Page>("workbench");
  const [selected, setSelected] = useState<SelectedDetail | null>(null);
  const [overlayArtifact, setOverlayArtifact] = useState<Artifact | null>(null);
  const [overlayAssetBase, setOverlayAssetBase] = useState("/api/package/assets");
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [toasts, setToasts] = useState<AppToast[]>([]);
  const [workbenchSidebar, setWorkbenchSidebar] = useState<SidebarRenderer | null>(null);

  useEffect(() => {
    refreshHistory();
  }, []);

  function notify(title: string, description?: string, tone: AppToast["tone"] = "info") {
    setToasts((current) => [...current, { id: Date.now() + Math.random(), title, description, tone }]);
  }

  async function refreshHistory() {
    setHistoryLoading(true);
    try {
      setHistory(await api.getHistory());
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  function openOverlayArtifact(artifact: Artifact, assetBase = "/api/package/assets") {
    setOverlayAssetBase(assetBase);
    setOverlayArtifact(artifact);
  }

  const registerWorkbenchSidebar = useCallback((renderer: SidebarRenderer | null) => {
    setWorkbenchSidebar(() => renderer);
  }, []);

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
        sidebarContent={page === "workbench" ? workbenchSidebar : null}
        detail={page === "workbench" ? undefined : <DetailPanel selected={selected} />}
      >
        {page === "workbench" && (
          <AnalysisWorkbenchPage notify={notify} openArtifact={openOverlayArtifact} refreshHistory={refreshHistory} setSidebarContent={registerWorkbenchSidebar} />
        )}
        {page === "plugins" && <PluginsPage plugins={plugins} validatePlugins={validatePlugins} setSelected={setSelected} />}
        {page === "history" && <RunHistoryPage history={history} historyLoading={historyLoading} clearHistory={clearHistory} setSelected={setSelected} />}
      </AppShell>
      <ChartLightbox artifact={overlayArtifact} assetBase={overlayAssetBase} onOpenChange={(open) => !open && setOverlayArtifact(null)} />
      <ToastRegion toasts={toasts} dismiss={(id) => setToasts((current) => current.filter((toast) => toast.id !== id))} />
    </>
  );
}
