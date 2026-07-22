import { useEffect, useMemo, useState, type ReactNode } from "react";
import { BarChart3, CheckCircle2, ChevronDown, ChevronRight, ClipboardCheck, Download, Edit3, FilePlus2, FolderOpen, Image, LineChart, Play, Plus, RefreshCw, RotateCcw, Save, Trash2, XCircle } from "lucide-react";
import * as api from "../api";
import type { AnalysisSession, AnalysisView, Artifact, ChartInstance, Observation, PackageView, ParameterField, ParameterPreset, ReviewStatus } from "../types";
import { compactPath, cn } from "../lib/utils";
import type { SidebarRenderer } from "../components/AppShell";
import { Button } from "../components/ui/Button";
import { CheckboxField } from "../components/ui/CheckboxField";
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
  drivers: "VER, PER",
  dataSource: "local" as "fastf1" | "local",
  localDatasetPath: "tests/fixtures/2023_bahrain_race_dataset.json",
  cacheDirectory: ".cache/fastf1",
  cacheMode: "cache-or-fetch" as "cache-or-fetch" | "cache-only"
};

const noPresetValue = "__none__";

export function AnalysisWorkbenchPage({ notify, openArtifact, refreshHistory, setSidebarContent }: AnalysisWorkbenchPageProps) {
  const [view, setView] = useState<AnalysisView | null>(null);
  const [exportedPackage, setExportedPackage] = useState<PackageView | null>(null);
  const [selection, setSelection] = useState<AnalysisSelection>({ kind: "overview" });
  const [sessionsOpen, setSessionsOpen] = useState(true);
  const [chartsOpen, setChartsOpen] = useState(true);
  const [analysisPath, setAnalysisPath] = useState("analyses/race-analysis");
  const [analysisName, setAnalysisName] = useState("Race Analysis");
  const [sessionDraft, setSessionDraft] = useState(defaultSession);
  const [chartDraft, setChartDraft] = useState({
    recipeId: "lap_time_delta",
    sessionId: "",
    name: "Lap time delta",
    title: "Lap time delta",
    presetId: noPresetValue,
    presetName: "Lap time delta",
    saveGlobal: false
  });

  useEffect(() => {
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
      .catch(() => undefined);
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
    try {
      const payload = await api.createAnalysis(analysisPath, analysisName);
      setView(payload);
      setSelection({ kind: "overview" });
      notify("Analysis created", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Create failed", message(error), "error");
    }
  }

  async function openAnalysis() {
    try {
      const payload = await api.openAnalysis(analysisPath);
      setView(payload);
      setAnalysisName(payload.analysis.name);
      if (payload.analysis.exported_package_path) {
        await loadExportedPackage(payload.analysis.exported_package_path);
      } else {
        setExportedPackage(null);
      }
      setSelection({ kind: "overview" });
      notify("Analysis opened", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Open failed", message(error), "error");
    }
  }

  async function saveAnalysis() {
    try {
      const payload = await api.saveAnalysis();
      setView(payload);
      notify("Analysis saved", compactPath(payload.analysis.root_path), "success");
    } catch (error) {
      notify("Save failed", message(error), "error");
    }
  }

  async function addSession() {
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
    }
  }

  async function removeSession(session: AnalysisSession) {
    const dependents = analysis?.charts.filter((chart) => chart.target_session_ids.includes(session.session_id)) ?? [];
    const confirmed = dependents.length === 0 || window.confirm(`Remove ${session.name} and ${dependents.length} dependent chart(s)?`);
    if (!confirmed) return;
    try {
      const payload = await api.removeAnalysisSession(session.session_id, dependents.length > 0);
      setView(payload);
      setSelection({ kind: "overview" });
      notify("Session removed", session.name, "success");
    } catch (error) {
      notify("Remove failed", message(error), "error");
    }
  }

  async function loadSession(session: AnalysisSession) {
    try {
      const payload = await api.loadAnalysisSession(session.session_id);
      setView(payload);
      notify("Session loaded", session.name, "success");
    } catch (error) {
      notify("Load failed", message(error), "error");
    }
  }

  async function addChart() {
    const sessionId = chartDraft.sessionId || analysis?.sessions[0]?.session_id || "";
    if (!sessionId) {
      notify("Chart blocked", "Select a session", "warning");
      return;
    }
    const preset = presets.find((item) => item.preset_id === chartDraft.presetId && item.recipe_id === chartDraft.recipeId) ?? null;
    try {
      const payload = await api.addAnalysisChart({
        recipe_id: chartDraft.recipeId,
        target_session_ids: [sessionId],
        name: chartDraft.name,
        parameters: preset?.parameters ?? { title: chartDraft.title || chartDraft.name },
        preset_id: preset?.preset_id ?? null
      });
      setView(payload);
      const latest = payload.analysis.charts[payload.analysis.charts.length - 1];
      if (latest) setSelection({ kind: "chart", id: latest.chart_instance_id });
      notify("Chart added", latest?.name, "success");
    } catch (error) {
      notify("Chart failed", message(error), "error");
    }
  }

  async function updateChart(chart: ChartInstance, parameters: Record<string, unknown>, presetId?: string | null) {
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
    }
  }

  async function generateChart(chart: ChartInstance) {
    try {
      const payload = await api.generateAnalysisCharts([chart.chart_instance_id]);
      setView(payload);
      notify("Chart generated", chart.name, "success");
    } catch (error) {
      notify("Generate failed", message(error), "error");
    }
  }

  async function removeChart(chart: ChartInstance) {
    if (chart.generation_state === "generated" && !window.confirm(`Remove ${chart.name}?`)) return;
    try {
      const payload = await api.removeAnalysisChart(chart.chart_instance_id);
      setView(payload);
      setSelection({ kind: "overview" });
      notify("Chart removed", chart.name, "success");
    } catch (error) {
      notify("Remove failed", message(error), "error");
    }
  }

  async function savePreset(chart: ChartInstance, global: boolean) {
    try {
      const payload = await api.saveAnalysisPreset({
        recipe_id: chart.recipe_id,
        display_name: chartDraft.presetName || chart.name,
        parameters: chart.parameters,
        scope: global ? "global" : "analysis"
      });
      setView(payload);
      notify("Preset saved", global ? "Global" : "Analysis", "success");
    } catch (error) {
      notify("Preset failed", message(error), "error");
    }
  }

  async function refreshReview() {
    try {
      const payload = await api.refreshAnalysisReview();
      setView(payload);
      await loadExportedPackage(payload.analysis.exported_package_path);
      notify("Review refreshed", payload.analysis.exported_package_path ?? undefined, "success");
    } catch (error) {
      notify("Refresh failed", message(error), "error");
    }
  }

  async function exportAnalysis() {
    try {
      const payload = await api.exportAnalysis();
      setView(payload);
      await refreshHistory();
      await loadExportedPackage(payload.analysis.exported_package_path);
      notify("Package exported", payload.analysis.exported_package_path ?? undefined, "success");
    } catch (error) {
      notify("Export failed", message(error), "error");
    }
  }

  async function loadExportedPackage(path?: string | null) {
    if (!path) {
      setExportedPackage(null);
      return;
    }
    try {
      setExportedPackage(await api.openPackage(path));
    } catch {
      setExportedPackage(null);
    }
  }

  async function updateObservation(observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) {
    try {
      await api.updateObservationReview(observationId, reviewStatus, editedText);
      const packageView = await api.regenerateDraft();
      setExportedPackage(packageView);
      notify("Observation saved", reviewStatus, "success");
    } catch (error) {
      notify("Review failed", message(error), "error");
    }
  }

  return (
    <div className="grid gap-4">
      <div className="rounded-lg border border-line bg-panel p-4">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto]">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(180px,260px)]">
            <Field label="Analysis directory" value={analysisPath} onChange={(event) => setAnalysisPath(event.target.value)} />
            <Field label="Name" value={analysisName} onChange={(event) => setAnalysisName(event.target.value)} />
          </div>
          <div className="flex flex-wrap items-end gap-2 xl:justify-end">
            <Button icon={<FilePlus2 className="h-4 w-4" />} onClick={createAnalysis}>
              New
            </Button>
            <Button icon={<FolderOpen className="h-4 w-4" />} onClick={openAnalysis}>
              Open
            </Button>
            <Button icon={<Save className="h-4 w-4" />} onClick={saveAnalysis} disabled={!analysis}>
              Save
            </Button>
            <Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={exportAnalysis} disabled={!analysis || generatedCharts.length === 0}>
              Export
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        {selection.kind === "overview" && <Overview analysis={analysis} staleCharts={staleCharts.length} />}
        {selection.kind === "new-session" && (
          <SessionDraftEditor draft={sessionDraft} setDraft={setSessionDraft} addSession={addSession} disabled={!analysis} />
        )}
        {selectedSession && <SessionEditor session={selectedSession} loadSession={loadSession} removeSession={removeSession} />}
        {selection.kind === "new-chart" && analysis && view && (
          <ChartDraftEditor
            draft={chartDraft}
            setDraft={setChartDraft}
            sessions={analysis.sessions}
            recipes={view.recipes}
            presets={presets.filter((preset) => preset.recipe_id === chartDraft.recipeId)}
            addChart={addChart}
          />
        )}
        {selectedChart && (
          <ChartEditor
            chart={selectedChart}
            schemaFields={selectedSchema?.fields ?? []}
            presets={presets.filter((preset) => preset.recipe_id === selectedChart.recipe_id)}
            updateChart={updateChart}
            generateChart={generateChart}
            removeChart={removeChart}
            savePreset={savePreset}
            presetName={chartDraft.presetName}
            setPresetName={(presetName) => setChartDraft((current) => ({ ...current, presetName }))}
            saveGlobal={chartDraft.saveGlobal}
            setSaveGlobal={(saveGlobal) => setChartDraft((current) => ({ ...current, saveGlobal }))}
            openArtifact={openArtifact}
          />
        )}
        {selection.kind === "review" && <ReviewEditor analysis={analysis} packageView={exportedPackage} refreshReview={refreshReview} updateObservation={updateObservation} />}
        {selection.kind === "export" && <ExportEditor analysis={analysis} packageView={exportedPackage} exportAnalysis={exportAnalysis} openArtifact={openArtifact} />}
      </div>
    </div>
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

function SessionDraftEditor({ draft, setDraft, addSession, disabled }: { draft: typeof defaultSession; setDraft: (draft: typeof defaultSession) => void; addSession: () => void; disabled: boolean }) {
  return (
    <Panel title="Add Session" actions={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={addSession} disabled={disabled}>Add</Button>}>
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

function SessionEditor({ session, loadSession, removeSession }: { session: AnalysisSession; loadSession: (session: AnalysisSession) => void; removeSession: (session: AnalysisSession) => void }) {
  return (
    <Panel
      title={session.name}
      actions={
        <>
          <StatusBadge value={session.load_state} />
          <Button icon={<RefreshCw className="h-4 w-4" />} onClick={() => loadSession(session)}>Load</Button>
          <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => removeSession(session)}>Remove</Button>
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
  addChart
}: {
  draft: typeof chartDraftSeed;
  setDraft: (draft: typeof chartDraftSeed) => void;
  sessions: AnalysisSession[];
  recipes: AnalysisView["recipes"];
  presets: ParameterPreset[];
  addChart: () => void;
}) {
  const selectedRecipe = recipes.find((recipe) => recipe.recipe_id === draft.recipeId) ?? recipes[0];
  return (
    <Panel title="Add Chart" actions={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={addChart}>Add</Button>}>
      <div className="grid gap-3 md:grid-cols-2">
        <SelectField label="Recipe" value={draft.recipeId} onValueChange={(recipeId) => setDraft({ ...draft, recipeId, presetId: noPresetValue })} options={recipes.map((recipe) => ({ value: recipe.recipe_id, label: recipe.display_name }))} />
        <SelectField label="Session" value={draft.sessionId || sessions[0]?.session_id || ""} onValueChange={(sessionId) => setDraft({ ...draft, sessionId })} options={sessions.map((session) => ({ value: session.session_id, label: session.name }))} />
        {presets.length > 0 && (
          <SelectField
            label="Preset"
            value={draft.presetId}
            onValueChange={(presetId) => {
              const preset = presets.find((item) => item.preset_id === presetId);
              setDraft({
                ...draft,
                presetId,
                title: String(preset?.parameters.title ?? draft.title)
              });
            }}
            options={[{ value: noPresetValue, label: "None" }, ...presets.map((preset) => ({ value: preset.preset_id, label: preset.display_name }))]}
          />
        )}
        <Field label="Name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
        <Field label="Title" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
      </div>
      {selectedRecipe && <div className="mt-4 text-sm text-muted">{selectedRecipe.recipe_id}</div>}
    </Panel>
  );
}

const chartDraftSeed = {
  recipeId: "lap_time_delta",
  sessionId: "",
  name: "Lap time delta",
  title: "Lap time delta",
  presetId: noPresetValue,
  presetName: "Lap time delta",
  saveGlobal: false
};

function ChartEditor({
  chart,
  schemaFields,
  presets,
  updateChart,
  generateChart,
  removeChart,
  savePreset,
  presetName,
  setPresetName,
  saveGlobal,
  setSaveGlobal,
  openArtifact
}: {
  chart: ChartInstance;
  schemaFields: ParameterField[];
  presets: AnalysisView["analysis"]["presets"];
  updateChart: (chart: ChartInstance, parameters: Record<string, unknown>, presetId?: string | null) => void;
  generateChart: (chart: ChartInstance) => void;
  removeChart: (chart: ChartInstance) => void;
  savePreset: (chart: ChartInstance, global: boolean) => void;
  presetName: string;
  setPresetName: (value: string) => void;
  saveGlobal: boolean;
  setSaveGlobal: (value: boolean) => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
}) {
  const [parameters, setParameters] = useState<Record<string, unknown>>(chart.parameters);
  const [selectedPresetId, setSelectedPresetId] = useState(chart.preset_id ?? noPresetValue);

  useEffect(() => {
    setParameters(chart.parameters);
    setSelectedPresetId(chart.preset_id ?? noPresetValue);
  }, [chart.chart_instance_id, chart.parameters]);

  function applyPreset(presetId: string) {
    setSelectedPresetId(presetId);
    if (presetId === noPresetValue) return;
    const preset = presets.find((item) => item.preset_id === presetId);
    if (preset) setParameters(preset.parameters);
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
    <Panel
      title={chart.name}
      actions={
        <>
          <StatusBadge value={chart.generation_state} />
          <Button icon={<Save className="h-4 w-4" />} onClick={() => updateChart(chart, parameters, selectedPresetId === noPresetValue ? null : selectedPresetId)}>Save</Button>
          <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={() => generateChart(chart)}>Generate</Button>
          <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => removeChart(chart)}>Remove</Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <div className="grid gap-3">
          {artifact ? (
            <button className="overflow-hidden rounded-md border border-line bg-slate-50" onClick={() => openArtifact(artifact, "/api/analysis/assets")}>
              <img src={`/api/analysis/assets/${artifact.image_path}`} alt={artifact.artifact_id} className="aspect-video w-full object-contain" />
            </button>
          ) : (
            <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-line bg-slate-50 text-muted">
              <Image className="h-8 w-8" />
            </div>
          )}
          {chart.errors.length > 0 && <ErrorList errors={chart.errors} />}
        </div>
        <div className="grid gap-4">
          <div className="grid gap-3">
            {schemaFields.map((field) => (
              <ParameterControl key={field.name} field={field} value={parameters[field.name]} setValue={(value) => setParameters((current) => ({ ...current, [field.name]: value }))} />
            ))}
          </div>
          <div className="grid gap-3 rounded-md border border-line p-3">
            {presets.length > 0 && (
              <SelectField
                label="Preset"
                value={selectedPresetId}
                onValueChange={applyPreset}
                options={[{ value: noPresetValue, label: "None" }, ...presets.map((preset) => ({ value: preset.preset_id, label: preset.display_name }))]}
              />
            )}
            <Field label="Preset name" value={presetName} onChange={(event) => setPresetName(event.target.value)} />
            <CheckboxField label="Global" checked={saveGlobal} onCheckedChange={setSaveGlobal} />
            <Button icon={<Save className="h-4 w-4" />} onClick={() => savePreset(chart, saveGlobal)}>Save Preset</Button>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function ReviewEditor({
  analysis,
  packageView,
  refreshReview,
  updateObservation
}: {
  analysis: AnalysisView["analysis"] | null;
  packageView: PackageView | null;
  refreshReview: () => void;
  updateObservation: (observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) => void;
}) {
  const observations = packageView?.observations ?? [];
  return (
    <Panel title="Review" actions={<Button icon={<RefreshCw className="h-4 w-4" />} onClick={refreshReview} disabled={!analysis}>Refresh</Button>}>
      <div className="grid gap-4">
        <dl className="grid gap-3 sm:grid-cols-3">
          <Metric label="State" value={analysis?.review_stale ? "Stale" : "Current"} />
          <Metric label="Charts" value={analysis?.charts.length ?? 0} />
          <Metric label="Observations" value={observations.length} />
        </dl>
        <div className="grid gap-3">
          {observations.length > 0 ? (
            observations.map((observation) => (
              <ObservationCard key={observation.observation_id} observation={observation} updateObservation={updateObservation} />
            ))
          ) : (
            <div className="rounded-md border border-dashed border-line bg-slate-50 p-6 text-sm text-muted">No observations</div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function ObservationCard({
  observation,
  updateObservation
}: {
  observation: Observation;
  updateObservation: (observationId: string, reviewStatus: ReviewStatus, editedText?: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(observation.edited_text ?? observation.text);

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
            <Button icon={<CheckCircle2 className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "accepted")}>Accept</Button>
          )}
          {observation.review_status !== "rejected" && (
            <Button icon={<XCircle className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "rejected")}>Reject</Button>
          )}
          <Button icon={<Edit3 className="h-4 w-4" />} onClick={() => setEditing(true)}>Edit</Button>
          {observation.review_status !== "unreviewed" && (
            <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "unreviewed", null)}>Clear</Button>
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
            <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => updateObservation(observation.observation_id, "edited", draft)}>Save</Button>
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
  openArtifact
}: {
  analysis: AnalysisView["analysis"] | null;
  packageView: PackageView | null;
  exportAnalysis: () => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
}) {
  return (
    <div className="grid gap-4">
      <Panel title="Export" actions={<Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={exportAnalysis} disabled={!analysis}>Export</Button>}>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Metric label="Sessions" value={analysis?.sessions.length ?? 0} />
          <Metric label="Charts" value={analysis?.charts.length ?? 0} />
          <Metric label="Package" value={analysis?.exported_package_path ? compactPath(analysis.exported_package_path) : "None"} />
        </dl>
      </Panel>
      {packageView && (
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

function ParameterControl({ field, value, setValue }: { field: ParameterField; value: unknown; setValue: (value: unknown) => void }) {
  if (field.field_type === "checkbox") {
    return <CheckboxField label={field.label} checked={Boolean(value ?? field.default)} onCheckedChange={setValue} />;
  }
  if (field.field_type === "select" && field.options.length > 0) {
    return <SelectField label={field.label} value={String(value ?? field.default ?? field.options[0])} onValueChange={setValue} options={field.options.map((option) => ({ value: option, label: option }))} />;
  }
  return <Field label={field.label} value={String(value ?? field.default ?? "")} onChange={(event) => setValue(event.target.value)} />;
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
        "flex min-h-9 items-center justify-between gap-2 rounded-md px-2 text-left text-sm text-muted hover:bg-slate-100 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50",
        collapsed && "justify-center px-0",
        active && "bg-teal-50 text-brand"
      )}
      onClick={onClick}
      disabled={disabled}
      title={label}
    >
      <span className={cn("flex min-w-0 items-center gap-2", collapsed && "justify-center")}>
        {icon}
        {!collapsed && <span className="truncate">{label}</span>}
      </span>
      {!collapsed && status && <span className="rounded border border-line px-1.5 py-0.5 text-[11px]">{status}</span>}
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
        "flex min-h-8 items-center justify-between rounded-md px-2 py-1 text-xs font-semibold uppercase tracking-normal text-muted hover:bg-slate-100 hover:text-ink",
        collapsed && "justify-center px-0"
      )}
      onClick={onToggle}
      title={label}
    >
      <span className={cn("flex min-w-0 items-center gap-2", collapsed && "justify-center")}>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {!collapsed && <span>{label}</span>}
      </span>
      {!collapsed && <span>{count}</span>}
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

function splitDrivers(value: string) {
  return value
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
