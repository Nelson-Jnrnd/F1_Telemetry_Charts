import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent, type PointerEvent, type ReactNode, type WheelEvent } from "react";
import { BarChart3, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, ClipboardCheck, Download, Edit3, FilePlus2, FolderOpen, Image, LineChart, Loader2, Map as MapIcon, Maximize2, Play, Plus, RefreshCw, RotateCcw, RotateCw, Save, Trash2, XCircle, ZoomIn, ZoomOut } from "lucide-react";
import * as api from "../api";
import type { AnalysisSession, AnalysisView, Artifact, ChartInstance, Observation, PackageView, ParameterDiagnostics, ParameterField, ParameterPreset, PlaybackMarker, PlaybackMode, PlaybackPayload, ReviewStatus, TrackMapCorner, TrackMapPayload, TrackMapPoint } from "../types";
import { compactPath, cn } from "../lib/utils";
import type { SidebarRenderer } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { CheckboxField } from "../components/ui/CheckboxField";
import { Dialog } from "../components/ui/Dialog";
import { Field, TextAreaField } from "../components/ui/Field";
import { Panel } from "../components/ui/Panel";
import { SelectField } from "../components/ui/SelectField";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { AppToast } from "../components/ui/Toast";

type AnalysisSelection =
  | { kind: "overview" }
  | { kind: "new-session" }
  | { kind: "session"; id: string }
  | { kind: "new-chart" }
  | { kind: "chart"; id: string }
  | { kind: "playback" }
  | { kind: "review" }
  | { kind: "export" };

type AnalysisWorkbenchPageProps = {
  notify: (title: string, description?: string, tone?: AppToast["tone"]) => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
  refreshHistory: () => Promise<void>;
  setSidebarContent?: (renderer: SidebarRenderer | null) => void;
};

const defaultSession = {
  season: 2023,
  event: "Bahrain Grand Prix",
  session: "Race",
  drivers: "ALL",
  dataSource: "fastf1" as "fastf1" | "local",
  localDatasetPath: "tests/fixtures/2023_bahrain_race_dataset.json",
  cacheDirectory: ".cache/fastf1",
  cacheMode: "cache-or-fetch" as "cache-or-fetch" | "cache-only"
};

type ChartPendingAction = "saving" | "generating" | "removing";
type AnalysisPendingAction = "creating" | "opening" | "saving";
type SessionPendingAction = "loading" | "removing";
type PresetPendingAction = "saving" | "replacing" | "renaming" | "deleting";
type ObservationPendingAction = "accepting" | "rejecting" | "saving" | "clearing";

const noPresetValue = "__none__";
const inspectorMinWidth = 300;
const inspectorMaxWidth = 560;
const inspectorDefaultWidth = 360;

