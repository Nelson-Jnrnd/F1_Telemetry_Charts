import { useEffect, useMemo, useState, type ReactNode } from "react";
import { BarChart3, CheckCircle2, ChevronDown, ChevronRight, ClipboardCheck, Download, Edit3, FilePlus2, FolderOpen, Image, LineChart, Play, Plus, RefreshCw, RotateCcw, Save, Trash2, XCircle } from "lucide-react";
import * as api from "../api";
import type { AnalysisSession, AnalysisView, Artifact, ChartInstance, Observation, PackageView, ParameterDiagnostics, ParameterField, ParameterPreset, ReviewStatus } from "../types";
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
  drivers: "ALL",
  dataSource: "fastf1" as "fastf1" | "local",
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
    parameters: { title: "Lap time delta" } as Record<string, unknown>,
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
    const parameters = preset?.parameters ?? { ...chartDraft.parameters, title: chartDraft.title || chartDraft.name };
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

  async function generateChart(chart: ChartInstance, parameters?: Record<string, unknown>, presetId?: string | null) {
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

  async function savePreset(chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting = false) {
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
    }
  }

  async function updatePreset(presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting = false) {
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
    }
  }

  async function deletePreset(preset: ParameterPreset) {
    if (!window.confirm(`Delete ${preset.display_name}?`)) return;
    try {
      const payload = await api.deleteAnalysisPreset(preset.preset_id);
      setView(payload);
      notify("Preset deleted", preset.display_name, "success");
    } catch (error) {
      notify("Delete failed", message(error), "error");
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
            schemaFields={selectedRecipe?.parameter_schema.fields ?? []}
            addChart={addChart}
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
  schemaFields,
  addChart
}: {
  draft: typeof chartDraftSeed;
  setDraft: (draft: typeof chartDraftSeed) => void;
  sessions: AnalysisSession[];
  recipes: AnalysisView["recipes"];
  presets: ParameterPreset[];
  schemaFields: ParameterField[];
  addChart: () => void;
}) {
  const selectedRecipe = recipes.find((recipe) => recipe.recipe_id === draft.recipeId) ?? recipes[0];
  const selectedSession = sessions.find((session) => session.session_id === draft.sessionId) ?? sessions[0];
  const sessionDrivers = selectedSession?.drivers ?? [];
  const sessionTeams = selectedSession?.available_teams ?? [];
  const [mode, setMode] = useState<"basic" | "advanced">("basic");
  const [diagnostics, setDiagnostics] = useState<ParameterDiagnostics | null>(null);
  const [presetFilter, setPresetFilter] = useState("");
  const fields = visibleSchemaFields(schemaFields, draft.parameters, mode);
  const filteredPresets = filterPresets(presets, presetFilter);

  useEffect(() => {
    if (!selectedRecipe || !selectedSession) return;
    const timer = window.setTimeout(() => {
      api
        .resolveAnalysisChartDiagnostics({
          template_id: draft.recipeId,
          target_session_ids: [selectedSession.session_id],
          parameters: { ...draft.parameters, title: draft.title || draft.name }
        })
        .then(setDiagnostics)
        .catch(() => setDiagnostics(null));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [draft.recipeId, draft.parameters, draft.title, draft.name, selectedRecipe, selectedSession]);

  const canAdd = Boolean(selectedSession) && diagnostics?.status !== "invalid";
  return (
    <Panel title="Add Chart" actions={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={addChart} disabled={!canAdd}>Add</Button>}>
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
      <div className="mt-4 flex gap-2">
        <Button variant={mode === "basic" ? "primary" : "secondary"} onClick={() => setMode("basic")}>Basic</Button>
        <Button variant={mode === "advanced" ? "primary" : "secondary"} onClick={() => setMode("advanced")}>Advanced</Button>
      </div>
      {diagnostics && (
        <div className="mt-4 grid gap-2 rounded-md border border-line p-3">
          <div className="flex flex-wrap gap-2">
            <StatusBadge value={diagnostics.status} />
            {diagnostics.active_filter_summary.map((item) => (
              <span key={item} className="rounded border border-line px-2 py-1 text-xs text-muted">{item}</span>
            ))}
          </div>
          {diagnostics.warnings.length > 0 && <WarningList warnings={diagnostics.warnings.map((item) => item.message)} />}
          {diagnostics.errors.length > 0 && <ErrorList errors={diagnostics.errors.map((item) => item.message)} />}
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
          setParameter={(field, value) => {
            const parameters = { ...draft.parameters, [field.name]: value };
            setDraft({
              ...draft,
              parameters,
              title: field.name === "title" ? String(value ?? "") : draft.title
            });
          }}
        />
      </div>
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
  openArtifact
}: {
  chart: ChartInstance;
  sessions: AnalysisSession[];
  schemaFields: ParameterField[];
  presets: AnalysisView["analysis"]["presets"];
  updateChart: (chart: ChartInstance, parameters: Record<string, unknown>, presetId?: string | null) => void;
  generateChart: (chart: ChartInstance, parameters?: Record<string, unknown>, presetId?: string | null) => void;
  removeChart: (chart: ChartInstance) => void;
  savePreset: (chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting?: boolean) => void;
  updatePreset: (presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting?: boolean) => void;
  deletePreset: (preset: ParameterPreset) => void;
  presetName: string;
  setPresetName: (value: string) => void;
  saveGlobal: boolean;
  setSaveGlobal: (value: boolean) => void;
  openArtifact: (artifact: Artifact, assetBase: string) => void;
}) {
  const [parameters, setParameters] = useState<Record<string, unknown>>(chart.parameters);
  const [selectedPresetId, setSelectedPresetId] = useState(chart.preset_id ?? noPresetValue);
  const [mode, setMode] = useState<"basic" | "advanced">("basic");
  const [diagnostics, setDiagnostics] = useState<ParameterDiagnostics | null>(null);
  const [presetToolsOpen, setPresetToolsOpen] = useState(false);
  const [presetFilter, setPresetFilter] = useState("");
  const selectedPreset = presets.find((item) => item.preset_id === selectedPresetId) ?? null;
  const filteredPresets = filterPresets(presets, presetFilter);
  const targetSession = sessions.find((session) => chart.target_session_ids.includes(session.session_id));
  const sessionDrivers = targetSession?.drivers ?? [];
  const sessionTeams = targetSession?.available_teams ?? [];
  const drivers = sessionDrivers.length > 0 ? sessionDrivers : Array.isArray(parameters.drivers) ? parameters.drivers.map(String) : [];
  const fields = visibleSchemaFields(schemaFields, parameters, mode);
  const dirty = !sameJson(parameters, chart.parameters) || selectedPresetId !== (chart.preset_id ?? noPresetValue);

  useEffect(() => {
    setParameters(chart.parameters);
    setSelectedPresetId(chart.preset_id ?? noPresetValue);
  }, [chart.chart_instance_id, chart.parameters]);

  useEffect(() => {
    if (!targetSession) return;
    const timer = window.setTimeout(() => {
      api
        .resolveAnalysisChartDiagnostics({
          template_id: chart.recipe_id,
          target_session_ids: chart.target_session_ids,
          parameters
        })
        .then(setDiagnostics)
        .catch(() => setDiagnostics(null));
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
          <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={() => generateChart(chart, parameters, selectedPresetId === noPresetValue ? null : selectedPresetId)}>{dirty ? "Save + Generate" : "Generate"}</Button>
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
          <div className="flex flex-wrap gap-2">
            <Button variant={mode === "basic" ? "primary" : "secondary"} onClick={() => setMode("basic")}>Basic</Button>
            <Button variant={mode === "advanced" ? "primary" : "secondary"} onClick={() => setMode("advanced")}>Advanced</Button>
            <Button icon={<RotateCcw className="h-4 w-4" />} onClick={resetChart}>Reset chart</Button>
            <Button icon={<RotateCcw className="h-4 w-4" />} onClick={restorePreset} disabled={!selectedPreset}>Restore preset</Button>
            <Button icon={<XCircle className="h-4 w-4" />} onClick={clearOverrides}>Clear overrides</Button>
          </div>
          {diagnostics && (
            <div className="grid gap-2 rounded-md border border-line p-3">
              <div className="flex flex-wrap gap-2">
                <StatusBadge value={diagnostics.status} />
                {diagnostics.active_filter_summary.map((item) => (
                  <span key={item} className="rounded border border-line px-2 py-1 text-xs text-muted">{item}</span>
                ))}
              </div>
              {diagnostics.warnings.length > 0 && <WarningList warnings={diagnostics.warnings.map((item) => item.message)} />}
              {diagnostics.errors.length > 0 && <ErrorList errors={diagnostics.errors.map((item) => item.message)} />}
            </div>
          )}
          <RenderedConfigSummary chart={chart} dirty={dirty} preset={selectedPreset} diagnostics={diagnostics} sessionDriverCount={sessionDrivers.length} />
          <ParameterSections fields={fields} allFields={schemaFields} parameters={parameters} diagnostics={diagnostics} drivers={drivers} teams={sessionTeams} setParameter={(field, value) => setParameters((current) => ({ ...current, [field.name]: value }))} />
          {mode === "advanced" && (
            <div className="flex flex-wrap gap-2">
              <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("selection")}>Reset selection</Button>
              <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("filters")}>Reset filters</Button>
              <Button icon={<RotateCcw className="h-4 w-4" />} onClick={() => resetSection("presentation")}>Reset style</Button>
            </div>
          )}
          <PresetApplyPanel presets={filteredPresets} selectedPresetId={selectedPresetId} presetFilter={presetFilter} setPresetFilter={setPresetFilter} applyPreset={applyPreset} />
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
            />
          )}
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

function PresetApplyPanel({
  presets,
  selectedPresetId,
  presetFilter,
  setPresetFilter,
  applyPreset
}: {
  presets: ParameterPreset[];
  selectedPresetId: string;
  presetFilter: string;
  setPresetFilter: (value: string) => void;
  applyPreset: (presetId: string) => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-line p-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(180px,240px)]">
        <Field label="Find preset" value={presetFilter} onChange={(event) => setPresetFilter(event.target.value)} />
        <SelectField
          label="Apply preset"
          value={selectedPresetId}
          onValueChange={applyPreset}
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
  deletePreset
}: {
  chart: ChartInstance;
  parameters: Record<string, unknown>;
  selectedPreset: ParameterPreset | null;
  presetName: string;
  setPresetName: (value: string) => void;
  saveGlobal: boolean;
  setSaveGlobal: (value: boolean) => void;
  savePreset: (chart: ChartInstance, parameters: Record<string, unknown>, global: boolean, replaceExisting?: boolean) => void;
  updatePreset: (presetId: string, displayName: string, parameters?: Record<string, unknown>, replaceExisting?: boolean) => void;
  deletePreset: (preset: ParameterPreset) => void;
}) {
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
        <Button icon={<Save className="h-4 w-4" />} onClick={() => savePreset(chart, parameters, saveGlobal)}>Save Preset</Button>
        <Button icon={<RefreshCw className="h-4 w-4" />} onClick={() => savePreset(chart, parameters, saveGlobal, true)}>Replace</Button>
        <Button icon={<Edit3 className="h-4 w-4" />} onClick={() => selectedPreset && updatePreset(selectedPreset.preset_id, presetName || selectedPreset.display_name)} disabled={!selectedPreset}>Rename</Button>
        <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} onClick={() => selectedPreset && deletePreset(selectedPreset)} disabled={!selectedPreset}>Delete</Button>
      </div>
    </div>
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

function ParameterControl({
  field,
  value,
  drivers,
  teams,
  state,
  setValue
}: {
  field: ParameterField;
  value: unknown;
  drivers: string[];
  teams: string[];
  state: ParameterFieldState;
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
        <div className="flex items-center justify-between rounded-md border border-line bg-slate-50 px-3 py-2 text-sm text-muted">
          <span>{selected.length === 0 ? `All ${options.length}` : `${selected.length} selected`}</span>
          <button className="font-medium text-brand disabled:text-muted" type="button" disabled={state.disabled} onClick={() => setValue([])}>All</button>
        </div>
        {options.length > 8 && <Field label={`Find ${itemLabel}`} value={driverFilter} disabled={state.disabled} onChange={(event) => setDriverFilter(event.target.value)} />}
        <div className="grid max-h-56 gap-2 overflow-auto rounded-md border border-line p-2 sm:grid-cols-2">
          {visibleDrivers.map((driver) => (
            <CheckboxField
              key={driver}
              label={driver}
              checked={selected.length === 0 || selected.includes(driver)}
              disabled={state.disabled}
              onCheckedChange={(checked) => {
                const base = selected.length === 0 ? options : selected;
                const next = checked ? [...base.filter((item) => item !== driver), driver] : base.filter((item) => item !== driver);
                setValue(next.length === options.length ? [] : next);
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
    return (
      <div className="grid gap-2">
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Start" type="number" value={range.start ?? ""} disabled={state.disabled} onChange={(event) => setValue({ ...range, start: numberOrNull(event.target.value) })} />
          <Field label="End" type="number" value={range.end ?? ""} disabled={state.disabled} onChange={(event) => setValue({ ...range, end: numberOrNull(event.target.value) })} />
        </div>
        {feedback && <div className={cn("text-xs font-medium", state.error ? "text-danger" : "text-amber-700")}>{feedback}</div>}
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
    return <Field label={label} type="number" value={String(value ?? field.default ?? "")} disabled={state.disabled} error={state.error} description={state.warning} onChange={(event) => setValue(numberOrNull(event.target.value))} />;
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
  setParameter
}: {
  fields: ParameterField[];
  allFields: ParameterField[];
  parameters: Record<string, unknown>;
  diagnostics: ParameterDiagnostics | null;
  drivers: string[];
  teams: string[];
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

function RenderedConfigSummary({
  chart,
  dirty,
  preset,
  diagnostics,
  sessionDriverCount
}: {
  chart: ChartInstance;
  dirty: boolean;
  preset: ParameterPreset | null;
  diagnostics: ParameterDiagnostics | null;
  sessionDriverCount: number;
}) {
  const effective = diagnostics?.effective_configuration ?? {};
  const selection = objectValue(effective.selection);
  const filters = objectValue(effective.filters);
  const selectionMode = String(selection.driver_selection_mode ?? "all_session");
  const driverInfo = selection.drivers
    ? Array.isArray(selection.drivers)
      ? `${selection.drivers.length} driver(s)`
      : String(selection.drivers)
    : selectionMode === "all_session" && sessionDriverCount > 0
      ? `${sessionDriverCount} driver(s)`
      : selectionMode;
  const renderedState = dirty ? "Unsaved edits" : chart.generation_state === "generated" ? "Rendered saved config" : chart.generation_state;
  return (
    <dl className="grid gap-3 rounded-md border border-line bg-slate-50 p-3 sm:grid-cols-3">
      <Metric label="Image reflects" value={renderedState} />
      <Metric label="Preset" value={preset?.display_name ?? "None"} />
      <Metric label="Selection" value={driverInfo} />
      <Metric label="Filters" value={Object.keys(filters).length ? Object.keys(filters).join(", ") : "Default"} />
      <Metric label="Warnings" value={diagnostics?.warnings.length ?? 0} />
      <Metric label="Errors" value={diagnostics?.errors.length ?? 0} />
    </dl>
  );
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
  return { disabled: !enabled, required, error, warning };
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
  if (name === "series_colors") {
    const colors = objectValue(presentation.colors);
    return colors.overrides ?? fallback;
  }
  return selection[name] ?? filters[name] ?? analysis[name] ?? presentation[name] ?? fallback;
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