export function AnalysisWorkbenchPage({ notify, openArtifact, refreshHistory, setSidebarContent }: AnalysisWorkbenchPageProps) {
  const [view, setView] = useState<AnalysisView | null>(null);
  const [exportedPackage, setExportedPackage] = useState<PackageView | null>(null);
  const [selection, setSelection] = useState<AnalysisSelection>({ kind: "overview" });
  const [sessionsOpen, setSessionsOpen] = useState(true);
  const [chartsOpen, setChartsOpen] = useState(true);
  const [newAnalysisOpen, setNewAnalysisOpen] = useState(false);
  const [openAnalysisOpen, setOpenAnalysisOpen] = useState(false);
  const [analysisPath, setAnalysisPath] = useState("analyses/race-analysis");
  const [analysisName, setAnalysisName] = useState("Race Analysis");
  const [sessionDraft, setSessionDraft] = useState(defaultSession);
  const [chartDraft, setChartDraft] = useState({
    recipeId: "lap_time_delta",
    sessionId: "",
    name: "Lap time delta",
    title: "Lap time delta",
    parameters: { title: "Lap time delta" } as Record<string, unknown>,
    presetId: noPresetValue,
    presetName: "Lap time delta",
    saveGlobal: false
  });
  const [initialLoading, setInitialLoading] = useState(true);
  const [packageLoading, setPackageLoading] = useState(false);
  const [analysisPending, setAnalysisPending] = useState<AnalysisPendingAction | null>(null);
  const [sessionDraftPending, setSessionDraftPending] = useState(false);
  const [pendingSessionActions, setPendingSessionActions] = useState<Record<string, SessionPendingAction>>({});
  const [chartDraftPending, setChartDraftPending] = useState(false);
  const [pendingChartActions, setPendingChartActions] = useState<Record<string, ChartPendingAction>>({});
  const [pendingPresetActions, setPendingPresetActions] = useState<Record<string, PresetPendingAction>>({});
  const [pendingObservationActions, setPendingObservationActions] = useState<Record<string, ObservationPendingAction>>({});
  const [reviewPending, setReviewPending] = useState(false);
  const [exportPending, setExportPending] = useState(false);

  useEffect(() => {
    setInitialLoading(true);
    api
      .getAnalysis()
      .then((payload) => {
        setView(payload);
        setAnalysisPath(payload.analysis.root_path);
        setAnalysisName(payload.analysis.name);
        if (payload.analysis.exported_package_path) {
          loadExportedPackage(payload.analysis.exported_package_path);
        }
      })
      .catch(() => undefined)
      .finally(() => setInitialLoading(false));
  }, []);

  const analysis = view?.analysis ?? null;
  const selectedSession = selection.kind === "session" ? analysis?.sessions.find((item) => item.session_id === selection.id) ?? null : null;
  const selectedChart = selection.kind === "chart" ? analysis?.charts.find((item) => item.chart_instance_id === selection.id) ?? null : null;
  const generatedCharts = analysis?.charts.filter((chart) => chart.generation_state === "generated") ?? [];
  const staleCharts = analysis?.charts.filter((chart) => chart.stale || chart.observations_stale) ?? [];
  const selectedRecipe = view?.recipes.find((recipe) => recipe.recipe_id === chartDraft.recipeId) ?? view?.recipes[0] ?? null;
  const selectedSchema = selectedChart ? view?.recipe_schemas.find((schema) => schema.recipe_id === selectedChart.recipe_id) : selectedRecipe?.parameter_schema;
  const presets = useMemo(
    () => [...(analysis?.presets ?? []), ...(view?.global_presets ?? [])],
    [analysis?.presets, view?.global_presets]
  );

  function setChartPending(chartId: string, action: ChartPendingAction | null) {
    setPendingChartActions((current) => {
      const next = { ...current };
      if (action) {
        next[chartId] = action;
      } else {
        delete next[chartId];
      }
      return next;
    });
  }

  function setSessionPending(sessionId: string, action: SessionPendingAction | null) {
    setPendingSessionActions((current) => {
      const next = { ...current };
      if (action) {
        next[sessionId] = action;
      } else {
        delete next[sessionId];
      }
      return next;
    });
  }

  function setPresetPending(chartId: string, action: PresetPendingAction | null) {
    setPendingPresetActions((current) => {
      const next = { ...current };
      if (action) {
        next[chartId] = action;
      } else {
        delete next[chartId];
      }
      return next;
    });
  }

  function setObservationPending(observationId: string, action: ObservationPendingAction | null) {
    setPendingObservationActions((current) => {
      const next = { ...current };
      if (action) {
        next[observationId] = action;
      } else {
        delete next[observationId];
      }
      return next;
    });
  }

  useEffect(() => {
    if (!setSidebarContent) return;
    setSidebarContent((collapsed) => (
      <AnalysisSidebar
        analysis={analysis}
        selection={selection}
        setSelection={setSelection}
        sessionsOpen={sessionsOpen}
        setSessionsOpen={setSessionsOpen}
        chartsOpen={chartsOpen}
        setChartsOpen={setChartsOpen}
        collapsed={collapsed}
      />
    ));
    return () => setSidebarContent(null);
  }, [analysis, selection, sessionsOpen, chartsOpen, setSidebarContent]);

  async function createAnalysis() {
    setAnalysisPending("creating");
    try {
      const payload = await api.createAnalysis(analysisPath, analysisName);
      setView(payload);
      setAnalysisPath(payload.analysis.root_path);
      setAnalysisName(payload.analysis.name);
      setSelection({ kind: "overview" });
      setNewAnalysisOpen(false);
      notify("Analysis created", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Create failed", message(error), "error");
    } finally {
      setAnalysisPending(null);
    }
  }

  async function openAnalysis(path = analysisPath) {
    setAnalysisPending("opening");
    try {
      const payload = await api.openAnalysis(path);
      setView(payload);
      setAnalysisPath(payload.analysis.root_path);
      setAnalysisName(payload.analysis.name);
      if (payload.analysis.exported_package_path) {
        await loadExportedPackage(payload.analysis.exported_package_path);
      } else {
        setExportedPackage(null);
      }
      setSelection({ kind: "overview" });
      setOpenAnalysisOpen(false);
      notify("Analysis opened", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Open failed", message(error), "error");
    } finally {
      setAnalysisPending(null);
    }
  }

  async function openAnalysisFromPicker() {
    setAnalysisPending("opening");
    try {
      const response = await api.pickAnalysisDirectory(analysisPath);
      if (response.status === "cancelled") return;
      if (response.status === "unavailable" || !response.path) {
        setOpenAnalysisOpen(true);
        return;
      }
      await openAnalysis(response.path);
    } catch {
      setOpenAnalysisOpen(true);
    } finally {
      setAnalysisPending(null);
    }
  }

  async function saveAnalysis() {
    setAnalysisPending("saving");
    try {
      const payload = await api.saveAnalysis();
      setView(payload);
      notify("Analysis saved", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Save failed", message(error), "error");
    } finally {
      setAnalysisPending(null);
    }
  }

  async function addSession() {
    setSessionDraftPending(true);
    try {
      const payload = await api.addAnalysisSession({
        session: {
          season: Number(sessionDraft.season),
          event: sessionDraft.event,
          session: sessionDraft.session
        },
        drivers: splitDrivers(sessionDraft.drivers),
        data_cache: {
          directory: sessionDraft.cacheDirectory,
          mode: sessionDraft.cacheMode,
          fixture_path: sessionDraft.dataSource === "local" ? sessionDraft.localDatasetPath || null : null
        },
        load: true
      });
      setView(payload);
      const latest = payload.analysis.sessions[payload.analysis.sessions.length - 1];
      if (latest) setSelection({ kind: "session", id: latest.session_id });
      notify("Session added", latest?.name, latest?.load_state === "loaded" ? "success" : "warning");
    } catch (error) {
      notify("Session failed", message(error), "error");
    } finally {
      setSessionDraftPending(false);
    }
  }

  async function removeSession(session: AnalysisSession) {
    const dependents = analysis?.charts.filter((chart) => chart.target_session_ids.includes(session.session_id)) ?? [];
    const confirmed = dependents.length === 0 || window.confirm(`Remove ${session.name} and ${dependents.length} dependent chart(s)?`);
    if (!confirmed) return;
    setSessionPending(session.session_id, "removing");
    try {
      const payload = await api.removeAnalysisSession(session.session_id, dependents.length > 0);
      setView(payload);
      setSelection({ kind: "overview" });
      notify("Session removed", session.name, "success");
    } catch (error) {
      notify("Remove failed", message(error), "error");
    } finally {
      setSessionPending(session.session_id, null);
    }
  }

  async function loadSession(session: AnalysisSession) {
    setSessionPending(session.session_id, "loading");
    try {
      const payload = await api.loadAnalysisSession(session.session_id);
      setView(payload);
      notify("Session loaded", session.name, "success");
    } catch (error) {
      notify("Load failed", message(error), "error");
    } finally {
      setSessionPending(session.session_id, null);
    }
  }

  async function addChart() {
    const sessionId = chartDraft.sessionId || analysis?.sessions[0]?.session_id || "";
    if (!sessionId) {
      notify("Chart blocked", "Select a session", "warning");
      return;
    }
    const preset = presets.find((item) => item.preset_id === chartDraft.presetId && item.recipe_id === chartDraft.recipeId) ?? null;
    const parameters = preset?.parameters ?? { ...chartDraft.parameters, title: chartDraft.title || chartDraft.name };
    setChartDraftPending(true);
    try {
      const diagnostics = await api.resolveAnalysisChartDiagnostics({
        template_id: chartDraft.recipeId,
        target_session_ids: [sessionId],
        parameters
      });
      if (diagnostics.status === "invalid") {
        notify("Chart blocked", diagnostics.errors.map((item) => item.message).join("; "), "warning");
        return;
      }
      const payload = await api.addAnalysisChart({
        template_id: chartDraft.recipeId,
        target_session_ids: [sessionId],
        name: chartDraft.name,
        parameters,
        preset_id: preset?.preset_id ?? null
      });
      setView(payload);
      const latest = payload.analysis.charts[payload.analysis.charts.length - 1];
      if (latest) setSelection({ kind: "chart", id: latest.chart_instance_id });
      notify("Chart added", latest?.name, "success");
    } catch (error) {
      notify("Chart failed", message(error), "error");
    } finally {
      setChartDraftPending(false);
    }
  }

  async function updateChart(chart: ChartInstance, parameters: Record<string, unknown>, presetId?: string | null) {
    setChartPending(chart.chart_instance_id, "saving");
    try {
      const payload = await api.updateAnalysisChart(chart.chart_instance_id, {
        name: String(parameters.title || chart.name),
        parameters,
        preset_id: presetId === undefined ? undefined : presetId
      });
      setView(payload);
      notify("Chart saved", chart.name, "success");
    } catch (error) {
      notify("Save failed", message(error), "error");
    } finally {
      setChartPending(chart.chart_instance_id, null);
    }
  }

  async function generateChart(chart: ChartInstance, parameters?: Record<string, unknown>, presetId?: string | null) {
    setChartPending(chart.chart_instance_id, "generating");
    try {
      let targetChart = chart;
      if (parameters) {
        const saved = await api.updateAnalysisChart(chart.chart_instance_id, {
          name: String(parameterValue(parameters, "title", chart.name) || chart.name),
          parameters,
          preset_id: presetId === undefined ? undefined : presetId
        });
        targetChart = saved.analysis.charts.find((item) => item.chart_instance_id === chart.chart_instance_id) ?? chart;
        setView(saved);
      }
      const payload = await api.generateAnalysisCharts([targetChart.chart_instance_id]);
      setView(payload);
      notify("Chart generated", chart.name, "success");
    } catch (error) {
      notify("Generate failed", message(error), "error");
    } finally {
      setChartPending(chart.chart_instance_id, null);
    }
  }

  async function removeChart(chart: ChartInstance) {
    if (!window.confirm("Remove chart?")) return;
    setChartPending(chart.chart_instance_id, "removing");
    const previousView = view;
    if (previousView) {
      setView({
        ...previousView,
        analysis: {
          ...previousView.analysis,
          charts: previousView.analysis.charts.filter((item) => item.chart_instance_id !== chart.chart_instance_id),
          review_stale: true
        }
      });
    }
    setSelection({ kind: "overview" });
    try {
      const payload = await api.removeAnalysisChart(chart.chart_instance_id);
      setView(payload);
    } catch (error) {
      if (previousView) setView(previousView);
      setSelection({ kind: "chart", id: chart.chart_instance_id });
      notify("Remove failed", message(error), "error");
    } finally {
      setChartPending(chart.chart_instance_id, null);
    }
  }

  async function savePreset(chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting = false) {
    setPresetPending(chart.chart_instance_id, replaceExisting ? "replacing" : "saving");
    try {
      const payload = await api.saveAnalysisPreset({
        template_id: chart.recipe_id,
        display_name: chartDraft.presetName || chart.name,
        parameters,
        scope: global ? "global" : "analysis",
        replace_existing: replaceExisting
      });
      setView(payload);
      notify("Preset saved", global ? "Global" : "Analysis", "success");
    } catch (error) {
      notify("Preset failed", message(error), "error");
    } finally {
      setPresetPending(chart.chart_instance_id, null);
    }
  }

  async function updatePreset(presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting = false) {
    const chart = analysis?.charts.find((item) => item.preset_id === presetId);
    if (chart) setPresetPending(chart.chart_instance_id, "renaming");
    try {
      const payload = await api.updateAnalysisPreset(presetId, {
        display_name: displayName,
        parameters,
        replace_existing: replaceExisting
      });
      setView(payload);
      notify("Preset updated", displayName, "success");
    } catch (error) {
      notify("Preset failed", message(error), "error");
    } finally {
      if (chart) setPresetPending(chart.chart_instance_id, null);
    }
  }

  async function deletePreset(preset: ParameterPreset) {
    if (!window.confirm(`Delete ${preset.display_name}?`)) return;
    const affectedCharts = analysis?.charts.filter((chart) => chart.preset_id === preset.preset_id) ?? [];
    for (const chart of affectedCharts) setPresetPending(chart.chart_instance_id, "deleting");
    try {
      const payload = await api.deleteAnalysisPreset(preset.preset_id);
      setView(payload);
      notify("Preset deleted", preset.display_name, "success");
    } catch (error) {
      notify("Delete failed", message(error), "error");
    } finally {
      for (const chart of affectedCharts) setPresetPending(chart.chart_instance_id, null);
    }
  }

  async function refreshReview() {
    setReviewPending(true);
    try {
      const payload = await api.refreshAnalysisReview();
      setView(payload);
      await loadExportedPackage(payload.analysis.exported_package_path);
      notify("Review refreshed", payload.analysis.exported_package_path ?? undefined, "success");
    } catch (error) {
      notify("Refresh failed", message(error), "error");
    } finally {
      setReviewPending(false);
    }
  }

  async function exportAnalysis() {
    setExportPending(true);
    try {
      const payload = await api.exportAnalysis();
      setView(payload);
      await refreshHistory();
      await loadExportedPackage(payload.analysis.exported_package_path);
      notify("Package exported", payload.analysis.exported_package_path ?? undefined, "success");
    } catch (error) {
      notify("Export failed", message(error), "error");
    } finally {
      setExportPending(false);
    }
  }

  async function loadExportedPackage(path?: string | null) {
    if (!path) {
      setExportedPackage(null);
      return;
    }
    setPackageLoading(true);
    try {
      setExportedPackage(await api.openPackage(path));
    } catch {
      setExportedPackage(null);
    } finally {
      setPackageLoading(false);
    }
  }

  async function updateObservation(observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) {
    const action: ObservationPendingAction =
      reviewStatus === "accepted" ? "accepting" : reviewStatus === "rejected" ? "rejecting" : reviewStatus === "unreviewed" ? "clearing" : "saving";
    setObservationPending(observationId, action);
    try {
      await api.updateObservationReview(observationId, reviewStatus, editedText);
      const packageView = await api.regenerateDraft();
      setExportedPackage(packageView);
      notify("Observation saved", reviewStatus, "success");
    } catch (error) {
      notify("Review failed", message(error), "error");
    } finally {
      setObservationPending(observationId, null);
    }
  }

  return (
    <div className="grid gap-4">
      <AnalysisHeader
        analysis={analysis}
        pendingAction={analysisPending}
        onNew={() => setNewAnalysisOpen(true)}
        onOpen={openAnalysisFromPicker}
        onSave={saveAnalysis}
      />

      <div className="grid gap-4">
        {initialLoading && <LoadingBlock label="Loading Analysis" />}
        {!initialLoading && selection.kind === "overview" && <Overview analysis={analysis} staleCharts={staleCharts.length} />}
        {selection.kind === "new-session" && (
          <SessionDraftEditor draft={sessionDraft} setDraft={setSessionDraft} addSession={addSession} disabled={!analysis} pending={sessionDraftPending} />
        )}
        {selectedSession && <SessionEditor session={selectedSession} loadSession={loadSession} removeSession={removeSession} pendingAction={pendingSessionActions[selectedSession.session_id] ?? null} />}
        {selection.kind === "new-chart" && analysis && view && (
          <ChartDraftEditor
            draft={chartDraft}
            setDraft={setChartDraft}
            sessions={analysis.sessions}
            recipes={view.recipes}
            presets={presets.filter((preset) => preset.recipe_id === chartDraft.recipeId)}
            schemaFields={selectedRecipe?.parameter_schema.fields ?? []}
            addChart={addChart}
            pending={chartDraftPending}
          />
        )}
        {selectedChart && (
          <ChartEditor
            chart={selectedChart}
            sessions={analysis?.sessions ?? []}
            schemaFields={selectedSchema?.fields ?? []}
            presets={presets.filter((preset) => preset.recipe_id === selectedChart.recipe_id)}
            updateChart={updateChart}
            generateChart={generateChart}
            removeChart={removeChart}
            savePreset={savePreset}
            updatePreset={updatePreset}
            deletePreset={deletePreset}
            presetName={chartDraft.presetName}
            setPresetName={(presetName) => setChartDraft((current) => ({ ...current, presetName }))}
            saveGlobal={chartDraft.saveGlobal}
            setSaveGlobal={(saveGlobal) => setChartDraft((current) => ({ ...current, saveGlobal }))}
            openArtifact={openArtifact}
            pendingAction={pendingChartActions[selectedChart.chart_instance_id] ?? null}
            presetPendingAction={pendingPresetActions[selectedChart.chart_instance_id] ?? null}
          />
        )}
        {selection.kind === "playback" && analysis && (
          <PlaybackExplorer
            sessions={analysis.sessions}
          />
        )}
        {selection.kind === "review" && <ReviewEditor analysis={analysis} packageView={exportedPackage} refreshReview={refreshReview} updateObservation={updateObservation} pending={reviewPending} observationPendingActions={pendingObservationActions} />}
        {selection.kind === "export" && <ExportEditor analysis={analysis} packageView={exportedPackage} exportAnalysis={exportAnalysis} openArtifact={openArtifact} pending={exportPending} packageLoading={packageLoading} />}
      </div>
      <Dialog open={newAnalysisOpen} onOpenChange={setNewAnalysisOpen} title="New Analysis">
        <div className="grid gap-3">
          <Field label="Name" value={analysisName} onChange={(event) => setAnalysisName(event.target.value)} />
          <Field label="Directory path" value={analysisPath} onChange={(event) => setAnalysisPath(event.target.value)} />
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button onClick={() => setNewAnalysisOpen(false)}>Cancel</Button>
          <Button variant="primary" icon={<FilePlus2 className="h-4 w-4" />} onClick={createAnalysis} loading={analysisPending === "creating"}>
            Create
          </Button>
        </div>
      </Dialog>
      <Dialog open={openAnalysisOpen} onOpenChange={setOpenAnalysisOpen} title="Open Analysis">
        <div className="grid gap-3">
          <Field label="Directory path" value={analysisPath} onChange={(event) => setAnalysisPath(event.target.value)} />
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button onClick={() => setOpenAnalysisOpen(false)}>Cancel</Button>
          <Button variant="primary" icon={<FolderOpen className="h-4 w-4" />} onClick={() => openAnalysis()} loading={analysisPending === "opening"}>
            Open
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function AnalysisHeader({
  analysis,
  pendingAction,
  onNew,
  onOpen,
  onSave
}: {
  analysis: AnalysisView["analysis"] | null;
  pendingAction: AnalysisPendingAction | null;
  onNew: () => void;
  onOpen: () => void;
  onSave: () => void;
}) {
  const path = analysis?.root_path ?? null;
  const pendingLabel =
    pendingAction === "creating" ? "Creating"
      : pendingAction === "opening" ? "Opening"
        : pendingAction === "saving" ? "Saving"
          : null;

  return (
    <header className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
      <div className="grid min-w-0 gap-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h1 className="min-w-0 break-words text-lg font-semibold text-ink">{analysis?.name ?? "No analysis open"}</h1>
          {pendingLabel && (
            <span className="inline-flex h-7 items-center gap-2 rounded-full border border-line bg-slate-50 px-2.5 text-xs font-semibold text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              {pendingLabel}
            </span>
          )}
        </div>
        <p className="min-w-0 truncate text-sm text-muted" title={path ?? undefined}>
          {path ? compactPath(path) : "Create or open an analysis"}
        </p>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        <Button icon={<FilePlus2 className="h-4 w-4" />} onClick={onNew} disabled={pendingAction !== null}>
          New
        </Button>
        <Button icon={<FolderOpen className="h-4 w-4" />} onClick={onOpen} disabled={pendingAction !== null} loading={pendingAction === "opening"}>
          Open
        </Button>
        <Button icon={<Save className="h-4 w-4" />} onClick={onSave} disabled={!analysis || pendingAction !== null} loading={pendingAction === "saving"}>
          Save
        </Button>
      </div>
    </header>
  );
}

function AnalysisSidebar({
  analysis,
  selection,
  setSelection,
  sessionsOpen,
  setSessionsOpen,
  chartsOpen,
  setChartsOpen,
  collapsed
}: {
  analysis: AnalysisView["analysis"] | null;
  selection: AnalysisSelection;
  setSelection: (selection: AnalysisSelection) => void;
  sessionsOpen: boolean;
  setSessionsOpen: (open: boolean) => void;
  chartsOpen: boolean;
  setChartsOpen: (open: boolean) => void;
  collapsed: boolean;
}) {
  return (
    <nav className="grid gap-2">
      <OutlineButton
        active={selection.kind === "overview"}
        label={analysis?.name ?? "Overview"}
        icon={<BarChart3 className="h-4 w-4" />}
        onClick={() => setSelection({ kind: "overview" })}
        collapsed={collapsed}
      />

      <div className="mt-2 grid gap-1">
        <GroupLabel
          label="Sessions"
          count={analysis?.sessions.length ?? 0}
          open={sessionsOpen}
          onToggle={() => setSessionsOpen(!sessionsOpen)}
          collapsed={collapsed}
        />
        {sessionsOpen && (
          <>
            {analysis?.sessions.map((session) => (
              <OutlineButton
                key={session.session_id}
                active={selection.kind === "session" && selection.id === session.session_id}
                label={session.name}
                status={session.load_state}
                icon={<BarChart3 className="h-4 w-4" />}
                onClick={() => setSelection({ kind: "session", id: session.session_id })}
                collapsed={collapsed}
              />
            ))}
            <OutlineButton
              active={selection.kind === "new-session"}
              label="Add Session"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setSelection({ kind: "new-session" })}
              collapsed={collapsed}
            />
          </>
        )}
      </div>

      <div className="mt-2 grid gap-1">
        <GroupLabel
          label="Charts"
          count={analysis?.charts.length ?? 0}
          open={chartsOpen}
          onToggle={() => setChartsOpen(!chartsOpen)}
          collapsed={collapsed}
        />
        {chartsOpen && (
          <>
            {analysis?.charts.map((chart) => (
              <OutlineButton
                key={chart.chart_instance_id}
                active={selection.kind === "chart" && selection.id === chart.chart_instance_id}
                label={chart.name}
                status={chart.generation_state}
                icon={<LineChart className="h-4 w-4" />}
                onClick={() => setSelection({ kind: "chart", id: chart.chart_instance_id })}
                collapsed={collapsed}
              />
            ))}
            <OutlineButton
              active={selection.kind === "new-chart"}
              label="Add Chart"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setSelection({ kind: "new-chart" })}
              disabled={!analysis || analysis.sessions.length === 0}
              collapsed={collapsed}
            />
          </>
        )}
      </div>

      <div className="mt-2 grid gap-1">
        <OutlineButton
          active={selection.kind === "playback"}
          label="Race Playback"
          icon={<MapIcon className="h-4 w-4" />}
          onClick={() => setSelection({ kind: "playback" })}
          disabled={!analysis || !analysis.sessions.some((session) => session.load_state === "loaded")}
          collapsed={collapsed}
        />
        <OutlineButton
          active={selection.kind === "review"}
          label="Review"
          status={analysis?.review_stale ? "stale" : undefined}
          icon={<ClipboardCheck className="h-4 w-4" />}
          onClick={() => setSelection({ kind: "review" })}
          disabled={!analysis}
          collapsed={collapsed}
        />
        <OutlineButton
          active={selection.kind === "export"}
          label="Export"
          icon={<Download className="h-4 w-4" />}
          onClick={() => setSelection({ kind: "export" })}
          disabled={!analysis}
          collapsed={collapsed}
        />
      </div>
    </nav>
  );
}

function Overview({ analysis, staleCharts }: { analysis: AnalysisView["analysis"] | null; staleCharts: number }) {
  return (
    <Panel title="Overview">
      <dl className="grid gap-3 sm:grid-cols-4">
        <Metric label="Sessions" value={analysis?.sessions.length ?? 0} />
        <Metric label="Charts" value={analysis?.charts.length ?? 0} />
        <Metric label="Generated" value={analysis?.charts.filter((chart) => chart.generation_state === "generated").length ?? 0} />
        <Metric label="Stale" value={staleCharts} />
      </dl>
      {analysis?.exported_package_path && (
        <div className="mt-4 rounded-md border border-line bg-slate-50 p-3 text-sm text-ink">{compactPath(analysis.exported_package_path)}</div>
      )}
    </Panel>
  );
}

function SessionDraftEditor({ draft, setDraft, addSession, disabled, pending }: { draft: typeof defaultSession; setDraft: (draft: typeof defaultSession) => void; addSession: () => void; disabled: boolean; pending: boolean }) {
  return (
    <Panel title="Add Session" actions={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={addSession} disabled={disabled} loading={pending}>Add</Button>}>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Season" type="number" value={draft.season} onChange={(event) => setDraft({ ...draft, season: Number(event.target.value) })} />
        <Field label="Event" value={draft.event} onChange={(event) => setDraft({ ...draft, event: event.target.value })} />
        <Field label="Session" value={draft.session} onChange={(event) => setDraft({ ...draft, session: event.target.value })} />
        <TextAreaField label="Drivers" value={draft.drivers} onChange={(event) => setDraft({ ...draft, drivers: event.target.value })} />
        <SelectField label="Data source" value={draft.dataSource} onValueChange={(value) => setDraft({ ...draft, dataSource: value as "fastf1" | "local" })} options={[{ value: "fastf1", label: "FastF1" }, { value: "local", label: "Local dataset" }]} />
        {draft.dataSource === "local" ? (
          <Field label="Local dataset" value={draft.localDatasetPath} onChange={(event) => setDraft({ ...draft, localDatasetPath: event.target.value })} />
        ) : (
          <>
            <Field label="Cache directory" value={draft.cacheDirectory} onChange={(event) => setDraft({ ...draft, cacheDirectory: event.target.value })} />
            <SelectField label="Cache mode" value={draft.cacheMode} onValueChange={(value) => setDraft({ ...draft, cacheMode: value as "cache-or-fetch" | "cache-only" })} options={[{ value: "cache-or-fetch", label: "Cache or fetch" }, { value: "cache-only", label: "Cache only" }]} />
          </>
        )}
      </div>
    </Panel>
  );
}

function SessionEditor({ session, loadSession, removeSession, pendingAction }: { session: AnalysisSession; loadSession: (session: AnalysisSession) => void; removeSession: (session: AnalysisSession) => void; pendingAction: SessionPendingAction | null }) {
  const loading = pendingAction === "loading";
  const removing = pendingAction === "removing";
  return (
    <Panel
      title={session.name}
      actions={
        <>
          <StatusBadge value={session.load_state} />
          <Button icon={<RefreshCw className="h-4 w-4" />} onClick={() => loadSession(session)} loading={loading} disabled={removing}>Load</Button>
          <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => removeSession(session)} loading={removing} disabled={loading}>Remove</Button>
        </>
      }
    >
      <dl className="grid gap-3 sm:grid-cols-3">
        <Metric label="Season" value={session.session.season} />
        <Metric label="Event" value={session.session.event} />
        <Metric label="Session" value={session.session.session} />
        <Metric label="Drivers" value={session.drivers.join(", ")} />
        <Metric label="Snapshot" value={session.snapshot?.snapshot_id ?? "None"} />
        <Metric label="Hash" value={session.snapshot?.dataset_hash.slice(0, 12) ?? "None"} />
      </dl>
      {session.errors.length > 0 && <ErrorList errors={session.errors} />}
    </Panel>
  );
}

function ChartDraftEditor({
  draft,
  setDraft,
  sessions,
  recipes,
  presets,
  schemaFields,
  addChart,
  pending
}: {
  draft: typeof chartDraftSeed;
  setDraft: (draft: typeof chartDraftSeed) => void;
  sessions: AnalysisSession[];
  recipes: AnalysisView["recipes"];
  presets: ParameterPreset[];
  schemaFields: ParameterField[];
  addChart: () => void;
  pending: boolean;
}) {
  const selectedRecipe = recipes.find((recipe) => recipe.recipe_id === draft.recipeId) ?? recipes[0];
  const selectedSession = sessions.find((session) => session.session_id === draft.sessionId) ?? sessions[0];
  const sessionDrivers = selectedSession?.drivers ?? [];
  const sessionTeams = selectedSession?.available_teams ?? [];
  const [mode, setMode] = useState<"basic" | "advanced">("basic");
  const [diagnostics, setDiagnostics] = useState<ParameterDiagnostics | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [presetFilter, setPresetFilter] = useState("");
  const [trackSelectorOpen, setTrackSelectorOpen] = useState(false);
  const [trackMap, setTrackMap] = useState<TrackMapPayload | null>(null);
  const [trackMapLoading, setTrackMapLoading] = useState(false);
  const [trackMapError, setTrackMapError] = useState<string | null>(null);
  const fields = visibleSchemaFields(schemaFields, draft.parameters, mode);
  const filteredPresets = filterPresets(presets, presetFilter);

  useEffect(() => {
    setTrackSelectorOpen(false);
    setTrackMap(null);
    setTrackMapError(null);
  }, [draft.recipeId, draft.sessionId]);

  useEffect(() => {
    if (!selectedRecipe || !selectedSession) return;
    const timer = window.setTimeout(() => {
      setDiagnosticsLoading(true);
      api
        .resolveAnalysisChartDiagnostics({
          template_id: draft.recipeId,
          target_session_ids: [selectedSession.session_id],
          parameters: { ...draft.parameters, title: draft.title || draft.name }
        })
        .then(setDiagnostics)
        .catch(() => setDiagnostics(null))
        .finally(() => setDiagnosticsLoading(false));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [draft.recipeId, draft.parameters, draft.title, draft.name, selectedRecipe, selectedSession]);

  async function openDraftTrackSelector() {
    if (draft.recipeId !== "telemetry_trace" || !selectedSession) return;
    setTrackSelectorOpen(true);
    setTrackMapLoading(true);
    setTrackMapError(null);
    try {
      const payload = await api.getAnalysisTrackMap({
        template_id: draft.recipeId,
        target_session_ids: [selectedSession.session_id],
        parameters: { ...draft.parameters, title: draft.title || draft.name },
        max_points: 500
      });
      setTrackMap(payload);
    } catch (error) {
      setTrackMap(null);
      setTrackMapError(message(error));
    } finally {
      setTrackMapLoading(false);
    }
  }

  function applyDraftTrackSegment(startDistance: number, endDistance: number, payload: TrackMapPayload, cornerSelection?: TrackCornerSelection | null) {
    setDraft({
      ...draft,
      parameters: trackSegmentParameters(draft.parameters, startDistance, endDistance, payload, cornerSelection)
    });
    setTrackSelectorOpen(false);
  }

  const hasInvalidDiagnostics = diagnostics?.status === "invalid";
  const canAdd = Boolean(selectedSession) && diagnostics?.status !== "invalid";
  const canUseTrackSelector =
    draft.recipeId === "telemetry_trace"
    && Boolean(selectedSession)
    && selectedSession?.load_state === "loaded"
    && !hasInvalidDiagnostics;
  return (
    <Panel title="Add Chart" actions={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={addChart} disabled={!canAdd} loading={pending}>Add</Button>}>
      <div className="grid gap-3 md:grid-cols-2">
        <SelectField
          label="Chart template"
          value={draft.recipeId}
          onValueChange={(recipeId) => {
            const nextRecipe = recipes.find((recipe) => recipe.recipe_id === recipeId);
            const nextParameters = defaultParameters(nextRecipe?.parameter_schema.fields ?? []);
            setDraft({
              ...draft,
              recipeId,
              name: nextRecipe?.display_name ?? draft.name,
              title: String(nextParameters.title ?? nextRecipe?.display_name ?? draft.title),
              parameters: nextParameters,
              presetId: noPresetValue
            });
          }}
          options={recipes.map((recipe) => ({ value: recipe.recipe_id, label: `${recipe.display_name} - ${recipe.source_label}` }))}
        />
        <SelectField label="Session" value={draft.sessionId || sessions[0]?.session_id || ""} onValueChange={(sessionId) => setDraft({ ...draft, sessionId })} options={sessions.map((session) => ({ value: session.session_id, label: session.name }))} />
        {presets.length > 0 && (
          <div className="grid gap-3">
            <Field label="Find preset" value={presetFilter} onChange={(event) => setPresetFilter(event.target.value)} />
            <SelectField
              label="Preset"
              value={draft.presetId}
              onValueChange={(presetId) => {
                const preset = presets.find((item) => item.preset_id === presetId);
                setDraft({
                  ...draft,
                  presetId,
                  parameters: preset?.parameters ?? draft.parameters,
                  title: String(preset?.parameters.title ?? draft.title)
                });
              }}
              options={[{ value: noPresetValue, label: "None" }, ...filteredPresets.map((preset) => ({ value: preset.preset_id, label: `${preset.display_name} - ${preset.scope}` }))]}
            />
          </div>
        )}
        <Field label="Name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant={mode === "basic" ? "primary" : "secondary"} onClick={() => setMode("basic")}>Basic</Button>
        <Button variant={mode === "advanced" ? "primary" : "secondary"} onClick={() => setMode("advanced")}>Advanced</Button>
      </div>
      {(diagnosticsLoading || diagnostics) && (
        <div className="mt-4 grid gap-2 rounded-md border border-line p-3">
          <div className="flex flex-wrap gap-2">
            {diagnosticsLoading && (
              <span className="inline-flex items-center gap-2 rounded border border-line px-2 py-1 text-xs font-medium text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                Checking
              </span>
            )}
            {diagnostics && <StatusBadge value={diagnostics.status} />}
            {diagnostics?.active_filter_summary.map((item) => (
              <span key={item} className="rounded border border-line px-2 py-1 text-xs text-muted">{item}</span>
            ))}
          </div>
          {diagnostics && diagnostics.warnings.length > 0 && <WarningList warnings={diagnostics.warnings.map((item) => item.message)} />}
          {diagnostics && diagnostics.errors.length > 0 && <ErrorList errors={diagnostics.errors.map((item) => item.message)} />}
        </div>
      )}
      <div className="mt-4">
        <ParameterSections
          fields={fields}
          allFields={schemaFields}
          parameters={draft.parameters}
          diagnostics={diagnostics}
          drivers={sessionDrivers}
          teams={sessionTeams}
          renderFieldAction={(field) => field.name === "distance_range_m" && draft.recipeId === "telemetry_trace" ? (
            <Button icon={<MapIcon className="h-4 w-4" />} onClick={openDraftTrackSelector} disabled={!canUseTrackSelector} loading={trackMapLoading}>
              Track Selector
            </Button>
          ) : null}
          setParameter={(field, value) => {
            const parameters = parametersWithFieldValue(draft.parameters, field.name, value);
            setDraft({
              ...draft,
              parameters,
              title: field.name === "title" ? String(value ?? "") : draft.title
            });
          }}
        />
      </div>
      <TrackSegmentDialog
        open={trackSelectorOpen}
        onOpenChange={setTrackSelectorOpen}
        payload={trackMap}
        loading={trackMapLoading}
        error={trackMapError}
        onApply={applyDraftTrackSegment}
      />
      {selectedRecipe && <div className="mt-4 text-sm text-muted">{selectedRecipe.source_label}</div>}
    </Panel>
  );
}

const chartDraftSeed = {
  recipeId: "lap_time_delta",
  sessionId: "",
  name: "Lap time delta",
  title: "Lap time delta",
  parameters: { title: "Lap time delta" } as Record<string, unknown>,
  presetId: noPresetValue,
  presetName: "Lap time delta",
  saveGlobal: false
};

function ChartEditor({
  chart,
  sessions,
  schemaFields,
  presets,
  updateChart,
  generateChart,
  removeChart,
  savePreset,
  updatePreset,
  deletePreset,
  presetName,
  setPresetName,
  saveGlobal,
  setSaveGlobal,
  openArtifact,
  pendingAction,
  presetPendingAction
}: {
  chart: ChartInstance;
  sessions: AnalysisSession[];
  schemaFields: ParameterField[];
  presets: AnalysisView["analysis"]["presets"];
  updateChart: (chart: ChartInstance, parameters: Record<string, unknown>, presetId?: string | null) => Promise<void>;
  generateChart: (chart: ChartInstance, parameters?: Record<string, unknown>, presetId?: string | null) => void;
  removeChart: (chart: ChartInstance) => void;
  savePreset: (chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting?: boolean) => Promise<void>;
  updatePreset: (presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting?: boolean) => Promise<void>;
  deletePreset: (preset: ParameterPreset) => Promise<void>;
  presetName: string;
  setPresetName: (value: string) => void;
  saveGlobal: boolean;
  setSaveGlobal: (value: boolean) => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
  pendingAction: ChartPendingAction | null;
  presetPendingAction: PresetPendingAction | null;
}) {
  const [parameters, setParameters] = useState<Record<string, unknown>>(chart.parameters);
  const [selectedPresetId, setSelectedPresetId] = useState(chart.preset_id ?? noPresetValue);
  const [mode, setMode] = useState<"basic" | "advanced">("basic");
  const [diagnostics, setDiagnostics] = useState<ParameterDiagnostics | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(true);
  const [inspectorWidth, setInspectorWidth] = useState(inspectorDefaultWidth);
  const [presetToolsOpen, setPresetToolsOpen] = useState(false);
  const [presetFilter, setPresetFilter] = useState("");
  const [trackSelectorOpen, setTrackSelectorOpen] = useState(false);
  const [trackMap, setTrackMap] = useState<TrackMapPayload | null>(null);
  const [trackMapLoading, setTrackMapLoading] = useState(false);
  const [trackMapError, setTrackMapError] = useState<string | null>(null);
  const selectedPreset = presets.find((item) => item.preset_id === selectedPresetId) ?? null;
  const filteredPresets = filterPresets(presets, presetFilter);
  const targetSession = sessions.find((session) => chart.target_session_ids.includes(session.session_id));
  const sessionDrivers = targetSession?.drivers ?? [];
  const sessionTeams = targetSession?.available_teams ?? [];
  const drivers = sessionDrivers.length > 0 ? sessionDrivers : Array.isArray(parameters.drivers) ? parameters.drivers.map(String) : [];
  const fields = visibleSchemaFields(schemaFields, parameters, mode);
  const dirty = !sameJson(parameters, chart.parameters) || selectedPresetId !== (chart.preset_id ?? noPresetValue);
  const hasInvalidDiagnostics = diagnostics?.status === "invalid";
  const saving = pendingAction === "saving";
  const generating = pendingAction === "generating";
  const removing = pendingAction === "removing";
  const pending = pendingAction !== null;

  useEffect(() => {
    setParameters(chart.parameters);
    setSelectedPresetId(chart.preset_id ?? noPresetValue);
    setTrackSelectorOpen(false);
    setTrackMap(null);
    setTrackMapError(null);
  }, [chart.chart_instance_id, chart.parameters]);

  useEffect(() => {
    if (!targetSession) return;
    const timer = window.setTimeout(() => {
      setDiagnosticsLoading(true);
      api
        .resolveAnalysisChartDiagnostics({
          template_id: chart.recipe_id,
          target_session_ids: chart.target_session_ids,
          parameters
        })
        .then(setDiagnostics)
        .catch(() => setDiagnostics(null))
        .finally(() => setDiagnosticsLoading(false));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [chart.recipe_id, chart.target_session_ids, parameters, targetSession]);

  function applyPreset(presetId: string) {
    setSelectedPresetId(presetId);
    if (presetId === noPresetValue) return;
        const preset = presets.find((item) => item.preset_id === presetId);
        if (preset) setParameters(preset.parameters);
  }

  function resetSection(group: string) {
    setParameters((current) => resetParametersByGroup(schemaFields, current, group));
  }

  function resetChart() {
    setParameters(defaultParameters(schemaFields));
    setSelectedPresetId(noPresetValue);
  }

  function restorePreset() {
    if (selectedPreset) setParameters(selectedPreset.parameters);
  }

  function clearOverrides() {
    setParameters((current) => clearCustomOverrides(current));
  }

  function resizeInspector(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = inspectorWidth;

    function onMouseMove(moveEvent: globalThis.MouseEvent) {
      const nextWidth = clampNumber(startWidth - (moveEvent.clientX - startX), inspectorMinWidth, inspectorMaxWidth);
      setInspectorWidth(nextWidth);
    }

    function onMouseUp() {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  async function openTrackSelector() {
    if (chart.recipe_id !== "telemetry_trace") return;
    setTrackSelectorOpen(true);
    setTrackMapLoading(true);
    setTrackMapError(null);
    try {
      const payload = await api.getAnalysisTrackMap({
        template_id: chart.recipe_id,
        target_session_ids: chart.target_session_ids,
        parameters,
        max_points: 500
      });
      setTrackMap(payload);
    } catch (error) {
      setTrackMap(null);
      setTrackMapError(message(error));
    } finally {
      setTrackMapLoading(false);
    }
  }

  function applyTrackSegment(startDistance: number, endDistance: number, payload: TrackMapPayload, cornerSelection?: TrackCornerSelection | null) {
    setParameters((current) => trackSegmentParameters(current, startDistance, endDistance, payload, cornerSelection));
    setTrackSelectorOpen(false);
  }

  const artifact: Artifact | null = chart.image_path
    ? {
        artifact_id: chart.artifact_id ?? chart.chart_instance_id,
        recipe_id: chart.recipe_id,
        image_path: chart.image_path,
        metadata_path: chart.metadata_path,
        title: chart.name
      }
    : null;

  return (
    <Panel className="xl:h-[calc(100vh-152px)] xl:overflow-hidden [&>div]:xl:h-full [&>div]:xl:min-h-0">
      <div
        className={cn("grid gap-4 xl:h-full xl:min-h-0", optionsOpen && "xl:grid-cols-[minmax(0,1fr)_minmax(300px,var(--inspector-width))]")}
        style={optionsOpen ? { "--inspector-width": `${inspectorWidth}px` } as CSSProperties : undefined}
      >
        <div className="grid gap-3 xl:min-h-0 xl:grid-rows-[auto_minmax(0,1fr)_auto] xl:overflow-hidden">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h2 className="min-w-0 break-words text-base font-semibold text-ink">{chart.name}</h2>
              <StatusBadge value={pendingAction ?? chart.generation_state} />
            </div>
            <Button
              variant="ghost"
              className="h-9 w-9 px-0"
              icon={optionsOpen ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
              aria-label={optionsOpen ? "Collapse chart options" : "Expand chart options"}
              title={optionsOpen ? "Collapse chart options" : "Expand chart options"}
              onClick={() => setOptionsOpen((current) => !current)}
            />
          </div>
          {artifact && generating ? (
            <button type="button" className="relative flex min-h-0 items-center justify-center overflow-hidden rounded-md border border-line bg-slate-50 max-xl:aspect-video xl:h-full" onClick={() => openArtifact(artifact, "/api/analysis/assets")}>
              <img src={`/api/analysis/assets/${artifact.image_path}`} alt={artifact.artifact_id} className="max-h-full max-w-full object-contain opacity-40 max-xl:h-auto max-xl:w-full" />
              <div className="absolute inset-0 flex items-center justify-center bg-panel/60">
                <span className="inline-flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-ink">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Generating
                </span>
              </div>
              <div className="absolute inset-x-0 bottom-0 border-t border-line bg-panel/95 px-3 py-2 text-sm font-medium text-ink">Previous render</div>
            </button>
          ) : artifact ? (
            <button type="button" className="flex min-h-0 items-center justify-center overflow-hidden rounded-md border border-line bg-slate-50 max-xl:aspect-video xl:h-full" onClick={() => openArtifact(artifact, "/api/analysis/assets")}>
              <img src={`/api/analysis/assets/${artifact.image_path}`} alt={artifact.artifact_id} className="max-h-full max-w-full object-contain max-xl:h-auto max-xl:w-full" />
            </button>
          ) : generating ? (
            <div className="flex min-h-0 items-center justify-center rounded-md border border-dashed border-line bg-slate-50 text-muted max-xl:aspect-video xl:h-full">
              <span className="inline-flex items-center gap-2 text-sm font-medium">
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                Generating
              </span>
            </div>
          ) : (
            <div className="flex min-h-0 items-center justify-center rounded-md border border-dashed border-line bg-slate-50 text-muted max-xl:aspect-video xl:h-full">
              <Image className="h-8 w-8" />
            </div>
          )}
          {chart.errors.length > 0 && <ErrorList errors={chart.errors} />}
        </div>
        {optionsOpen && (
          <aside className="relative grid content-start gap-4 rounded-md border border-line bg-slate-50 p-3 max-xl:w-full xl:h-full xl:min-h-0 xl:grid-rows-[auto_minmax(0,1fr)_auto] xl:overflow-hidden">
            <button
              type="button"
              className="absolute -left-2 top-0 hidden h-full w-3 cursor-col-resize rounded-full bg-transparent outline-none transition hover:bg-teal-100 focus-visible:bg-teal-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent xl:block"
              aria-label="Resize chart options"
              title="Resize chart options"
              onMouseDown={resizeInspector}
            >
              <span className="mx-auto block h-full w-px bg-line" />
            </button>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Chart Options</h3>
            </div>
            <div className="grid content-start gap-4 xl:min-h-0 xl:overflow-y-auto xl:pr-1">
              <div className="flex flex-wrap gap-2">
                <Button variant={mode === "basic" ? "primary" : "secondary"} onClick={() => setMode("basic")}>Basic</Button>
                <Button variant={mode === "advanced" ? "primary" : "secondary"} onClick={() => setMode("advanced")}>Advanced</Button>
                <Button icon={<RotateCcw className="h-4 w-4" />} onClick={resetChart} disabled={pending}>Reset chart</Button>
                <Button icon={<RotateCcw className="h-4 w-4" />} onClick={restorePreset} disabled={!selectedPreset || pending}>Restore preset</Button>
                <Button icon={<XCircle className="h-4 w-4" />} onClick={clearOverrides} disabled={pending}>Clear overrides</Button>
              </div>
              {(diagnosticsLoading || diagnostics) && (
                <div className="grid gap-2 rounded-md border border-line bg-panel p-3">
                  <div className="flex flex-wrap gap-2">
                    {diagnosticsLoading && (
                      <span className="inline-flex items-center gap-2 rounded border border-line px-2 py-1 text-xs font-medium text-muted">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                        Checking
                      </span>
                    )}
                    {diagnostics && <StatusBadge value={diagnostics.status} />}
                    {diagnostics?.active_filter_summary.map((item) => (
                      <span key={item} className="rounded border border-line px-2 py-1 text-xs text-muted">{item}</span>
                    ))}
                  </div>
                  {diagnostics && diagnostics.warnings.length > 0 && <WarningList warnings={diagnostics.warnings.map((item) => item.message)} />}
                  {diagnostics && diagnostics.errors.length > 0 && <ErrorList errors={diagnostics.errors.map((item) => item.message)} />}
                </div>
              )}
              <ParameterSections
                fields={fields}
                allFields={schemaFields}
                parameters={parameters}
                diagnostics={diagnostics}
                drivers={drivers}
                teams={sessionTeams}
                renderFieldAction={(field) => field.name === "distance_range_m" && chart.recipe_id === "telemetry_trace" ? (
                  <Button icon={<MapIcon className="h-4 w-4" />} onClick={openTrackSelector} disabled={!targetSession || hasInvalidDiagnostics} loading={trackMapLoading}>
                    Track Selector
                  </Button>
                ) : null}
                setParameter={(field, value) => setParameters((current) => parametersWithFieldValue(current, field.name, value))}
              />
              {mode === "advanced" && (
                <div className="flex flex-wrap gap-2">
                  <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("selection")} disabled={pending}>Reset selection</Button>
                  <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("filters")} disabled={pending}>Reset filters</Button>
                  <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("presentation")} disabled={pending}>Reset style</Button>
                </div>
              )}
              <PresetApplyPanel presets={filteredPresets} selectedPresetId={selectedPresetId} presetFilter={presetFilter} setPresetFilter={setPresetFilter} applyPreset={applyPreset} disabled={pending || presetPendingAction !== null} />
              <div className="flex justify-end">
                <Button icon={presetToolsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />} onClick={() => setPresetToolsOpen((current) => !current)}>
                  Preset Tools
                </Button>
              </div>
              {presetToolsOpen && (
                <PresetManagementPanel
                  chart={chart}
                  parameters={parameters}
                  selectedPreset={selectedPreset}
                  presetName={presetName}
                  setPresetName={setPresetName}
                  saveGlobal={saveGlobal}
                  setSaveGlobal={setSaveGlobal}
                  savePreset={savePreset}
                  updatePreset={updatePreset}
                  deletePreset={deletePreset}
                  pendingAction={presetPendingAction}
                />
              )}
            </div>
            <div className="-mx-3 -mb-3 mt-1 flex flex-wrap justify-end gap-2 border-t border-line bg-panel p-3">
              <Button icon={<Save className="h-4 w-4" />} onClick={() => updateChart(chart, parameters, selectedPresetId === noPresetValue ? null : selectedPresetId)} disabled={hasInvalidDiagnostics || (pending && !saving)} loading={saving}>Save</Button>
              <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={() => generateChart(chart, parameters, selectedPresetId === noPresetValue ? null : selectedPresetId)} disabled={hasInvalidDiagnostics || (pending && !generating)} loading={generating}>{dirty ? "Save + Generate" : "Generate"}</Button>
              <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => removeChart(chart)} disabled={pending && !removing} loading={removing}>Remove</Button>
            </div>
          </aside>
        )}
      </div>
      <TrackSegmentDialog
        open={trackSelectorOpen}
        onOpenChange={setTrackSelectorOpen}
        payload={trackMap}
        loading={trackMapLoading}
        error={trackMapError}
        onApply={applyTrackSegment}
      />
    </Panel>
  );
}

type TrackDraft = {
  start: number;
  end: number;
  activeEndpoint: "start" | "end";
  selectedCornerLabel: string | null;
  prePaddingM: number;
  postPaddingM: number;
};

type TrackCornerSelection = {
  corner: TrackMapCorner;
  prePaddingM: number;
  postPaddingM: number;
};

const defaultCornerPaddingM = 100;

function TrackSegmentDialog({
  open,
  onOpenChange,
  payload,
  loading,
  error,
  onApply
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload: TrackMapPayload | null;
  loading: boolean;
  error: string | null;
  onApply: (startDistance: number, endDistance: number, payload: TrackMapPayload, cornerSelection?: TrackCornerSelection | null) => void;
}) {
  const bounds = payload ? trackMapDistanceBounds(payload) : null;
  const [draft, setDraft] = useState<TrackDraft | null>(null);

  useEffect(() => {
    if (!open || !payload || payload.status !== "available" || !bounds) {
      setDraft(null);
      return;
    }
    const segment = payload.segment;
    const corner = objectValue(segment?.corner);
    const prePadding = numericValue(corner.pre_padding_m, defaultCornerPaddingM);
    const postPadding = numericValue(corner.post_padding_m, defaultCornerPaddingM);
    setDraft({
      start: clampDistance(segment?.start_distance_m ?? bounds.minimum, bounds),
      end: clampDistance(segment?.end_distance_m ?? bounds.maximum, bounds),
      activeEndpoint: "start",
      selectedCornerLabel: typeof corner.label === "string" ? corner.label : null,
      prePaddingM: prePadding,
      postPaddingM: postPadding
    });
  }, [open, payload, bounds?.minimum, bounds?.maximum]);

  const available = payload?.status === "available" && payload.points.length >= 2 && draft !== null && bounds !== null;
  const projectedCorners = available
    ? payload.corners.filter((corner) => corner.distance_m !== null && corner.display_x !== null && corner.display_y !== null)
    : [];
  const selectedCorner = available && draft.selectedCornerLabel
    ? projectedCorners.find((corner) => corner.label === draft.selectedCornerLabel) ?? null
    : null;
  const startMarker = available ? markerAtDistance(payload.points, draft.start) : null;
  const endMarker = available ? markerAtDistance(payload.points, draft.end) : null;
  const fullTrace = payload ? polylinePoints(payload.points) : "";
  const selectedTrace = available ? segmentPolylinePoints(payload.points, draft.start, draft.end) : "";

  function setEndpoint(endpoint: "start" | "end", distance: number) {
    if (!bounds) return;
    setDraft((current) => {
      if (!current) return current;
      const nextDistance = clampDistance(distance, bounds);
      if (endpoint === "start") {
        return { ...current, start: Math.min(nextDistance, current.end), activeEndpoint: endpoint, selectedCornerLabel: null };
      }
      return { ...current, end: Math.max(nextDistance, current.start), activeEndpoint: endpoint, selectedCornerLabel: null };
    });
  }

  function resetToFullLap() {
    if (!bounds || !draft) return;
    setDraft({ ...draft, start: bounds.minimum, end: bounds.maximum, selectedCornerLabel: null });
  }

  function selectCorner(corner: TrackMapCorner) {
    const cornerDistance = corner.distance_m;
    if (!bounds || cornerDistance === null || cornerDistance === undefined) return;
    setDraft((current) => {
      const prePaddingM = current?.prePaddingM ?? defaultCornerPaddingM;
      const postPaddingM = current?.postPaddingM ?? defaultCornerPaddingM;
      return {
        start: clampDistance(cornerDistance - prePaddingM, bounds),
        end: clampDistance(cornerDistance + postPaddingM, bounds),
        activeEndpoint: "start",
        selectedCornerLabel: corner.label,
        prePaddingM,
        postPaddingM
      };
    });
  }

  function setCornerPadding(key: "prePaddingM" | "postPaddingM", value: number) {
    if (!bounds || !draft) return;
    const nextValue = Math.max(0, Number.isFinite(value) ? value : 0);
    const nextDraft = { ...draft, [key]: nextValue };
    const corner = projectedCorners.find((item) => item.label === nextDraft.selectedCornerLabel);
    if (corner?.distance_m !== null && corner?.distance_m !== undefined) {
      nextDraft.start = clampDistance(corner.distance_m - nextDraft.prePaddingM, bounds);
      nextDraft.end = clampDistance(corner.distance_m + nextDraft.postPaddingM, bounds);
    }
    setDraft(nextDraft);
  }

  function selectNearestPoint(event: MouseEvent<SVGSVGElement>) {
    if (!available) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 108 - 4;
    const y = ((event.clientY - rect.top) / rect.height) * 108 - 4;
    setEndpoint(draft.activeEndpoint, nearestPointDistance(payload.points, x, y));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Track Range" className="w-[min(920px,calc(100vw-32px))]">
      {loading ? (
        <div className="flex min-h-64 items-center justify-center rounded-md border border-line bg-slate-50 text-sm font-medium text-muted">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading track
          </span>
        </div>
      ) : error ? (
        <div className="grid gap-4">
          <ErrorList errors={[error]} />
          <div className="flex justify-end">
            <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          </div>
        </div>
      ) : available ? (
        <div className="grid gap-4">
          <div className="grid gap-3 lg:hidden">
            <dl className="grid gap-2">
              <Metric label="Selected range" value={`${Math.round(Math.min(draft.start, draft.end))}-${Math.round(Math.max(draft.start, draft.end))} m`} />
              <Metric label="Loaded range" value={`${Math.round(bounds.minimum)}-${Math.round(bounds.maximum)} m`} />
            </dl>
            <div className="flex flex-wrap justify-end gap-2">
              <Button onClick={resetToFullLap}>Reset</Button>
              <Button onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button
                variant="primary"
                icon={<Save className="h-4 w-4" />}
                onClick={() => onApply(
                  draft.start,
                  draft.end,
                  payload,
                  selectedCorner ? {
                    corner: selectedCorner,
                    prePaddingM: draft.prePaddingM,
                    postPaddingM: draft.postPaddingM
                  } : null
                )}
              >
                Apply
              </Button>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px]">
            <div className="rounded-md border border-line bg-slate-50 p-3">
              <svg
                className="h-[min(58vh,440px)] w-full cursor-crosshair"
                data-testid="track-map-selector"
                role="img"
                viewBox="-4 -4 108 108"
                onClick={selectNearestPoint}
              >
                <polyline points={fullTrace} fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points={selectedTrace} fill="none" stroke="#0f766e" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                {startMarker && (
                  <circle cx={startMarker.display_x} cy={startMarker.display_y} r="3.5" fill="#0f766e" stroke="#ffffff" strokeWidth="1.5" />
                )}
                {endMarker && (
                  <circle cx={endMarker.display_x} cy={endMarker.display_y} r="3.5" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
                )}
                {projectedCorners.map((corner) => (
                  <g key={corner.label} className="cursor-pointer" onClick={(event) => { event.stopPropagation(); selectCorner(corner); }}>
                    <title>{`Turn ${corner.label}`}</title>
                    <circle
                      cx={corner.display_x ?? 0}
                      cy={corner.display_y ?? 0}
                      r={draft.selectedCornerLabel === corner.label ? "3.8" : "2.8"}
                      fill={draft.selectedCornerLabel === corner.label ? "#f97316" : "#ffffff"}
                      stroke="#f97316"
                      strokeWidth="1.4"
                    />
                    <text x={(corner.display_x ?? 0) + 2.6} y={(corner.display_y ?? 0) - 2.6} className="fill-slate-800 text-[4px] font-semibold">{corner.label}</text>
                  </g>
                ))}
              </svg>
            </div>
            <div className="grid content-start gap-3">
              <dl className="hidden gap-2 lg:grid">
                <Metric label="Selected range" value={`${Math.round(Math.min(draft.start, draft.end))}-${Math.round(Math.max(draft.start, draft.end))} m`} />
                <Metric label="Loaded range" value={`${Math.round(bounds.minimum)}-${Math.round(bounds.maximum)} m`} />
              </dl>
              <div className="grid grid-cols-2 gap-2">
                <Button variant={draft.activeEndpoint === "start" ? "primary" : "secondary"} onClick={() => setDraft({ ...draft, activeEndpoint: "start" })}>Start</Button>
                <Button variant={draft.activeEndpoint === "end" ? "primary" : "secondary"} onClick={() => setDraft({ ...draft, activeEndpoint: "end" })}>End</Button>
              </div>
              <Field label="Start" type="number" min={bounds.minimum} max={bounds.maximum} value={draft.start} onChange={(event) => setEndpoint("start", Number(event.target.value))} />
              <Field label="End" type="number" min={bounds.minimum} max={bounds.maximum} value={draft.end} onChange={(event) => setEndpoint("end", Number(event.target.value))} />
              <div className="hidden flex-wrap justify-end gap-2 lg:flex">
                <Button onClick={resetToFullLap}>Reset</Button>
                <Button onClick={() => onOpenChange(false)}>Cancel</Button>
                <Button
                  variant="primary"
                  icon={<Save className="h-4 w-4" />}
                  onClick={() => onApply(
                    draft.start,
                    draft.end,
                    payload,
                    selectedCorner ? {
                      corner: selectedCorner,
                      prePaddingM: draft.prePaddingM,
                      postPaddingM: draft.postPaddingM
                    } : null
                  )}
                >
                  Apply
                </Button>
              </div>
              {projectedCorners.length > 0 && (
                <div className="grid gap-2">
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Before" type="number" min={0} value={draft.prePaddingM} onChange={(event) => setCornerPadding("prePaddingM", Number(event.target.value))} />
                    <Field label="After" type="number" min={0} value={draft.postPaddingM} onChange={(event) => setCornerPadding("postPaddingM", Number(event.target.value))} />
                  </div>
                  <div className="grid max-h-40 grid-cols-3 gap-2 overflow-auto rounded-md border border-line p-2">
                    {projectedCorners.map((corner) => (
                      <Button
                        key={corner.label}
                        variant={draft.selectedCornerLabel === corner.label ? "primary" : "secondary"}
                        onClick={() => selectCorner(corner)}
                      >
                        {corner.label}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <TrackDistanceSlider label="Start" value={draft.start} minimum={bounds.minimum} maximum={draft.end} onChange={(value) => setEndpoint("start", value)} />
            <TrackDistanceSlider label="End" value={draft.end} minimum={draft.start} maximum={bounds.maximum} onChange={(value) => setEndpoint("end", value)} />
          </div>
          {payload.diagnostics.length > 0 && <WarningList warnings={payload.diagnostics.map((item) => item.message)} />}
        </div>
      ) : (
        <div className="grid gap-4">
          <div className="rounded-md border border-line bg-slate-50 p-4">
            <StatusBadge value={payload?.status ?? "unavailable"} />
            <div className="mt-3 grid gap-2">
              {(payload?.diagnostics.length ? payload.diagnostics : [{ field: "track_map", message: "Track geometry is unavailable" }]).map((item) => (
                <div key={`${item.field}-${item.message}`} className="text-sm text-muted">{item.message}</div>
              ))}
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function TrackDistanceSlider({
  label,
  value,
  minimum,
  maximum,
  unit = "m",
  onChange
}: {
  label: string;
  value: number;
  minimum: number;
  maximum: number;
  unit?: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <input
        className="h-9 w-full accent-teal-700"
        type="range"
        min={minimum}
        max={maximum}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="text-xs text-muted">{Math.round(value)}{unit ? ` ${unit}` : ""}</span>
    </label>
  );
}

function PlaybackExplorer({
  sessions
}: {
  sessions: AnalysisSession[];
}) {
  const loadedSessions = sessions.filter((session) => session.load_state === "loaded");
  const [sessionId, setSessionId] = useState(loadedSessions[0]?.session_id ?? "");
  const [mode, setMode] = useState<PlaybackMode>("lap");
  const [cursorLap, setCursorLap] = useState<number | null>(null);
  const [cursorTime, setCursorTime] = useState<number | null>(null);
  const [timelineSpanSeconds, setTimelineSpanSeconds] = useState<number | null>(null);
  const [selectedDrivers, setSelectedDrivers] = useState<string[]>([]);
  const [payload, setPayload] = useState<PlaybackPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debug = playbackDebugEnabled();
  const frame = payload?.frames[0] ?? null;
  const lapBounds = payload ? playbackLapBounds(payload) : null;
  const timeBounds = payload ? playbackTimeBounds(payload) : null;
  const lapMinimum = lapBounds?.minimum ?? 1;
  const lapMaximum = lapBounds?.maximum ?? lapMinimum;
  const lapCursor = clampNumber(cursorLap ?? lapMinimum, lapMinimum, lapMaximum);
  const timeCursor = timeBounds
    ? clampNumber(cursorTime ?? frame?.session_time_seconds ?? timeBounds.minimum, timeBounds.minimum, timeBounds.maximum)
    : 0;
  const timeView = timeBounds ? playbackTimeView(timeBounds, timeCursor, timelineSpanSeconds) : null;
  const markers = frame?.markers ?? [];
  const timeAvailability = payload?.available_modes.time;

  useEffect(() => {
    if (!sessionId && loadedSessions[0]) setSessionId(loadedSessions[0].session_id);
  }, [sessionId, loadedSessions]);

  useEffect(() => {
    setCursorLap(null);
    setCursorTime(null);
    setTimelineSpanSeconds(null);
    setSelectedDrivers([]);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      api
        .getAnalysisPlayback({
          session_id: sessionId,
          mode,
          cursor: mode === "lap" ? cursorLap : cursorTime,
          max_frames: 1,
          max_markers: 60,
          max_points: 500,
          maximum_sample_gap_seconds: 5,
          maximum_timing_sample_age_seconds: 10
        })
        .then((nextPayload) => {
          if (cancelled) return;
          setPayload(nextPayload);
          const bounds = playbackLapBounds(nextPayload);
          if (bounds) {
            const defaultLap = Math.round(nextPayload.frames[0]?.cursor?.leader_lap_number ?? nextPayload.frames[0]?.lap_number ?? nextPayload.available_modes.lap?.default ?? bounds.minimum);
            setCursorLap((current) => clampNumber(current ?? defaultLap, bounds.minimum, bounds.maximum));
          }
          const nextTimeBounds = playbackTimeBounds(nextPayload);
          if (nextTimeBounds) {
            const defaultTime = nextPayload.frames[0]?.session_time_seconds ?? nextPayload.available_modes.time?.default ?? nextTimeBounds.minimum;
            setCursorTime((current) => clampNumber(current ?? defaultTime, nextTimeBounds.minimum, nextTimeBounds.maximum));
            setTimelineSpanSeconds((current) => {
              const fullSpan = nextTimeBounds.maximum - nextTimeBounds.minimum;
              if (!Number.isFinite(fullSpan) || fullSpan <= 0) return null;
              return current === null ? fullSpan : clampNumber(current, Math.min(fullSpan, 10), fullSpan);
            });
          }
        })
        .catch((requestError) => {
          if (cancelled) return;
          setPayload(null);
          setError(message(requestError));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sessionId, mode, cursorLap, cursorTime]);

  function zoomTimeline(factor: number) {
    if (!timeBounds) return;
    const fullSpan = timeBounds.maximum - timeBounds.minimum;
    if (!Number.isFinite(fullSpan) || fullSpan <= 0) return;
    setTimelineSpanSeconds((current) => clampNumber((current ?? fullSpan) * factor, Math.min(fullSpan, 10), fullSpan));
  }

  function fitTimeline() {
    if (!timeBounds) return;
    setTimelineSpanSeconds(timeBounds.maximum - timeBounds.minimum);
  }

  function toggleSelectedDriver(driver: string) {
    setSelectedDrivers((current) => current.includes(driver) ? current.filter((item) => item !== driver) : [...current, driver]);
  }

  if (loadedSessions.length === 0) {
    return (
      <Panel title="Race Playback">
        <div className="rounded-md border border-dashed border-line bg-slate-50 p-6 text-sm text-muted">No loaded sessions</div>
      </Panel>
    );
  }

  return (
    <Panel
      title="Race Playback"
      actions={
        <div className="flex flex-wrap items-center justify-end gap-3">
          {frame && (
            <div
              className="inline-flex w-fit items-center rounded-full border border-line bg-slate-50 px-3 py-1 text-xs font-semibold tabular-nums text-ink"
              data-testid="playback-cursor-chip"
            >
              Lap {frame.cursor.leader_lap_number ?? frame.lap_number ?? "—"} · {formatSessionTime(frame.session_time_seconds)} · {markers.filter((marker) => marker.status !== "missing").length} cars
            </div>
          )}
          <SelectField
            label="Session"
            className="flex min-w-[240px] items-center gap-2"
            value={sessionId}
            onValueChange={setSessionId}
            options={loadedSessions.map((session) => ({ value: session.session_id, label: session.name }))}
          />
        </div>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-3">
          {error && <ErrorList errors={[error]} />}
          {payload?.status === "available" && frame && lapBounds ? (
            <>
              <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_112px] xl:items-stretch">
                <div className="relative min-w-0">
                  <PlaybackMap
                    points={payload.points}
                    markers={markers}
                    selectedDrivers={selectedDrivers}
                    onToggleDriver={toggleSelectedDriver}
                  />
                  <div className="mt-3 min-w-0 xl:absolute xl:bottom-2 xl:right-3 xl:top-2 xl:mt-0 xl:w-[min(430px,55%)]">
                    <PlaybackTimingTower
                      markers={markers}
                      selectedDrivers={selectedDrivers}
                      onToggleDriver={toggleSelectedDriver}
                      debug={debug}
                    />
                  </div>
                </div>
                <PlaybackTimeline
                  mode={mode}
                  payload={payload}
                  lapBounds={lapBounds}
                  timeBounds={timeBounds}
                  timeView={timeView}
                  lapValue={lapCursor}
                  timeValue={timeCursor}
                  loading={loading}
                  timeAvailable={payload !== null && timeAvailability?.available === true}
                  onModeChange={setMode}
                  onLapChange={(value) => setCursorLap(Math.round(value))}
                  onTimeChange={setCursorTime}
                  onZoomIn={() => zoomTimeline(0.5)}
                  onZoomOut={() => zoomTimeline(2)}
                  onFit={fitTimeline}
                />
              </div>
            </>
          ) : loading ? (
            <LoadingBlock label="Loading playback" />
          ) : (
            <div className="rounded-md border border-line bg-slate-50 p-4">
              <StatusBadge value={payload?.status ?? "unavailable"} />
              <div className="mt-3 grid gap-2">
                {(payload?.diagnostics.length ? payload.diagnostics : [{ field: "playback", message: "Playback position data is unavailable" }]).map((item) => (
                  <div key={`${item.field}-${item.message}`} className="text-sm text-muted">{item.message}</div>
                ))}
              </div>
            </div>
          )}
          {payload?.diagnostics.length ? <WarningList warnings={payload.diagnostics.map((item) => item.message)} /> : null}
        </div>
      </div>
    </Panel>
  );
}

const TIMING_PERFORMANCE_COLORS = {
  fastest: "#bd29c1",
  personalBest: "#31ce34",
  slower: "#ddcd35"
} as const;

const TIMING_PERFORMANCE_TEXT = {
  fastest: "text-[#bd29c1]",
  personalBest: "text-[#31ce34]",
  slower: "text-[#ddcd35]"
} as const;

const TIMING_PERFORMANCE_BACKGROUND = {
  fastest: "bg-[#bd29c1]",
  personalBest: "bg-[#31ce34]",
  slower: "bg-[#ddcd35]"
} as const;

function PlaybackTimingTower({
  markers,
  selectedDrivers,
  onToggleDriver,
  debug
}: {
  markers: PlaybackMarker[];
  selectedDrivers: string[];
  onToggleDriver: (driver: string) => void;
  debug: boolean;
}) {
  const [view, setView] = useState<"race" | "laps" | "sectors-last" | "sectors-best" | "mini">("race");
  const [collapsed, setCollapsed] = useState(false);
  const selectedDriverSet = new Set(selectedDrivers);
  const selectedMarkers = markers.filter((marker) => selectedDriverSet.has(marker.driver));
  const focusedMarker = selectedMarkers.length === 1 ? selectedMarkers[0] : null;
  const relativeMode = selectedMarkers.length === 1;
  const comparisonMode = selectedMarkers.length > 1;
  const fastestLastLap = minimumFinite(markers.map((marker) => marker.context.last_lap_time_seconds));
  const fastestBestLap = minimumFinite(markers.map((marker) => marker.context.best_lap_time_seconds));
  const fastestLastSectors = [0, 1, 2].map((index) => minimumFinite(markers.map((marker) => marker.context.last_sector_times_seconds[index])));
  const fastestBestSectors = [0, 1, 2].map((index) => minimumFinite(markers.map((marker) => marker.context.best_sector_times_seconds[index])));
  const selectedFastestLastLap = minimumFinite(selectedMarkers.map((marker) => marker.context.last_lap_time_seconds));
  const selectedFastestBestLap = minimumFinite(selectedMarkers.map((marker) => marker.context.best_lap_time_seconds));
  const selectedFastestLastSectors = [0, 1, 2].map((index) => minimumFinite(selectedMarkers.map((marker) => marker.context.last_sector_times_seconds[index])));
  const selectedFastestBestSectors = [0, 1, 2].map((index) => minimumFinite(selectedMarkers.map((marker) => marker.context.best_sector_times_seconds[index])));
  const selectedFastestTheoreticalLap = minimumFinite(selectedMarkers.map((marker) => sumCompleteSectors(marker.context.best_sector_times_seconds)));
  const sectorMode: "last" | "best" = view === "sectors-best" ? "best" : "last";

  if (collapsed) {
    return (
      <button
        type="button"
        className="ml-auto flex h-10 items-center gap-2 rounded-md border border-line bg-white/90 px-3 text-xs font-semibold text-ink shadow-lg backdrop-blur"
        onClick={() => setCollapsed(false)}
        data-testid="playback-timing-expand"
      >
        <ChevronLeft className="h-4 w-4" />
        Timing
      </button>
    );
  }

  return (
    <div className="grid max-h-full min-w-0 gap-1 overflow-hidden rounded-lg border border-white/70 bg-white/90 p-1.5 shadow-xl backdrop-blur-md" data-testid="playback-timing-tower">
      <div className="flex min-w-0 items-center gap-1 px-1">
        <div className="flex shrink-0 items-center gap-1">
          <div className="text-base font-semibold text-ink">Live timing</div>
          {debug && <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-muted">Debug</span>}
        </div>
        <div className="flex min-w-0 flex-1 gap-0.5 overflow-x-auto rounded bg-slate-100 p-0.5" aria-label="Timing view">
          {([
            ["race", "Race"],
            ["laps", "Laps"],
            ["sectors-last", "Last Sec"],
            ["sectors-best", "Best Sec"],
            ["mini", "Minis"]
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold text-muted", view === value && "bg-white text-ink shadow-sm")}
              onClick={() => setView(value)}
              data-testid={`playback-timing-view-${value}`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex shrink-0 items-center">
          <button type="button" className="rounded p-1 text-muted hover:bg-slate-100 hover:text-ink" aria-label="Collapse timing" onClick={() => setCollapsed(true)} data-testid="playback-timing-collapse">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="min-h-0 overflow-auto rounded-md border border-line bg-panel">
        {markers.length === 0 ? (
          <div className="px-3 py-3 text-sm text-muted">No markers</div>
        ) : view === "race" ? (
          <>
            <div className="grid grid-cols-[0.15rem_1.2rem_2.2rem_2.8rem_2.7rem_3rem_3.2rem] items-center justify-center gap-x-0.5 border-b border-line bg-slate-50 pr-1 py-0.5 text-[11px] font-semibold uppercase text-muted sm:grid-cols-[0.2rem_1.5rem_2.8rem_3.6rem_3.6rem_4rem_4.1rem] sm:gap-x-1 sm:pr-2">
              <span /><span>P</span><span>DRV</span><span className="text-right">INT</span><span className="text-right">{relativeMode ? "REL" : "GAP"}</span><span className="text-center">{relativeMode ? "TYRE Δ" : "TYRE"}</span><span className="text-right">{relativeMode ? "LAST Δ" : "LAST"}</span>
            </div>
            {markers.map((marker) => {
              const selected = selectedDriverSet.has(marker.driver);
              return (
                <div key={marker.driver} className={cn(selected && "bg-teal-50")} data-testid={`playback-timing-row-${marker.driver}`}>
                  <button
                    type="button"
                    className="grid h-[19px] w-full grid-cols-[0.15rem_1.2rem_2.2rem_2.8rem_2.7rem_3rem_3.2rem] items-center justify-center gap-x-0.5 border-b border-line pr-1 text-left text-[11px] hover:bg-slate-50/80 sm:grid-cols-[0.2rem_1.5rem_2.8rem_3.6rem_3.6rem_4rem_4.1rem] sm:gap-x-1 sm:pr-2"
                    onClick={() => onToggleDriver(marker.driver)}
                    aria-pressed={selected}
                  >
                    <span className="h-full w-full" style={{ backgroundColor: marker.color ?? "#0f766e" }} aria-hidden="true" />
                    <span className="font-bold tabular-nums text-ink">{marker.context.timing_position ?? marker.context.position ?? "—"}</span>
                    <span className={cn("flex min-w-0 items-center gap-1 truncate font-bold text-ink", selected && "text-brand")}>
                      {driverAbbreviation(marker.driver)}
                      {marker.context.pit_state !== "none" && <span className="text-[8px] font-bold text-amber-700">PIT</span>}
                    </span>
                    <span className="text-right tabular-nums text-muted">{relativeMode ? "—" : formatRaceGap(marker.context.interval_to_ahead_seconds, marker.context.interval_to_ahead_laps, { leaderLabel: "—" })}</span>
                    <span className="text-right font-semibold tabular-nums text-ink">{playbackTimingGap(marker, focusedMarker)}</span>
                    <TyreIcon compound={marker.context.compound} age={marker.context.tyre_age_laps} referenceAge={focusedMarker?.context.tyre_age_laps} relative={relativeMode} isReference={selected && relativeMode} />
                    <span
                      className={cn("text-right font-semibold tabular-nums", relativeMode ? relativeValueTone(marker.context.last_lap_time_seconds, focusedMarker?.context.last_lap_time_seconds, selected) : comparisonMode && selected && isTimingWinner(marker.context.last_lap_time_seconds, selectedFastestLastLap) ? comparisonWinnerClass() : lastLapToneClass(marker.context.last_lap_time_seconds, marker.context.best_lap_time_seconds, fastestBestLap))}
                      data-comparison-winner={comparisonMode && selected && isTimingWinner(marker.context.last_lap_time_seconds, selectedFastestLastLap) ? "last-lap" : undefined}
                    >
                      {relativeMode ? formatRelativeValue(marker.context.last_lap_time_seconds, focusedMarker?.context.last_lap_time_seconds, selected) : formatLapTime(marker.context.last_lap_time_seconds)}
                    </span>
                  </button>
                  {selected && debug && <div className="px-3 pb-2"><PlaybackDebugDetails marker={marker} /></div>}
                </div>
              );
            })}
          </>
        ) : view === "laps" ? (
          <>
            <div className="grid grid-cols-[0.15rem_1.2rem_2.2rem_3.8rem_3.8rem] items-center justify-center gap-x-0.5 border-b border-line bg-slate-50 pr-1 py-0.5 text-[11px] font-semibold uppercase text-muted sm:grid-cols-[0.2rem_1.5rem_2.8rem_4.6rem_4.6rem] sm:gap-x-1 sm:pr-2">
              <span /><span>P</span><span>DRV</span><span className="text-right">{relativeMode ? "LAST Δ" : "LAST"}</span><span className="text-right">{relativeMode ? "BEST Δ" : "BEST"}</span>
            </div>
            {markers.map((marker) => {
              const selected = selectedDriverSet.has(marker.driver);
              return (
                <button key={marker.driver} type="button" className={cn(
                  "grid h-[19px] w-full grid-cols-[0.15rem_1.2rem_2.2rem_3.8rem_3.8rem] items-center justify-center gap-x-0.5 border-b border-line pr-1 text-left text-[11px] hover:bg-slate-50 sm:grid-cols-[0.2rem_1.5rem_2.8rem_4.6rem_4.6rem] sm:gap-x-1 sm:pr-2",
                  selected && "bg-teal-50"
                )} onClick={() => onToggleDriver(marker.driver)} data-testid={`playback-timing-row-${marker.driver}`} aria-pressed={selected}>
                  <span className="h-full" style={{ backgroundColor: marker.color ?? "#0f766e" }} />
                  <span className="font-bold">{marker.context.timing_position ?? marker.context.position ?? "—"}</span>
                  <span className={cn("font-bold", selected && "text-brand")}>{driverAbbreviation(marker.driver)}</span>
                  <span className={cn("text-right font-semibold tabular-nums", relativeMode ? relativeValueTone(marker.context.last_lap_time_seconds, focusedMarker?.context.last_lap_time_seconds, selected) : comparisonMode && selected && isTimingWinner(marker.context.last_lap_time_seconds, selectedFastestLastLap) ? comparisonWinnerClass() : lastLapToneClass(marker.context.last_lap_time_seconds, marker.context.best_lap_time_seconds, fastestBestLap))} data-comparison-winner={comparisonMode && selected && isTimingWinner(marker.context.last_lap_time_seconds, selectedFastestLastLap) ? "last-lap" : undefined}>{relativeMode ? formatRelativeValue(marker.context.last_lap_time_seconds, focusedMarker?.context.last_lap_time_seconds, selected) : formatLapTime(marker.context.last_lap_time_seconds)}</span>
                  <span className={cn("text-right font-semibold tabular-nums", relativeMode ? relativeValueTone(marker.context.best_lap_time_seconds, focusedMarker?.context.best_lap_time_seconds, selected) : comparisonMode && selected && isTimingWinner(marker.context.best_lap_time_seconds, selectedFastestBestLap) && comparisonWinnerClass())} data-comparison-winner={comparisonMode && selected && isTimingWinner(marker.context.best_lap_time_seconds, selectedFastestBestLap) ? "best-lap" : undefined}>{relativeMode ? formatRelativeValue(marker.context.best_lap_time_seconds, focusedMarker?.context.best_lap_time_seconds, selected) : formatLapTime(marker.context.best_lap_time_seconds)}</span>
                </button>
              );
            })}
          </>
        ) : view === "sectors-last" || view === "sectors-best" ? (
          <>
            <div className="grid grid-cols-[0.15rem_1.2rem_2.2rem_repeat(3,2.7rem)_3.2rem] items-center justify-center gap-x-0.5 border-b border-line bg-slate-50 pr-1 py-0.5 text-[11px] font-semibold uppercase text-muted sm:grid-cols-[0.2rem_1.5rem_2.8rem_repeat(3,3.3rem)_4rem] sm:gap-x-1 sm:pr-2">
              <span /><span>P</span><span>DRV</span><span className="text-right">S1{relativeMode ? " Δ" : ""}</span><span className="text-right">S2{relativeMode ? " Δ" : ""}</span><span className="text-right">S3{relativeMode ? " Δ" : ""}</span><span className="text-right">{sectorMode === "best" ? (relativeMode ? "THEO Δ" : "THEO") : (relativeMode ? "LAP Δ" : "LAP")}</span>
            </div>
            {markers.map((marker) => {
              const selected = selectedDriverSet.has(marker.driver);
              const values = sectorMode === "best" ? marker.context.best_sector_times_seconds : marker.context.last_sector_times_seconds;
              const fastest = sectorMode === "best" ? fastestBestSectors : fastestLastSectors;
              const total = values.length === 3 && values.every((value) => value !== null) ? values.reduce<number>((sum, value) => sum + Number(value), 0) : null;
              const referenceValues = sectorMode === "best" ? focusedMarker?.context.best_sector_times_seconds : focusedMarker?.context.last_sector_times_seconds;
              const referenceTotal = sectorMode === "best"
                ? referenceValues?.length === 3 && referenceValues.every((value) => value !== null)
                  ? referenceValues.reduce<number>((sum, value) => sum + Number(value), 0)
                  : null
                : focusedMarker?.context.last_lap_time_seconds;
              return (
                <button key={marker.driver} type="button" className={cn("grid h-[19px] w-full grid-cols-[0.15rem_1.2rem_2.2rem_repeat(3,2.7rem)_3.2rem] items-center justify-center gap-x-0.5 border-b border-line pr-1 text-left text-[11px] hover:bg-slate-50 sm:grid-cols-[0.2rem_1.5rem_2.8rem_repeat(3,3.3rem)_4rem] sm:gap-x-1 sm:pr-2", selected && "bg-teal-50")} onClick={() => onToggleDriver(marker.driver)} data-testid={`playback-timing-row-${marker.driver}`} aria-pressed={selected}>
                  <span className="h-full" style={{ backgroundColor: marker.color ?? "#0f766e" }} />
                  <span className="font-bold">{marker.context.timing_position ?? marker.context.position ?? "—"}</span>
                  <span className={cn("font-bold", selected && "text-brand")}>{driverAbbreviation(marker.driver)}</span>
                  {values.map((value, index) => <SectorComparison key={index} value={value} fastest={fastest[index]} mode={sectorMode} reference={relativeMode ? referenceValues?.[index] : undefined} relative={relativeMode} isReference={selected && relativeMode} comparisonWinner={comparisonMode && selected && isTimingWinner(value, (sectorMode === "best" ? selectedFastestBestSectors : selectedFastestLastSectors)[index])} comparisonLabel={`S${index + 1}`} />)}
                  <span
                    className={cn("text-right font-semibold tabular-nums", relativeMode ? relativeValueTone(sectorMode === "best" ? total : marker.context.last_lap_time_seconds, referenceTotal, selected) : comparisonMode && selected && isTimingWinner(sectorMode === "best" ? total : marker.context.last_lap_time_seconds, sectorMode === "best" ? selectedFastestTheoreticalLap : selectedFastestLastLap) ? comparisonWinnerClass() : sectorMode === "last" && lastLapToneClass(marker.context.last_lap_time_seconds, marker.context.best_lap_time_seconds, fastestBestLap))}
                    data-comparison-winner={comparisonMode && selected && isTimingWinner(sectorMode === "best" ? total : marker.context.last_lap_time_seconds, sectorMode === "best" ? selectedFastestTheoreticalLap : selectedFastestLastLap) ? (sectorMode === "best" ? "theoretical-lap" : "last-lap") : undefined}
                  >
                    {relativeMode ? formatRelativeValue(sectorMode === "best" ? total : marker.context.last_lap_time_seconds, referenceTotal, selected) : sectorMode === "best" ? formatLapTime(total) : formatLapTime(marker.context.last_lap_time_seconds)}
                  </span>
                </button>
              );
            })}
          </>
        ) : (
          <>
            <div className="grid grid-cols-[0.15rem_1.2rem_2.2rem_minmax(0,1fr)] items-center gap-x-0.5 border-b border-line bg-slate-50 pr-1 py-0.5 text-[11px] font-semibold uppercase text-muted sm:grid-cols-[0.2rem_1.5rem_2.8rem_minmax(0,1fr)] sm:gap-x-1 sm:pr-2">
              <span /><span>P</span><span>DRV</span><span>LAST LAP</span>
            </div>
            {markers.map((marker) => {
              const selected = selectedDriverSet.has(marker.driver);
              return (
                <button key={marker.driver} type="button" className={cn("grid h-[19px] w-full grid-cols-[0.15rem_1.2rem_2.2rem_minmax(0,1fr)] items-center gap-x-0.5 border-b border-line pr-1 text-left text-[11px] hover:bg-slate-50 sm:grid-cols-[0.2rem_1.5rem_2.8rem_minmax(0,1fr)] sm:gap-x-1 sm:pr-2", selected && "bg-teal-50")} onClick={() => onToggleDriver(marker.driver)} data-testid={`playback-timing-row-${marker.driver}`} aria-pressed={selected}>
                  <span className="h-full" style={{ backgroundColor: marker.color ?? "#0f766e" }} />
                  <span className="font-bold">{marker.context.timing_position ?? marker.context.position ?? "—"}</span>
                  <span className={cn("font-bold", selected && "text-brand")}>{driverAbbreviation(marker.driver)}</span>
                  <MiniSectorStrip states={marker.context.mini_sector_states} groups={marker.context.mini_sector_groups} />
                </button>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}

function playbackTimingGap(marker: PlaybackMarker, focusedMarker: PlaybackMarker | null): string {
  if (focusedMarker === null) {
    return formatRaceGap(marker.context.gap_to_leader_seconds, marker.context.gap_to_leader_laps, { leaderLabel: "Leader" });
  }
  if (marker.driver === focusedMarker.driver) return "REF";
  const markerLaps = comparableLapDeficit(marker);
  const focusedLaps = comparableLapDeficit(focusedMarker);
  if (markerLaps !== null && focusedLaps !== null && markerLaps !== focusedLaps) {
    const delta = markerLaps - focusedLaps;
    return `${delta > 0 ? "+" : "−"}${Math.abs(delta)} LAP${Math.abs(delta) === 1 ? "" : "S"}`;
  }
  const markerGap = freshTimingGap(marker);
  const focusedGap = freshTimingGap(focusedMarker);
  if (markerGap === null || focusedGap === null) return "—";
  return formatGapSeconds(markerGap - focusedGap, { signed: true, leaderLabel: "0.000s" });
}

function comparableLapDeficit(marker: PlaybackMarker): number | null {
  if (marker.context.timing_status !== "fresh") return null;
  const laps = marker.context.gap_to_leader_laps;
  if (laps !== null && laps !== undefined && Number.isFinite(laps)) return laps;
  const seconds = marker.context.gap_to_leader_seconds;
  return seconds !== null && seconds !== undefined && Number.isFinite(seconds) ? 0 : null;
}

function freshTimingGap(marker: PlaybackMarker): number | null {
  const gap = marker.context.gap_to_leader_seconds;
  if (marker.context.timing_status !== "fresh" || gap === null || gap === undefined || !Number.isFinite(gap)) return null;
  return gap;
}

function MiniSectorStrip({
  states,
  groups
}: {
  states: PlaybackMarker["context"]["mini_sector_states"];
  groups: PlaybackMarker["context"]["mini_sector_groups"];
}) {
  if (!states.length) return <span className="text-xs text-muted">—</span>;
  const summary = [
    `${states.filter((state) => state === "fastest").length} session best`,
    `${states.filter((state) => state === "faster").length} personal best`,
    `${states.filter((state) => state === "slower").length} slower`,
    `${states.filter((state) => state === "unavailable").length} unavailable`
  ].join(", ");
  return (
    <span className="flex min-w-0 items-center gap-[2px]" aria-label={`Mini sectors: ${summary}`} data-testid="mini-sector-strip">
      {states.map((state, index) => (
        <span
          key={index}
          data-mini-sector-group={groups[index] ?? 0}
          data-mini-sector-state={state}
          className={cn(
            "h-3.5 min-w-[3px] flex-1 rounded-[1px]",
            index > 0 && groups[index] !== groups[index - 1] && "ml-1.5",
            state === "fastest" && TIMING_PERFORMANCE_BACKGROUND.fastest,
            state === "faster" && TIMING_PERFORMANCE_BACKGROUND.personalBest,
            state === "slower" && TIMING_PERFORMANCE_BACKGROUND.slower,
            state === "unavailable" && "bg-slate-300"
          )}
          title={`${groups[index] ? `Sector ${groups[index]} · ` : ""}${state === "fastest" ? "Session best" : state === "faster" ? "Personal best" : state === "slower" ? "Slower" : "Unavailable"}`}
        />
      ))}
    </span>
  );
}

function TyreIcon({
  compound,
  age,
  referenceAge,
  relative = false,
  isReference = false
}: {
  compound: string | null | undefined;
  age: number | null | undefined;
  referenceAge?: number | null;
  relative?: boolean;
  isReference?: boolean;
}) {
  const code = compoundCode(compound);
  const iconByCode: Record<string, string> = {
    S: "/tyres/tire_S_red.svg",
    M: "/tyres/tire_M_yellow.svg",
    H: "/tyres/tire_H_white.svg",
    I: "/tyres/tire_I_green.svg",
    W: "/tyres/tire_W_blue.svg"
  };
  const label = compound?.trim() || "Unknown compound";
  return (
    <span className="flex items-center justify-center gap-1" title={label}>
      {iconByCode[code] ? <img src={iconByCode[code]} alt={label} className="h-4 w-4 shrink-0" /> : <span className="font-bold">{code}</span>}
      <span className={cn("text-[10px] font-semibold", relative ? relativeLapTone(age, referenceAge, isReference) : "text-muted")}>
        {relative ? formatRelativeLaps(age, referenceAge, isReference) : formatTyreAge(age)}
      </span>
    </span>
  );
}

function formatRelativeValue(
  value: number | null | undefined,
  reference: number | null | undefined,
  isReference: boolean
): string {
  if (isReference) return "REF";
  if (value === null || value === undefined || !Number.isFinite(value) || reference === null || reference === undefined || !Number.isFinite(reference)) return "—";
  const delta = value - reference;
  if (Math.abs(delta) <= 0.0005) return "0.000";
  return `${delta > 0 ? "+" : "−"}${Math.abs(delta).toFixed(3)}`;
}

function formatRelativeLaps(
  value: number | null | undefined,
  reference: number | null | undefined,
  isReference: boolean
): string {
  if (isReference) return "REF";
  if (value === null || value === undefined || !Number.isFinite(value) || reference === null || reference === undefined || !Number.isFinite(reference)) return "—";
  const delta = Math.round(value - reference);
  if (delta === 0) return "0L";
  return `${delta > 0 ? "+" : "−"}${Math.abs(delta)}L`;
}

function relativeValueTone(
  value: number | null | undefined,
  reference: number | null | undefined,
  isReference: boolean
): string {
  if (isReference) return "text-brand";
  if (value === null || value === undefined || !Number.isFinite(value) || reference === null || reference === undefined || !Number.isFinite(reference)) return "text-muted";
  const delta = value - reference;
  if (Math.abs(delta) <= 0.0005) return "text-purple-700";
  return delta < 0 ? "text-emerald-700" : "text-amber-700";
}

function relativeLapTone(
  value: number | null | undefined,
  reference: number | null | undefined,
  isReference: boolean
): string {
  if (isReference) return "text-brand";
  if (value === null || value === undefined || !Number.isFinite(value) || reference === null || reference === undefined || !Number.isFinite(reference)) return "text-muted";
  const delta = Math.round(value - reference);
  if (delta === 0) return "text-muted";
  return delta < 0 ? "text-emerald-700" : "text-amber-700";
}

function lastLapToneClass(
  lastLap: number | null | undefined,
  personalBest: number | null | undefined,
  sessionBest: number | null
): string {
  if (lastLap === null || lastLap === undefined || !Number.isFinite(lastLap)) return "text-muted";
  if (sessionBest !== null && Math.abs(lastLap - sessionBest) <= 0.0005) return TIMING_PERFORMANCE_TEXT.fastest;
  if (personalBest !== null && personalBest !== undefined && Number.isFinite(personalBest) && Math.abs(lastLap - personalBest) <= 0.0005) return TIMING_PERFORMANCE_TEXT.personalBest;
  return TIMING_PERFORMANCE_TEXT.slower;
}

function SectorComparison({
  value,
  fastest,
  mode,
  reference,
  relative = false,
  isReference = false,
  comparisonWinner = false,
  comparisonLabel
}: {
  value: number | null;
  fastest: number | null;
  mode: "last" | "best";
  reference?: number | null;
  relative?: boolean;
  isReference?: boolean;
  comparisonWinner?: boolean;
  comparisonLabel?: string;
}) {
  const delta = timingDelta(value, fastest);
  if (relative) {
    return (
      <span className={cn("text-right font-semibold tabular-nums", relativeValueTone(value, reference, isReference))}>
        {formatRelativeValue(value, reference, isReference)}
      </span>
    );
  }
  if (value === null || delta === null) return <span className="text-right text-muted">—</span>;
  const isFastest = Math.abs(delta) <= 0.0005;
  return (
    <span
      className={cn("text-right font-semibold tabular-nums", comparisonWinner ? comparisonWinnerClass() : isFastest ? TIMING_PERFORMANCE_TEXT.fastest : mode === "best" ? TIMING_PERFORMANCE_TEXT.personalBest : TIMING_PERFORMANCE_TEXT.slower)}
      title={comparisonWinner ? `Fastest selected ${comparisonLabel ?? "sector"}` : isFastest ? "Fastest visible sector" : `+${delta.toFixed(3)}s to fastest visible sector`}
      data-comparison-winner={comparisonWinner ? comparisonLabel : undefined}
    >
      {value.toFixed(3)}
    </span>
  );
}

function minimumFinite(values: Array<number | null | undefined>): number | null {
  const finite = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return finite.length ? Math.min(...finite) : null;
}

function timingDelta(value: number | null | undefined, reference: number | null): number | null {
  if (value === null || value === undefined || !Number.isFinite(value) || reference === null) return null;
  return Math.max(0, value - reference);
}

function isTimingWinner(value: number | null | undefined, fastestSelected: number | null) {
  return value !== null && value !== undefined && Number.isFinite(value) && fastestSelected !== null && Math.abs(value - fastestSelected) <= 0.0005;
}

function comparisonWinnerClass() {
  return cn(TIMING_PERFORMANCE_TEXT.fastest, "rounded-sm bg-[#bd29c1]/10");
}

function sumCompleteSectors(values: Array<number | null>) {
  return values.length === 3 && values.every((value) => value !== null) ? values.reduce<number>((sum, value) => sum + Number(value), 0) : null;
}

function PlaybackDebugDetails({ marker }: { marker: PlaybackMarker }) {
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-1 rounded bg-slate-100 p-2 font-mono text-[9px] text-muted" data-testid={`playback-debug-${marker.driver}`}>
      <span>map {marker.status}</span>
      <span>timing {marker.context.timing_status}</span>
      <span>interp {marker.interpolation_method}</span>
      <span>age {marker.context.timing_sample_age_seconds ?? "—"}s</span>
      <span className="col-span-2 truncate">source {marker.context.gap_source ?? "—"} / {marker.context.timing_app_source ?? "—"}</span>
    </div>
  );
}

function driverAbbreviation(driver: string): string {
  return driver.trim().toUpperCase().slice(0, 3) || "—";
}

function compoundCode(compound: string | null | undefined): string {
  const normalized = compound?.trim().toUpperCase();
  const codes: Record<string, string> = {
    SOFT: "S",
    MEDIUM: "M",
    HARD: "H",
    INTERMEDIATE: "I",
    WET: "W"
  };
  return normalized ? codes[normalized] ?? normalized.slice(0, 1) : "—";
}

function formatTyreAge(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${Math.max(0, Math.round(value))}L`;
}

function formatLapTime(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return minutes > 0 ? `${minutes}:${seconds.toFixed(3).padStart(6, "0")}` : seconds.toFixed(3);
}

function formatSectors(values: Array<number | null>): string {
  if (!values.length || values.every((value) => value === null)) return "—";
  return values.map((value, index) => `S${index + 1} ${value === null ? "—" : value.toFixed(3)}`).join(" · ");
}

function playbackDebugEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const value = new URLSearchParams(window.location.search).get("debug");
  return value === "" || value === "1" || value?.toLowerCase() === "true";
}

function formatGapSeconds(
  value: number | null | undefined,
  options: { signed?: boolean; leaderLabel?: string } = {}
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (Math.abs(value) < 0.0005) return options.leaderLabel ?? "0.000s";
  const prefix = options.signed && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(3)}s`;
}

function formatRaceGap(
  seconds: number | null | undefined,
  laps: number | null | undefined,
  options: { leaderLabel?: string } = {}
): string {
  if (laps !== null && laps !== undefined && Number.isFinite(laps)) {
    return `+${laps} LAP${laps === 1 ? "" : "S"}`;
  }
  return formatGapSeconds(seconds, options);
}

type PlaybackMapView = {
  scale: number;
  panX: number;
  panY: number;
  rotationDeg: number;
};

type PlaybackMapDrag = {
  pointerId: number;
  startX: number;
  startY: number;
  panX: number;
  panY: number;
  moved: boolean;
};

function PlaybackMap({
  points,
  markers,
  selectedDrivers,
  onToggleDriver
}: {
  points: TrackMapPoint[];
  markers: PlaybackMarker[];
  selectedDrivers: string[];
  onToggleDriver: (driver: string) => void;
}) {
  const [view, setView] = useState<PlaybackMapView>(() => fitPlaybackMapView(points));
  const [drag, setDrag] = useState<PlaybackMapDrag | null>(null);
  const mapLayerRef = useRef<SVGGElement | null>(null);
  const boundsKey = points.map((point) => `${point.display_x}:${point.display_y}`).join("|");

  useEffect(() => {
    setView(fitPlaybackMapView(points));
  }, [boundsKey]);

  const bounds = playbackDisplayBounds(points);
  const centerX = (bounds.minimumX + bounds.maximumX) / 2;
  const centerY = (bounds.minimumY + bounds.maximumY) / 2;
  const transform = `translate(${view.panX} ${view.panY}) translate(50 50) rotate(${view.rotationDeg}) scale(${view.scale}) translate(${-centerX} ${-centerY})`;
  const visualSizeScale = 1 / Math.max(view.scale, 0.75);
  const hitSizeScale = 1 / Math.max(view.scale, 0.55);
  const selectedDriverSet = new Set(selectedDrivers);
  const selectedMarkers = markers.filter((marker) => selectedDriverSet.has(marker.driver));
  const focusedMarker = selectedMarkers.length === 1 ? selectedMarkers[0] : null;
  const focusedMiniSectorStates = focusedMarker?.context.mini_sector_states ?? [];
  const focusedMiniSectorGroups = focusedMarker?.context.mini_sector_groups ?? [];
  const miniSectorTrackSegments = useMemo(
    () => playbackMiniSectorTrackSegments(points, focusedMiniSectorStates, focusedMiniSectorGroups),
    [points, focusedMiniSectorStates, focusedMiniSectorGroups]
  );
  const officialSectorTrackSegments = useMemo(
    () => playbackOfficialSectorTrackSegments(points, selectedMarkers),
    [points, markers, selectedDrivers]
  );
  const renderedMarkers = markers.flatMap((marker, markerIndex) => {
    if (marker.display_x === null || marker.display_x === undefined || marker.display_y === null || marker.display_y === undefined) return [];
    const displayX = marker.display_x;
    const displayY = marker.display_y;
    const selected = selectedDriverSet.has(marker.driver);
    const dimmed = selectedDrivers.length > 0 && !selected;
    const labelOffset = ((markerIndex % 5) - 2) * 3.1 * visualSizeScale;
    const markerOpacity = marker.status === "stale" ? 0.55 : 1;
    const radius = (selected ? 4.2 : 3.2) * visualSizeScale;
    const selectedRingRadius = 5.7 * visualSizeScale;
    const hitRadius = Math.max(8.6 * hitSizeScale, selectedRingRadius + 1.8 * visualSizeScale);
    return [
      {
        marker,
        displayX,
        displayY,
        selected,
        dimmed,
        labelOffset,
        markerOpacity,
        radius,
        selectedRingRadius,
        hitRadius
      }
    ];
  });

  function zoomMap(factor: number) {
    setView((current) => ({
      ...current,
      scale: clampNumber(current.scale * factor, 0.35, 10)
    }));
  }

  function rotateMap(delta: number) {
    setView((current) => ({
      ...current,
      rotationDeg: normalizeRotation(current.rotationDeg + delta)
    }));
  }

  function fitMap() {
    setView((current) => ({
      ...fitPlaybackMapView(points),
      rotationDeg: current.rotationDeg
    }));
  }

  function resetMap() {
    setView(fitPlaybackMapView(points));
  }

  function startPan(event: PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panX: view.panX,
      panY: view.panY,
      moved: false
    });
  }

  function movePan(event: PointerEvent<SVGSVGElement>) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const deltaX = ((event.clientX - drag.startX) / Math.max(rect.width, 1)) * 108;
    const deltaY = ((event.clientY - drag.startY) / Math.max(rect.height, 1)) * 108;
    setDrag({ ...drag, moved: drag.moved || Math.abs(deltaX) > 0.4 || Math.abs(deltaY) > 0.4 });
    setView((current) => ({
      ...current,
      panX: clampNumber(drag.panX + deltaX, -80, 80),
      panY: clampNumber(drag.panY + deltaY, -80, 80)
    }));
  }

  function endPan(event: PointerEvent<SVGSVGElement>) {
    if (drag?.pointerId === event.pointerId) setDrag(null);
  }

  function wheelZoom(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    zoomMap(event.deltaY < 0 ? 1.15 : 0.87);
  }

  function focusNearestMarker(event: MouseEvent<SVGCircleElement>, fallbackDriver: string) {
    event.stopPropagation();
    const svg = event.currentTarget.ownerSVGElement;
    const inverseTransform = mapLayerRef.current?.getScreenCTM()?.inverse();
    if (!svg || !inverseTransform) {
      onToggleDriver(fallbackDriver);
      return;
    }

    const pointer = svg.createSVGPoint();
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    const mapPoint = pointer.matrixTransform(inverseTransform);
    let nearestDriver = fallbackDriver;
    const fallbackMarker = renderedMarkers.find(({ marker }) => marker.driver === fallbackDriver);
    let nearestDistance = fallbackMarker
      ? (mapPoint.x - fallbackMarker.displayX) ** 2 + (mapPoint.y - fallbackMarker.displayY) ** 2
      : Number.POSITIVE_INFINITY;

    for (const { marker, displayX, displayY } of renderedMarkers) {
      const deltaX = mapPoint.x - displayX;
      const deltaY = mapPoint.y - displayY;
      const distance = deltaX * deltaX + deltaY * deltaY;
      if (distance + 1e-6 < nearestDistance) {
        nearestDistance = distance;
        nearestDriver = marker.driver;
      }
    }

    onToggleDriver(nearestDriver);
  }

  return (
    <div className="relative rounded-md border border-line bg-slate-50 p-3">
      <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-1" data-testid="playback-map-controls">
        <Button className="h-8 min-h-8 px-2" icon={<ZoomIn className="h-4 w-4" />} aria-label="Zoom map in" data-testid="playback-map-zoom-in" onClick={() => zoomMap(1.2)} />
        <Button className="h-8 min-h-8 px-2" icon={<ZoomOut className="h-4 w-4" />} aria-label="Zoom map out" data-testid="playback-map-zoom-out" onClick={() => zoomMap(1 / 1.2)} />
        <Button className="h-8 min-h-8 px-2" icon={<RotateCcw className="h-4 w-4" />} aria-label="Rotate map left" data-testid="playback-map-rotate-left" onClick={() => rotateMap(-15)} />
        <Button className="h-8 min-h-8 px-2" icon={<RotateCw className="h-4 w-4" />} aria-label="Rotate map right" data-testid="playback-map-rotate-right" onClick={() => rotateMap(15)} />
        <Button className="h-8 min-h-8 px-2" icon={<Maximize2 className="h-4 w-4" />} aria-label="Fit map" data-testid="playback-map-fit" onClick={fitMap} />
        <Button className="h-8 min-h-8 px-2" icon={<RefreshCw className="h-4 w-4" />} aria-label="Reset map" data-testid="playback-map-reset" onClick={resetMap} />
      </div>
      <svg
        className="h-[min(58vh,480px)] w-full cursor-grab touch-none active:cursor-grabbing xl:h-[calc(100vh-17.5rem)] xl:min-h-[440px] xl:max-h-[640px]"
        data-testid="race-playback-map"
        role="img"
        viewBox="-4 -4 108 108"
        onPointerDown={startPan}
        onPointerMove={movePan}
        onPointerUp={endPan}
        onPointerCancel={endPan}
        onWheel={wheelZoom}
      >
        <g data-testid="playback-map-layer" transform={transform} ref={mapLayerRef}>
          <polyline points={polylinePoints(points)} fill="none" stroke="#94a3b8" strokeWidth={2.5 * visualSizeScale} strokeLinecap="round" strokeLinejoin="round" />
          {miniSectorTrackSegments.map((segment) => (
            <polyline
              key={segment.index}
              points={segment.points}
              fill="none"
              stroke={miniSectorStateColor(segment.state)}
              strokeWidth={3.6 * visualSizeScale}
              strokeLinecap="butt"
              strokeLinejoin="round"
              data-testid={`playback-map-mini-sector-${segment.index}`}
              data-mini-sector-state={segment.state}
              data-mini-sector-group={segment.group}
              data-start-distance={segment.startDistance}
              data-end-distance={segment.endDistance}
              pointerEvents="none"
            />
          ))}
          {officialSectorTrackSegments.map((segment) => (
            <polyline
              key={segment.sector}
              points={segment.points}
              fill="none"
              stroke={segment.color}
              strokeWidth={4.2 * visualSizeScale}
              strokeLinecap="butt"
              strokeLinejoin="round"
              data-testid={`playback-map-sector-${segment.sector}`}
              data-sector={segment.sector}
              data-driver={segment.driver}
              data-sector-time={segment.time}
              data-start-distance={segment.startDistance}
              data-end-distance={segment.endDistance}
              pointerEvents="none"
            />
          ))}
          {renderedMarkers.map(({ marker, displayX, displayY, hitRadius }) => (
            <circle
              key={`${marker.driver}-hitbox`}
              cx={displayX}
              cy={displayY}
              r={hitRadius}
              fill="transparent"
              stroke="none"
              pointerEvents="all"
              data-testid={`playback-marker-hitbox-${marker.driver}`}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => focusNearestMarker(event, marker.driver)}
            />
          ))}
          {renderedMarkers.map(({ marker, displayX, displayY, selected, dimmed, markerOpacity, radius, selectedRingRadius }) => {
            return (
              <g key={marker.driver}>
                <title>{`${marker.driver} ${marker.status}`}</title>
                {selected && (
                  <circle
                    cx={displayX}
                    cy={displayY}
                    r={selectedRingRadius}
                    fill="none"
                    stroke="#0f172a"
                    strokeWidth={1.4 * visualSizeScale}
                    opacity="0.9"
                    pointerEvents="none"
                  />
                )}
                <circle
                  cx={displayX}
                  cy={displayY}
                  r={radius}
                  fill={marker.color ?? "#0f766e"}
                  opacity={dimmed ? 0.32 : markerOpacity}
                  stroke={selected ? "#0f172a" : "#ffffff"}
                  strokeWidth={(selected ? 1.8 : 1.25) * visualSizeScale}
                  data-testid={`playback-marker-${marker.driver}`}
                  pointerEvents="all"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => focusNearestMarker(event, marker.driver)}
                />
              </g>
            );
          })}
          {renderedMarkers.map(({ marker, displayX, displayY, dimmed, labelOffset }) => (
            <g
              key={`${marker.driver}-label`}
              transform={`translate(${displayX} ${displayY}) rotate(${-view.rotationDeg})`}
              data-testid={`playback-label-${marker.driver}`}
              pointerEvents="none"
            >
              <text
                x={3.8 * visualSizeScale}
                y={-3.2 * visualSizeScale + labelOffset}
                className="fill-slate-900 font-semibold"
                fontSize={3.7 * visualSizeScale}
                opacity={dimmed ? 0.45 : 1}
              >
                {marker.driver}
              </text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

function PlaybackTimeline({
  mode,
  payload,
  lapBounds,
  timeBounds,
  timeView,
  lapValue,
  timeValue,
  loading,
  timeAvailable,
  onModeChange,
  onLapChange,
  onTimeChange,
  onZoomIn,
  onZoomOut,
  onFit
}: {
  mode: PlaybackMode;
  payload: PlaybackPayload;
  lapBounds: TrackBounds;
  timeBounds: TrackBounds | null;
  timeView: TrackBounds | null;
  lapValue: number;
  timeValue: number;
  loading: boolean;
  timeAvailable: boolean;
  onModeChange: (mode: PlaybackMode) => void;
  onLapChange: (value: number) => void;
  onTimeChange: (value: number) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
}) {
  const bounds = mode === "lap" ? lapBounds : timeView ?? timeBounds;
  const value = mode === "lap" ? lapValue : timeValue;
  const disabled = bounds === null;
  const minimum = bounds?.minimum ?? 0;
  const maximum = bounds?.maximum ?? minimum;
  const span = Math.max(maximum - minimum, 0);
  const step = mode === "lap" ? 1 : Math.max(span / 600, 0.05);
  const ticks = payload.leader_lap_markers.filter((marker) => {
    const tickValue = mode === "lap" ? marker.lap_number : marker.session_time_seconds;
    return tickValue >= minimum && tickValue <= maximum;
  });
  const tickStride = Math.max(1, Math.ceil(ticks.length / 12));
  const displayTicks = ticks.filter((_, index) => index % tickStride === 0 || index === ticks.length - 1);
  const label = mode === "lap"
    ? `Lap ${Math.round(lapValue)}`
    : formatSessionTime(timeValue);

  return (
    <div className="grid gap-2 rounded-md border border-line bg-slate-50 p-2 xl:h-full xl:min-h-0 xl:grid-rows-[auto_auto_auto_minmax(0,1fr)]" data-testid="race-playback-timeline">
      <div className="flex flex-wrap items-center justify-between gap-1 xl:grid xl:justify-items-center">
        <div className="text-xs font-semibold text-ink">Timeline</div>
        <div className="text-xs font-semibold tabular-nums text-ink">{label}</div>
      </div>
      <div className="flex items-center justify-center gap-1">
        <Button
          className="h-7 min-h-7 px-2 text-[10px]"
          variant={mode === "time" ? "primary" : "secondary"}
          onClick={() => onModeChange("time")}
          disabled={!timeAvailable}
        >
          Time
        </Button>
        <Button className="h-7 min-h-7 px-2 text-[10px]" variant={mode === "lap" ? "primary" : "secondary"} onClick={() => onModeChange("lap")}>Lap</Button>
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" aria-label="Loading playback" />}
      </div>
      <div className="flex justify-center gap-1">
        <Button className="h-7 min-h-7 px-1.5" icon={<ZoomIn className="h-3.5 w-3.5" />} aria-label="Zoom in" onClick={onZoomIn} disabled={mode !== "time" || !timeBounds} />
        <Button className="h-7 min-h-7 px-1.5" icon={<ZoomOut className="h-3.5 w-3.5" />} aria-label="Zoom out" onClick={onZoomOut} disabled={mode !== "time" || !timeBounds} />
        <Button className="h-7 min-h-7 px-1.5" icon={<Maximize2 className="h-3.5 w-3.5" />} aria-label="Fit timeline" onClick={onFit} disabled={mode !== "time" || !timeBounds} />
      </div>
      <div className="relative hidden min-h-0 xl:block" data-testid="race-playback-timeline-vertical">
        <div className="absolute bottom-1 left-1/2 top-1 w-1 -translate-x-1/2 rounded bg-slate-300" />
        {displayTicks.map((marker) => {
          const tickValue = mode === "lap" ? marker.lap_number : marker.session_time_seconds;
          const top = span > 0 ? (1 - ((tickValue - minimum) / span)) * 100 : 100;
          return (
            <div
              key={`${marker.lap_number}-${marker.session_time_seconds}`}
              className="absolute left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center"
              style={{ top: `${top}%` }}
            >
              <div className="h-px w-5 bg-slate-500" />
              <div className="ml-1 whitespace-nowrap text-[9px] font-medium text-muted">L{marker.lap_number}</div>
            </div>
          );
        })}
        <input
          className="absolute bottom-1 left-1/2 top-1 h-[calc(100%-0.5rem)] w-5 -translate-x-1/2 cursor-pointer bg-transparent accent-teal-700"
          data-testid="race-playback-timeline-slider-vertical"
          aria-label="Playback timeline"
          type="range"
          min={minimum}
          max={maximum}
          step={step}
          value={clampNumber(value, minimum, maximum)}
          style={{ writingMode: "vertical-lr", direction: "rtl" }}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (mode === "lap") onLapChange(next);
            else onTimeChange(next);
          }}
          disabled={disabled || span <= 0}
        />
        <span className="absolute left-1 top-0 text-[9px] tabular-nums text-muted">{mode === "lap" ? `L${maximum}` : formatSessionTime(maximum)}</span>
        <span className="absolute bottom-0 left-1 text-[9px] tabular-nums text-muted">{mode === "lap" ? `L${minimum}` : formatSessionTime(minimum)}</span>
      </div>
      <div className="xl:hidden">
        <div className="relative h-12">
          <div className="absolute inset-x-0 top-6 h-1 rounded bg-slate-300" />
          {displayTicks.map((marker) => {
            const tickValue = mode === "lap" ? marker.lap_number : marker.session_time_seconds;
            const left = span > 0 ? ((tickValue - minimum) / span) * 100 : 0;
            return (
              <div
                key={`${marker.lap_number}-${marker.session_time_seconds}`}
                className="absolute top-1 h-9 -translate-x-1/2"
                style={{ left: `${left}%` }}
              >
                <div className="mx-auto h-8 w-px bg-slate-500" />
                <div className="mt-0.5 whitespace-nowrap text-[10px] font-medium text-muted">L{marker.lap_number}</div>
              </div>
            );
          })}
          <input
            className="absolute inset-x-0 top-[18px] h-5 w-full cursor-pointer bg-transparent accent-teal-700"
            data-testid="race-playback-timeline-slider"
            aria-label="Playback timeline"
            type="range"
            min={minimum}
            max={maximum}
            step={step}
            value={clampNumber(value, minimum, maximum)}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (mode === "lap") onLapChange(next);
              else onTimeChange(next);
            }}
            disabled={disabled || span <= 0}
          />
        </div>
        <div className="flex justify-between text-xs tabular-nums text-muted">
          <span>{mode === "lap" ? `L${minimum}` : formatSessionTime(minimum)}</span>
          <span>{mode === "lap" ? `L${maximum}` : formatSessionTime(maximum)}</span>
        </div>
      </div>
    </div>
  );
}

function playbackLapBounds(payload: PlaybackPayload): TrackBounds | null {
  const laps = objectValue(payload.bounds.laps);
  const mode = payload.available_modes.lap;
  const minimum = typeof laps.minimum === "number" ? laps.minimum : typeof mode?.minimum === "number" ? mode.minimum : null;
  const maximum = typeof laps.maximum === "number" ? laps.maximum : typeof mode?.maximum === "number" ? mode.maximum : null;
  if (minimum === null || maximum === null || !Number.isFinite(minimum) || !Number.isFinite(maximum)) return null;
  return { minimum, maximum };
}

function playbackTimeBounds(payload: PlaybackPayload): TrackBounds | null {
  const sessionTime = objectValue(payload.bounds.session_time);
  const mode = payload.available_modes.time;
  const minimum = typeof sessionTime.minimum === "number" ? sessionTime.minimum : typeof mode?.minimum === "number" ? mode.minimum : null;
  const maximum = typeof sessionTime.maximum === "number" ? sessionTime.maximum : typeof mode?.maximum === "number" ? mode.maximum : null;
  if (minimum === null || maximum === null || !Number.isFinite(minimum) || !Number.isFinite(maximum)) return null;
  return { minimum, maximum };
}

function playbackTimeView(bounds: TrackBounds, cursor: number, requestedSpan: number | null): TrackBounds {
  const fullSpan = Math.max(bounds.maximum - bounds.minimum, 0);
  if (fullSpan <= 0) return bounds;
  const span = clampNumber(requestedSpan ?? fullSpan, Math.min(fullSpan, 10), fullSpan);
  const start = clampNumber(cursor - span / 2, bounds.minimum, bounds.maximum - span);
  return { minimum: start, maximum: start + span };
}

function playbackDisplayBounds(points: TrackMapPoint[]) {
  const finitePoints = points.filter((point) => Number.isFinite(point.display_x) && Number.isFinite(point.display_y));
  if (finitePoints.length === 0) {
    return { minimumX: 0, maximumX: 100, minimumY: 0, maximumY: 100 };
  }
  return {
    minimumX: Math.min(...finitePoints.map((point) => point.display_x)),
    maximumX: Math.max(...finitePoints.map((point) => point.display_x)),
    minimumY: Math.min(...finitePoints.map((point) => point.display_y)),
    maximumY: Math.max(...finitePoints.map((point) => point.display_y))
  };
}

function fitPlaybackMapView(points: TrackMapPoint[]): PlaybackMapView {
  const bounds = playbackDisplayBounds(points);
  const width = Math.max(bounds.maximumX - bounds.minimumX, 1);
  const height = Math.max(bounds.maximumY - bounds.minimumY, 1);
  const scale = clampNumber(Math.min(92 / width, 92 / height), 0.35, 10);
  return { scale, panX: 0, panY: 0, rotationDeg: 0 };
}

function normalizeRotation(value: number) {
  const normalized = value % 360;
  return normalized > 180 ? normalized - 360 : normalized < -180 ? normalized + 360 : normalized;
}

function formatSessionTime(value: number) {
  if (!Number.isFinite(value)) return "None";
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes}:${seconds.toFixed(1).padStart(4, "0")}`;
}

function ReviewEditor({
  analysis,
  packageView,
  refreshReview,
  updateObservation,
  pending,
  observationPendingActions
}: {
  analysis: AnalysisView["analysis"] | null;
  packageView: PackageView | null;
  refreshReview: () => void;
  updateObservation: (observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) => Promise<void>;
  pending: boolean;
  observationPendingActions: Record<string, ObservationPendingAction>;
}) {
  const observations = packageView?.observations ?? [];
  return (
    <Panel title="Review" actions={<Button icon={<RefreshCw className="h-4 w-4" />} onClick={refreshReview} disabled={!analysis} loading={pending}>Refresh</Button>}>
      <div className="grid gap-4">
        <dl className="grid gap-3 sm:grid-cols-3">
          <Metric label="State" value={analysis?.review_stale ? "Stale" : "Current"} />
          <Metric label="Charts" value={analysis?.charts.length ?? 0} />
          <Metric label="Observations" value={observations.length} />
        </dl>
        <div className="grid gap-3">
          {observations.length > 0 ? (
            observations.map((observation) => (
              <ObservationCard key={observation.observation_id} observation={observation} updateObservation={updateObservation} pendingAction={observationPendingActions[observation.observation_id] ?? null} />
            ))
          ) : (
            <div className="rounded-md border border-dashed border-line bg-slate-50 p-6 text-sm text-muted">No observations</div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function PresetApplyPanel({
  presets,
  selectedPresetId,
  presetFilter,
  setPresetFilter,
  applyPreset,
  disabled = false
}: {
  presets: ParameterPreset[];
  selectedPresetId: string;
  presetFilter: string;
  setPresetFilter: (value: string) => void;
  applyPreset: (presetId: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-line p-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(180px,240px)]">
        <Field label="Find preset" value={presetFilter} onChange={(event) => setPresetFilter(event.target.value)} />
        <SelectField
          label="Apply preset"
          value={selectedPresetId}
          onValueChange={applyPreset}
          disabled={disabled}
          options={[{ value: noPresetValue, label: "None" }, ...presets.map((preset) => ({ value: preset.preset_id, label: `${preset.display_name} - ${preset.scope}` }))]}
        />
      </div>
      <div className="grid max-h-36 gap-2 overflow-auto">
        {presets.map((preset) => (
          <button
            key={preset.preset_id}
            className={cn(
              "flex items-center justify-between rounded-md border border-line px-3 py-2 text-left text-sm hover:bg-slate-50",
              preset.preset_id === selectedPresetId && "border-brand bg-teal-50 text-brand"
            )}
            type="button"
            onClick={() => applyPreset(preset.preset_id)}
            disabled={disabled}
          >
            <span className="min-w-0 truncate font-medium">{preset.display_name}</span>
            <span className="ml-3 shrink-0 text-xs text-muted">{preset.scope}</span>
          </button>
        ))}
        {presets.length === 0 && <div className="rounded-md border border-dashed border-line p-3 text-sm text-muted">No matching presets</div>}
      </div>
    </div>
  );
}

function PresetManagementPanel({
  chart,
  parameters,
  selectedPreset,
  presetName,
  setPresetName,
  saveGlobal,
  setSaveGlobal,
  savePreset,
  updatePreset,
  deletePreset,
  pendingAction
}: {
  chart: ChartInstance;
  parameters: Record<string, unknown>;
  selectedPreset: ParameterPreset | null;
  presetName: string;
  setPresetName: (value: string) => void;
  saveGlobal: boolean;
  setSaveGlobal: (value: boolean) => void;
  savePreset: (chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting?: boolean) => Promise<void>;
  updatePreset: (presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting?: boolean) => Promise<void>;
  deletePreset: (preset: ParameterPreset) => Promise<void>;
  pendingAction: PresetPendingAction | null;
}) {
  const pending = pendingAction !== null;
  return (
    <div className="grid gap-3 rounded-md border border-line p-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
        <Field label="Preset name" value={presetName} onChange={(event) => setPresetName(event.target.value)} />
        <CheckboxField label="Save globally" checked={saveGlobal} onCheckedChange={setSaveGlobal} />
      </div>
      <div className="grid gap-2 rounded-md border border-line bg-slate-50 p-3 text-sm text-muted">
        <div>Selected: {selectedPreset ? `${selectedPreset.display_name} (${selectedPreset.scope})` : "None"}</div>
        <div>Replace updates an existing preset with the current chart parameters. Delete removes the selected preset and clears it from linked charts.</div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button icon={<Save className="h-4 w-4" />} onClick={() => savePreset(chart, parameters, saveGlobal)} disabled={pending && pendingAction !== "saving"} loading={pendingAction === "saving"}>Save Preset</Button>
        <Button icon={<RefreshCw className="h-4 w-4" />} onClick={() => savePreset(chart, parameters, saveGlobal, true)} disabled={pending && pendingAction !== "replacing"} loading={pendingAction === "replacing"}>Replace</Button>
        <Button icon={<Edit3 className="h-4 w-4" />} onClick={() => selectedPreset && updatePreset(selectedPreset.preset_id, presetName || selectedPreset.display_name)} disabled={!selectedPreset || (pending && pendingAction !== "renaming")} loading={pendingAction === "renaming"}>Rename</Button>
        <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => selectedPreset && deletePreset(selectedPreset)} disabled={!selectedPreset || (pending && pendingAction !== "deleting")} loading={pendingAction === "deleting"}>Delete</Button>
      </div>
    </div>
  );
}

function ObservationCard({
  observation,
  updateObservation,
  pendingAction
}: {
  observation: Observation;
  updateObservation: (observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) => Promise<void>;
  pendingAction: ObservationPendingAction | null;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(observation.edited_text ?? observation.text);
  const pending = pendingAction !== null;

  useEffect(() => {
    setEditing(false);
    setDraft(observation.edited_text ?? observation.text);
  }, [observation.observation_id, observation.edited_text, observation.text]);

  return (
    <div className="grid gap-3 rounded-md border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StatusBadge value={observation.review_status} />
        <div className="flex flex-wrap gap-2">
          {observation.review_status !== "accepted" && (
            <Button icon={<CheckCircle2 className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "accepted")} disabled={pending && pendingAction !== "accepting"} loading={pendingAction === "accepting"}>Accept</Button>
          )}
          {observation.review_status !== "rejected" && (
            <Button icon={<XCircle className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "rejected")} disabled={pending && pendingAction !== "rejecting"} loading={pendingAction === "rejecting"}>Reject</Button>
          )}
          <Button icon={<Edit3 className="h-4 w-4" />} onClick={() => setEditing(true)} disabled={pending}>Edit</Button>
          {observation.review_status !== "unreviewed" && (
            <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "unreviewed", null)} disabled={pending && pendingAction !== "clearing"} loading={pendingAction === "clearing"}>Clear</Button>
          )}
        </div>
      </div>
      {editing ? (
        <div className="grid gap-2">
          <TextAreaField label="Observation" value={draft} onChange={(event) => setDraft(event.target.value)} />
          <div className="flex justify-end gap-2">
            <Button onClick={() => {
              setDraft(observation.edited_text ?? observation.text);
              setEditing(false);
            }}>Cancel</Button>
            <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "edited", draft)} loading={pendingAction === "saving"}>Save</Button>
          </div>
        </div>
      ) : (
        <p className="text-sm leading-6 text-ink">{observation.edited_text ?? observation.text}</p>
      )}
      {observation.evidence_artifact_ids && observation.evidence_artifact_ids.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {observation.evidence_artifact_ids.map((artifactId) => (
            <span key={artifactId} className="rounded border border-line px-2 py-1 text-xs text-muted">{artifactId}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function ExportEditor({
  analysis,
  packageView,
  exportAnalysis,
  openArtifact,
  pending,
  packageLoading
}: {
  analysis: AnalysisView["analysis"] | null;
  packageView: PackageView | null;
  exportAnalysis: () => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
  pending: boolean;
  packageLoading: boolean;
}) {
  return (
    <div className="grid gap-4">
      <Panel title="Export" actions={<Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={exportAnalysis} disabled={!analysis} loading={pending}>Export</Button>}>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Metric label="Sessions" value={analysis?.sessions.length ?? 0} />
          <Metric label="Charts" value={analysis?.charts.length ?? 0} />
          <Metric label="Package" value={analysis?.exported_package_path ? compactPath(analysis.exported_package_path) : "None"} />
        </dl>
      </Panel>
      {packageLoading ? (
        <LoadingBlock label="Loading package" />
      ) : packageView && (
        <Panel title="Export Preview">
          <div className="grid gap-4">
            {packageView.manifest?.artifacts.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {packageView.manifest.artifacts.map((artifact) => (
                  <button key={artifact.artifact_id} className="overflow-hidden rounded-md border border-line bg-slate-50 text-left" onClick={() => openArtifact(artifact, "/api/package/assets")}>
                    <img src={`/api/package/assets/${artifact.image_path}`} alt={artifact.artifact_id} className="aspect-video w-full object-contain" />
                    <div className="border-t border-line p-3 text-sm font-medium text-ink">{artifact.artifact_id}</div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-line bg-slate-50 p-6 text-sm text-muted">No charts</div>
            )}
            <dl className="grid gap-3 sm:grid-cols-3">
              <Metric label="Health" value={packageView.health.status} />
              <Metric label="Observations" value={packageView.observations.length} />
              <Metric label="Draft" value={packageView.draft_markdown ? "Ready" : "None"} />
            </dl>
          </div>
        </Panel>
      )}
    </div>
  );
}

function ParameterControl({
  field,
  value,
  drivers,
  teams,
  state,
  fieldAction,
  setValue
}: {
  field: ParameterField;
  value: unknown;
  drivers: string[];
  teams: string[];
  state: ParameterFieldState;
  fieldAction?: ReactNode;
  setValue: (value: unknown) => void;
}) {
  const [driverFilter, setDriverFilter] = useState("");
  const [colorFilter, setColorFilter] = useState("");
  const label = state.required ? `${field.label} *` : field.label;
  const feedback = state.error ?? state.warning;
  if (field.field_type === "checkbox") {
    return <CheckboxField label={label} checked={Boolean(value ?? field.default)} disabled={state.disabled} description={feedback} onCheckedChange={setValue} />;
  }
  if (field.field_type === "select" && field.options.length > 0) {
    return <SelectField label={label} value={String(value ?? field.default ?? field.options[0])} disabled={state.disabled} error={state.error} description={state.warning} onValueChange={setValue} options={field.options.map((option) => ({ value: option, label: option }))} />;
  }
  if (field.field_type === "multi_select") {
    const selected = Array.isArray(value) ? value.map(String) : Array.isArray(field.default) ? field.default.map(String) : [];
    return (
      <div className="grid gap-2">
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {field.options.map((option) => (
            <CheckboxField
              key={option}
              label={option}
              checked={selected.includes(option)}
              disabled={state.disabled}
              onCheckedChange={(checked) => {
                const next = checked ? [...selected, option] : selected.filter((item) => item !== option);
                setValue(next);
              }}
            />
          ))}
        </div>
        {feedback && <div className={cn("text-xs font-medium", state.error ? "text-danger" : "text-amber-700")}>{feedback}</div>}
      </div>
    );
  }
  if (field.field_type === "driver_selector") {
    if (field.name === "reference_driver") {
      return (
        <SelectField
          label={label}
          value={String(value ?? "__none__")}
          disabled={state.disabled}
          error={state.error}
          description={state.warning}
          onValueChange={(next) => setValue(next === "__none__" ? null : next)}
          options={[{ value: "__none__", label: "None" }, ...drivers.map((driver) => ({ value: driver, label: driver }))]}
        />
      );
    }
    const selected = Array.isArray(value) ? value.map(String) : [];
    const options = field.name === "teams" ? teams : drivers;
    const visibleDrivers = options.filter((driver) => driver.toLowerCase().includes(driverFilter.toLowerCase()));
    const itemLabel = field.name === "teams" ? "team" : "driver";
    return (
      <div className="grid gap-2">
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-slate-50 px-3 py-2 text-sm text-muted">
          <span>{selected.length === options.length ? `All ${options.length}` : selected.length === 0 ? "None selected" : `${selected.length} selected`}</span>
          <div className="flex items-center gap-3">
            <button className="font-medium text-brand disabled:text-muted" type="button" disabled={state.disabled} onClick={() => setValue(options)}>All</button>
            <button className="font-medium text-brand disabled:text-muted" type="button" disabled={state.disabled} onClick={() => setValue([])}>Clear</button>
          </div>
        </div>
        {options.length > 8 && <Field label={`Find ${itemLabel}`} value={driverFilter} disabled={state.disabled} onChange={(event) => setDriverFilter(event.target.value)} />}
        <div className="grid max-h-56 gap-2 overflow-auto rounded-md border border-line p-2 sm:grid-cols-2">
          {visibleDrivers.map((driver) => (
            <CheckboxField
              key={driver}
              label={driver}
              checked={selected.includes(driver)}
              disabled={state.disabled}
              onCheckedChange={(checked) => {
                const next = checked ? [...selected.filter((item) => item !== driver), driver] : selected.filter((item) => item !== driver);
                setValue(next);
              }}
            />
          ))}
        </div>
        {feedback && <div className={cn("text-xs font-medium", state.error ? "text-danger" : "text-amber-700")}>{feedback}</div>}
      </div>
    );
  }
  if (field.field_type === "lap_range" || field.field_type === "numeric_range") {
    const range = isRange(value) ? value : {};
    const minimum = state.minimum ?? field.minimum ?? undefined;
    const maximum = state.maximum ?? field.maximum ?? undefined;
    const rangeDescription = feedback ?? state.boundsLabel;
    return (
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-medium text-ink">{label}</div>
          {fieldAction}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Start" type="number" min={minimum} max={maximum} value={range.start ?? ""} disabled={state.disabled} onChange={(event) => setValue({ ...range, start: numberOrNull(event.target.value) })} />
          <Field label="End" type="number" min={minimum} max={maximum} value={range.end ?? ""} disabled={state.disabled} onChange={(event) => setValue({ ...range, end: numberOrNull(event.target.value) })} />
        </div>
        {rangeDescription && <div className={cn("text-xs font-medium", state.error ? "text-danger" : state.warning ? "text-amber-700" : "text-muted")}>{rangeDescription}</div>}
      </div>
    );
  }
  if (field.field_type === "color_map") {
    const colors = isStringMap(value) ? value : {};
    const labels = drivers.length > 0 ? drivers : Object.keys(colors);
    const visibleLabels = labels.filter((item) => item.toLowerCase().includes(colorFilter.toLowerCase()) || colors[item]);
    return (
      <div className="grid gap-2">
        <div className="text-sm font-medium text-ink">{label}</div>
        {labels.length > 8 && <Field label="Find series" value={colorFilter} disabled={state.disabled} onChange={(event) => setColorFilter(event.target.value)} />}
        <div className="max-h-64 overflow-auto rounded-md border border-line">
          <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
            <thead>
              <tr>
                <th className="sticky top-0 border-b border-line bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-normal text-muted">Series</th>
                <th className="sticky top-0 border-b border-line bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-normal text-muted">Override</th>
                <th className="sticky top-0 border-b border-line bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-normal text-muted">Clear</th>
              </tr>
            </thead>
            <tbody>
              {visibleLabels.map((item) => (
                <tr key={item}>
                  <td className="border-b border-line px-3 py-2 font-medium text-ink">{item}</td>
                  <td className="border-b border-line px-3 py-2">
                    <input
                      className="h-8 w-12 rounded border border-line bg-panel"
                      type="color"
                      value={colors[item] ?? "#0f766e"}
                      disabled={state.disabled}
                      onChange={(event) => setValue({ ...colors, [item]: event.target.value })}
                    />
                  </td>
                  <td className="border-b border-line px-3 py-2">
                    <button
                      className="text-sm font-medium text-brand disabled:text-muted"
                      type="button"
                      disabled={state.disabled || !(item in colors)}
                      onClick={() => {
                        const next = { ...colors };
                        delete next[item];
                        setValue(next);
                      }}
                    >
                      Clear
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {feedback && <div className={cn("text-xs font-medium", state.error ? "text-danger" : "text-amber-700")}>{feedback}</div>}
      </div>
    );
  }
  if (field.field_type === "number") {
    return <Field label={label} type="number" min={state.minimum ?? field.minimum ?? undefined} max={state.maximum ?? field.maximum ?? undefined} value={String(value ?? field.default ?? "")} disabled={state.disabled} error={state.error} description={state.warning ?? state.boundsLabel} onChange={(event) => setValue(numberOrNull(event.target.value))} />;
  }
  if (field.field_type === "object") {
    return <Field label={label} value="Structured controls only" disabled description={feedback} />;
  }
  if (field.field_type === "color") {
    return <Field label={label} type="color" value={String(value ?? field.default ?? "#0f766e")} disabled={state.disabled} error={state.error} description={state.warning} onChange={(event) => setValue(event.target.value)} />;
  }
  return <Field label={label} value={String(value ?? field.default ?? "")} disabled={state.disabled} error={state.error} description={state.warning} onChange={(event) => setValue(event.target.value)} />;
}

function OutlineButton({
  active,
  label,
  onClick,
  status,
  icon,
  disabled,
  collapsed
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  status?: string;
  icon: ReactNode;
  disabled?: boolean;
  collapsed: boolean;
}) {
  return (
    <button
      className={cn(
        "flex min-h-9 w-full min-w-0 items-center justify-between gap-2 rounded-md px-2 text-left text-sm text-muted hover:bg-slate-100 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50",
        collapsed && "justify-center px-0",
        active && "bg-teal-50 text-brand"
      )}
      onClick={onClick}
      disabled={disabled}
      title={label}
    >
      <span className={cn("flex min-w-0 items-center gap-2", collapsed && "justify-center")}>
        <span className="shrink-0">{icon}</span>
        {!collapsed && <span className="truncate">{label}</span>}
      </span>
      {!collapsed && status && <span className="shrink-0 rounded border border-line px-1.5 py-0.5 text-[11px]">{status}</span>}
    </button>
  );
}

function GroupLabel({
  label,
  count,
  open,
  onToggle,
  collapsed
}: {
  label: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  collapsed: boolean;
}) {
  return (
    <button
      className={cn(
        "flex min-h-8 w-full min-w-0 items-center justify-between rounded-md px-2 py-1 text-xs font-semibold uppercase tracking-normal text-muted hover:bg-slate-100 hover:text-ink",
        collapsed && "justify-center px-0"
      )}
      onClick={onToggle}
      title={label}
    >
      <span className={cn("flex min-w-0 items-center gap-2", collapsed && "justify-center")}>
        <span className="shrink-0">{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</span>
        {!collapsed && <span>{label}</span>}
      </span>
      {!collapsed && <span className="shrink-0">{count}</span>}
    </button>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-slate-50 p-3">
      <dt className="text-xs font-semibold uppercase tracking-normal text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-ink">{value}</dd>
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-28 items-center justify-center rounded-md border border-line bg-slate-50 text-sm font-medium text-muted">
      <span className="inline-flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        {label}
      </span>
    </div>
  );
}

function ErrorList({ errors }: { errors: string[] }) {
  return (
    <div className="grid gap-2">
      {errors.map((error) => (
        <div key={error} className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-950">
          {error}
        </div>
      ))}
    </div>
  );
}

function WarningList({ warnings }: { warnings: string[] }) {
  return (
    <div className="grid gap-2">
      {warnings.map((warning) => (
        <div key={warning} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          {warning}
        </div>
      ))}
    </div>
  );
}

function ParameterSections({
  fields,
  allFields,
  parameters,
  diagnostics,
  drivers,
  teams,
  renderFieldAction,
  setParameter
}: {
  fields: ParameterField[];
  allFields: ParameterField[];
  parameters: Record<string, unknown>;
  diagnostics: ParameterDiagnostics | null;
  drivers: string[];
  teams: string[];
  renderFieldAction?: (field: ParameterField) => ReactNode;
  setParameter: (field: ParameterField, value: unknown) => void;
}) {
  const groups = groupedFields(fields);
  return (
    <div className="grid gap-4">
      {groups.map(([group, groupFields]) => (
        <section key={group} className="grid gap-3">
          <div className="text-xs font-semibold uppercase tracking-normal text-muted">{group}</div>
          <div className="grid gap-3 md:grid-cols-2">
            {groupFields.map((field) => {
              const state = parameterFieldState(field, allFields, parameters, diagnostics);
              return (
                <ParameterControl
                  key={field.name}
                  field={field}
                  value={parameterValue(parameters, field.name, field.default)}
                  drivers={drivers}
                  teams={teams}
                  state={state}
                  fieldAction={renderFieldAction?.(field) ?? undefined}
                  setValue={(value) => setParameter(field, value)}
                />
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

type TrackBounds = {
  minimum: number;
  maximum: number;
};

function trackSegmentParameters(
  current: Record<string, unknown>,
  startDistance: number,
  endDistance: number,
  payload: TrackMapPayload,
  cornerSelection?: TrackCornerSelection | null
) {
  const start = Math.min(startDistance, endDistance);
  const end = Math.max(startDistance, endDistance);
  const analysis = objectValue(current.analysis);
  const selection = objectValue(current.selection);
  const cornerMetadata = cornerSelection
    ? {
        label: cornerSelection.corner.label,
        number: cornerSelection.corner.number,
        letter: cornerSelection.corner.letter ?? null,
        distance_m: cornerSelection.corner.distance_m ?? null,
        pre_padding_m: cornerSelection.prePaddingM,
        post_padding_m: cornerSelection.postPaddingM,
        projection_status: cornerSelection.corner.projection_status,
        projection_error: cornerSelection.corner.projection_error ?? null,
        display_x: cornerSelection.corner.display_x ?? null,
        display_y: cornerSelection.corner.display_y ?? null
      }
    : null;
  const next: Record<string, unknown> = {
    ...current,
    analysis: {
      ...analysis,
      distance_range_m: { start, end }
    },
    selection: {
      ...selection,
      track_segment: {
        source: cornerMetadata ? "corner_selector" : "manual_track_selector",
        start_distance_m: start,
        end_distance_m: end,
        source_driver: payload.source_driver ?? null,
        source_lap: payload.source_lap ?? null,
        point_count: payload.point_count,
        original_sample_count: payload.original_sample_count,
        downsampled: payload.downsampled,
        start_marker: markerAtDistance(payload.points, start),
        end_marker: markerAtDistance(payload.points, end),
        corner: cornerMetadata
      }
    }
  };
  delete next.distance_range_m;
  return next;
}

function trackMapDistanceBounds(payload: TrackMapPayload): TrackBounds | null {
  const distance = objectValue(payload.bounds.distance_m);
  const minimum = typeof distance.minimum === "number" ? distance.minimum : null;
  const maximum = typeof distance.maximum === "number" ? distance.maximum : null;
  if (minimum !== null && maximum !== null && Number.isFinite(minimum) && Number.isFinite(maximum) && maximum >= minimum) {
    return { minimum, maximum };
  }
  const distances = payload.points.map((point) => point.distance_m).filter(Number.isFinite);
  if (distances.length === 0) return null;
  return { minimum: Math.min(...distances), maximum: Math.max(...distances) };
}

function clampDistance(distance: number, bounds: TrackBounds) {
  if (!Number.isFinite(distance)) return bounds.minimum;
  return Math.min(Math.max(distance, bounds.minimum), bounds.maximum);
}

function polylinePoints(points: TrackMapPoint[]) {
  return points.map((point) => `${point.display_x},${point.display_y}`).join(" ");
}

function segmentPolylinePoints(points: TrackMapPoint[], startDistance: number, endDistance: number) {
  const start = Math.min(startDistance, endDistance);
  const end = Math.max(startDistance, endDistance);
  const segment = [
    markerAtDistance(points, start),
    ...points
      .filter((point) => point.distance_m > start && point.distance_m < end)
      .sort((left, right) => left.distance_m - right.distance_m),
    markerAtDistance(points, end)
  ];
  return segment.map((point) => `${point.display_x},${point.display_y}`).join(" ");
}

type MiniSectorState = PlaybackMarker["context"]["mini_sector_states"][number];

function playbackMiniSectorTrackSegments(
  points: TrackMapPoint[],
  states: PlaybackMarker["context"]["mini_sector_states"],
  groups: PlaybackMarker["context"]["mini_sector_groups"]
) {
  if (points.length < 2 || states.length === 0) return [];
  const ordered = [...points].sort((left, right) => left.distance_m - right.distance_m);
  const minimum = 0;
  const maximum = ordered[ordered.length - 1].distance_m;
  const segmentLength = (maximum - minimum) / states.length;
  if (!Number.isFinite(segmentLength) || segmentLength <= 0) return [];
  return states.map((state, index) => {
    const startDistance = minimum + index * segmentLength;
    const endDistance = index === states.length - 1 ? maximum : minimum + (index + 1) * segmentLength;
    return {
      index,
      state,
      group: groups[index] ?? 0,
      startDistance,
      endDistance,
      points: segmentPolylinePoints(ordered, startDistance, endDistance)
    };
  });
}

function playbackOfficialSectorTrackSegments(points: TrackMapPoint[], selectedMarkers: PlaybackMarker[]) {
  if (points.length < 2 || selectedMarkers.length < 2) return [];
  const ordered = [...points].sort((left, right) => left.distance_m - right.distance_m);
  const trackLength = ordered[ordered.length - 1].distance_m;
  if (!Number.isFinite(trackLength) || trackLength <= 0) return [];
  const inferredGroups = selectedMarkers.find((marker) => marker.context.mini_sector_groups.some((group) => group > 0))?.context.mini_sector_groups ?? [];
  const boundaries = [0, 1, 2, 3].map((boundaryIndex) => {
    if (boundaryIndex === 0) return 0;
    if (boundaryIndex === 3) return trackLength;
    if (inferredGroups.length === 0) return trackLength * (boundaryIndex / 3);
    const completedSegments = inferredGroups.filter((group) => group > 0 && group <= boundaryIndex).length;
    return trackLength * (completedSegments / inferredGroups.length);
  });
  return [0, 1, 2].flatMap((sectorIndex) => {
    const winner = selectedMarkers
      .map((marker) => ({ marker, time: marker.context.last_sector_times_seconds[sectorIndex] }))
      .filter((candidate): candidate is { marker: PlaybackMarker; time: number } => candidate.time !== null && candidate.time !== undefined && Number.isFinite(candidate.time))
      .sort((left, right) => left.time - right.time)[0];
    if (!winner) return [];
    const startDistance = boundaries[sectorIndex];
    const endDistance = boundaries[sectorIndex + 1];
    return [{
      sector: sectorIndex + 1,
      driver: winner.marker.driver,
      time: winner.time,
      color: winner.marker.color ?? "#0f766e",
      startDistance,
      endDistance,
      points: segmentPolylinePoints(ordered, startDistance, endDistance)
    }];
  });
}

function miniSectorStateColor(state: MiniSectorState) {
  if (state === "fastest") return TIMING_PERFORMANCE_COLORS.fastest;
  if (state === "faster") return TIMING_PERFORMANCE_COLORS.personalBest;
  if (state === "slower") return TIMING_PERFORMANCE_COLORS.slower;
  return "#cbd5e1";
}

function markerAtDistance(points: TrackMapPoint[], distance: number) {
  const ordered = [...points].sort((left, right) => left.distance_m - right.distance_m);
  if (ordered.length === 0) {
    return { distance_m: distance, display_x: 50, display_y: 50 };
  }
  if (distance <= ordered[0].distance_m) {
    return {
      distance_m: distance,
      display_x: ordered[0].display_x,
      display_y: ordered[0].display_y
    };
  }
  const last = ordered[ordered.length - 1];
  if (distance >= last.distance_m) {
    return {
      distance_m: distance,
      display_x: last.display_x,
      display_y: last.display_y
    };
  }
  for (let index = 0; index < ordered.length - 1; index += 1) {
    const left = ordered[index];
    const right = ordered[index + 1];
    if (left.distance_m <= distance && distance <= right.distance_m) {
      const span = right.distance_m - left.distance_m;
      const ratio = span === 0 ? 0 : (distance - left.distance_m) / span;
      return {
        distance_m: distance,
        display_x: left.display_x + (right.display_x - left.display_x) * ratio,
        display_y: left.display_y + (right.display_y - left.display_y) * ratio
      };
    }
  }
  return {
    distance_m: distance,
    display_x: last.display_x,
    display_y: last.display_y
  };
}

function nearestPointDistance(points: TrackMapPoint[], x: number, y: number) {
  let nearest = points[0];
  let best = Number.POSITIVE_INFINITY;
  for (const point of points) {
    const distance = Math.hypot(point.display_x - x, point.display_y - y);
    if (distance < best) {
      best = distance;
      nearest = point;
    }
  }
  return nearest.distance_m;
}

function visibleSchemaFields(fields: ParameterField[], parameters: Record<string, unknown>, mode: "basic" | "advanced") {
  return fields
    .filter((field) => mode === "advanced" || field.mode !== "advanced")
    .filter((field) => dependenciesMatch(field.visible_when, fields, parameters));
}

function groupedFields(fields: ParameterField[]) {
  const groups = new Map<string, ParameterField[]>();
  for (const field of fields) {
    const group = field.group ?? "Parameters";
    groups.set(group, [...(groups.get(group) ?? []), field]);
  }
  return Array.from(groups.entries()).map(([group, groupFields]) => [
    group,
    groupFields.sort((left, right) => left.order - right.order)
  ] as const);
}

type ParameterFieldState = {
  disabled: boolean;
  required: boolean;
  error?: string;
  warning?: string;
  minimum?: number | null;
  maximum?: number | null;
  boundsLabel?: string;
};

function parameterFieldState(
  field: ParameterField,
  fields: ParameterField[],
  parameters: Record<string, unknown>,
  diagnostics: ParameterDiagnostics | null
): ParameterFieldState {
  const enabled = !field.enabled_when || Object.keys(field.enabled_when).length === 0 || dependenciesMatch(field.enabled_when, fields, parameters);
  const required = field.required || (Object.keys(field.required_when ?? {}).length > 0 && dependenciesMatch(field.required_when, fields, parameters));
  const error = diagnostics?.errors.find((item) => item.field === field.name)?.message;
  const warning = diagnostics?.warnings.find((item) => item.field === field.name)?.message;
  const bounds = rangeBounds(field, diagnostics);
  return { disabled: !enabled, required, error, warning, ...bounds };
}

function rangeBounds(field: ParameterField, diagnostics: ParameterDiagnostics | null) {
  const coverage = objectValue(diagnostics?.coverage_bounds);
  const source = field.name === "lap_range" || field.name === "lap_number"
    ? objectValue(coverage.laps)
    : field.name === "distance_range_m"
      ? objectValue(coverage.telemetry_distance_m)
      : {};
  if (source.available !== true) {
    return {};
  }
  const minimum = typeof source.minimum === "number" ? source.minimum : null;
  const maximum = typeof source.maximum === "number" ? source.maximum : null;
  const unit = field.name === "distance_range_m" ? " m" : "";
  return {
    minimum,
    maximum,
    boundsLabel: minimum !== null && maximum !== null ? `Loaded range ${minimum}-${maximum}${unit}` : undefined
  };
}

function dependenciesMatch(dependencies: Record<string, unknown>, fields: ParameterField[], parameters: Record<string, unknown>) {
  return Object.entries(dependencies ?? {}).every(([name, expected]) => {
    const field = fields.find((item) => item.name === name);
    const actual = parameterValue(parameters, name, field?.default);
    return Array.isArray(expected) ? expected.includes(actual) : actual === expected;
  });
}

function parameterValue(parameters: Record<string, unknown>, name: string, fallback: unknown) {
  if (name in parameters) return parameters[name];
  const chart = objectValue(parameters.chart);
  const selection = objectValue(parameters.selection);
  const filters = objectValue(parameters.filters);
  const analysis = objectValue(parameters.analysis);
  const presentation = objectValue(parameters.presentation);
  if (name === "title") return chart.title ?? fallback;
  if (name === "lap_range") {
    const laps = objectValue(selection.laps);
    return laps.range ?? fallback;
  }
  if (name === "lap_number") {
    const laps = objectValue(selection.laps);
    const range = objectValue(laps.range);
    const start = range.start;
    const end = range.end;
    if (typeof start === "number" && start === end) return start;
    return typeof start === "number" ? start : fallback;
  }
  if (name === "series_colors") {
    const colors = objectValue(presentation.colors);
    return colors.overrides ?? fallback;
  }
  return selection[name] ?? filters[name] ?? analysis[name] ?? presentation[name] ?? fallback;
}

function parametersWithFieldValue(parameters: Record<string, unknown>, name: string, value: unknown) {
  const next = { ...parameters, [name]: value };
  if (name === "lap_number") {
    delete next.lap_range;
    const selection = objectValue(next.selection);
    if (typeof value === "number" && Number.isFinite(value)) {
      selection.laps = { range: { start: value, end: value } };
    } else {
      const laps = objectValue(selection.laps);
      delete laps.range;
      selection.laps = laps;
    }
    next.selection = selection;
  }
  if (name === "lap_range") {
    delete next.lap_number;
    const selection = objectValue(next.selection);
    selection.laps = { ...objectValue(selection.laps), range: value };
    next.selection = selection;
  }
  return next;
}

function resetParametersByGroup(fields: ParameterField[], parameters: Record<string, unknown>, group: string) {
  const next = { ...parameters };
  for (const field of fields) {
    if (field.reset_group === group) {
      if (field.default === undefined || field.default === null) {
        delete next[field.name];
      } else {
        next[field.name] = field.default;
      }
    }
  }
  delete next[group];
  return next;
}

function clearCustomOverrides(parameters: Record<string, unknown>) {
  const next = { ...parameters };
  delete next.series_colors;
  const presentation = objectValue(next.presentation);
  if ("colors" in presentation) {
    const colors = objectValue(presentation.colors);
    delete colors.overrides;
    presentation.colors = colors;
    next.presentation = presentation;
  }
  return next;
}

function filterPresets(presets: ParameterPreset[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return presets;
  return presets.filter((preset) =>
    `${preset.display_name} ${preset.scope} ${preset.preset_id}`.toLowerCase().includes(normalized)
  );
}

function objectValue(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? { ...(value as Record<string, unknown>) } : {};
}

function numericValue(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clampNumber(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

function splitDrivers(value: string) {
  const drivers = value
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  if (drivers.some((driver) => driver === "ALL" || driver === "*")) {
    return ["*"];
  }
  return drivers;
}

function defaultParameters(fields: ParameterField[]) {
  return Object.fromEntries(fields.filter((field) => field.default !== undefined && field.default !== null).map((field) => [field.name, field.default]));
}

function numberOrNull(value: string) {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isRange(value: unknown): value is { start?: number | null; end?: number | null } {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringMap(value: unknown): value is Record<string, string> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sameJson(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
