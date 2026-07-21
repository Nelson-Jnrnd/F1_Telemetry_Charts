import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Edit3, RefreshCw } from "lucide-react";
import type { Artifact, Finding, Observation, PackageView, PreviewTab, ReviewStatus, SelectedDetail } from "../types";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { Panel } from "../components/ui/Panel";
import { StatusBadge } from "../components/ui/StatusBadge";
import { TabContent, Tabs } from "../components/ui/Tabs";
import { DataTable, Td, Th } from "../components/ui/Table";
import { Dialog } from "../components/ui/Dialog";
import { TextAreaField } from "../components/ui/Field";

type PackagePreviewPageProps = {
  view: PackageView | null;
  tab: PreviewTab;
  setTab: (tab: PreviewTab) => void;
  packagePath: string;
  setPackagePath: (path: string) => void;
  openPackage: () => Promise<void>;
  setSelected: (selected: SelectedDetail | null) => void;
  setOverlayArtifact: (artifact: Artifact) => void;
  regenerateDraft: () => Promise<void>;
  updateObservation: (observation: Observation, status: ReviewStatus, editedText?: string | null) => Promise<void>;
};

export function PackagePreviewPage(props: PackagePreviewPageProps) {
  const { view, tab, setTab, packagePath, setPackagePath, openPackage, setSelected, setOverlayArtifact, regenerateDraft, updateObservation } = props;
  const artifacts = view?.manifest?.artifacts ?? [];

  return (
    <div className="grid gap-4">
      <Panel title="Open Package">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <Field label="Package directory" value={packagePath} onChange={(event) => setPackagePath(event.target.value)} placeholder="runs/2023-bahrain-race" />
          <div className="flex items-end">
            <Button variant="primary" onClick={openPackage}>
              Open
            </Button>
          </div>
        </div>
      </Panel>

      {view ? (
        <Panel
          title={String(view.manifest?.project_id ?? "Package")}
          description={view.package_path}
          actions={
            <StatusBadge value={view.health.status} />
          }
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Metric label="Charts" value={artifacts.length} />
            <Metric label="Observations" value={view.observations.length} />
            <Metric label="Findings" value={view.health.findings.length} />
            <Metric label="Draft" value={view.draft_markdown ? "Present" : "Missing"} />
          </div>
        </Panel>
      ) : (
        <Panel title="No Package Open">
          <div className="rounded-md border border-dashed border-line bg-slate-50 p-8 text-center text-sm text-muted">No package</div>
        </Panel>
      )}

      {view && (
        <Tabs
          value={tab}
          onValueChange={setTab}
          items={[
            { value: "charts", label: "Charts" },
            { value: "observations", label: "Observations" },
            { value: "draft", label: "Draft" },
            { value: "integrity", label: "Integrity" }
          ]}
        >
          <TabContent value="charts">
            <ChartGallery artifacts={artifacts} setOverlayArtifact={setOverlayArtifact} />
          </TabContent>
          <TabContent value="observations">
            <ObservationList observations={view.observations} updateObservation={updateObservation} setSelected={setSelected} />
          </TabContent>
          <TabContent value="draft">
            <DraftPreview view={view} regenerateDraft={regenerateDraft} setSelected={setSelected} />
          </TabContent>
          <TabContent value="integrity">
            <IntegrityFindings findings={view.health.findings} setSelected={setSelected} />
          </TabContent>
        </Tabs>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-slate-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-normal text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function ChartGallery({ artifacts, setOverlayArtifact }: { artifacts: Artifact[]; setOverlayArtifact: (artifact: Artifact) => void }) {
  if (artifacts.length === 0) {
    return <EmptyPanel>No charts</EmptyPanel>;
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
      {artifacts.map((artifact) => (
        <article key={artifact.artifact_id} className="grid gap-3 rounded-lg border border-line bg-panel p-3">
          <button className="group cursor-zoom-in overflow-hidden rounded-md border border-line bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" onClick={() => setOverlayArtifact(artifact)}>
            {artifact.image_path ? (
              <img src={`/api/package/assets/${artifact.image_path}`} alt={artifact.artifact_id} className="aspect-video w-full object-contain transition group-hover:scale-[1.01]" />
            ) : (
              <div className="flex aspect-video items-center justify-center text-sm text-muted">Missing image</div>
            )}
          </button>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-ink" title={artifact.artifact_id}>{artifact.artifact_id}</h3>
            <p className="truncate text-xs text-muted" title={artifact.recipe_id}>{artifact.recipe_id}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

function ObservationList({ observations, updateObservation, setSelected }: { observations: Observation[]; updateObservation: (observation: Observation, status: ReviewStatus, editedText?: string | null) => Promise<void>; setSelected: (selected: SelectedDetail) => void }) {
  const grouped = useMemo(() => observations, [observations]);
  const [editing, setEditing] = useState<Observation | null>(null);
  const [draft, setDraft] = useState("");

  function openEdit(observation: Observation) {
    setEditing(observation);
    setDraft(observation.edited_text ?? observation.text);
  }

  if (observations.length === 0) {
    return <EmptyPanel>No observations</EmptyPanel>;
  }

  return (
    <>
      <div className="grid gap-2">
        {grouped.map((observation) => (
          <article key={observation.observation_id} className="grid gap-3 rounded-lg border border-line bg-panel p-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <button className="min-w-0 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" onClick={() => setSelected({ kind: "observation", value: observation })}>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <StatusBadge value={observation.review_status} />
                <span className="text-xs font-medium text-muted">{observation.observation_id}</span>
              </div>
              <p className="text-sm leading-6 text-ink">{observation.edited_text ?? observation.text}</p>
            </button>
            <div className="flex flex-wrap content-start gap-2">
              {observation.review_status !== "accepted" && <Button onClick={() => updateObservation(observation, "accepted")}>Accept</Button>}
              <Button icon={<Edit3 className="h-4 w-4" />} onClick={() => openEdit(observation)}>
                Edit
              </Button>
              {observation.review_status !== "unreviewed" && <Button onClick={() => updateObservation(observation, "unreviewed")}>Clear Review</Button>}
            </div>
          </article>
        ))}
      </div>
      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)} title="Edit Observation">
        <TextAreaField label="Observation text" value={draft} onChange={(event) => setDraft(event.target.value)} />
        <div className="flex justify-end gap-2">
          <Button onClick={() => setEditing(null)}>Cancel</Button>
          <Button
            variant="primary"
            onClick={async () => {
              if (editing) await updateObservation(editing, "edited", draft);
              setEditing(null);
            }}
          >
            Save Edit
          </Button>
        </div>
      </Dialog>
    </>
  );
}

function DraftPreview({ view, regenerateDraft, setSelected }: { view: PackageView; regenerateDraft: () => Promise<void>; setSelected: (selected: SelectedDetail) => void }) {
  return (
    <Panel
      title="Draft Markdown"
      actions={
        <>
          <Button onClick={() => setSelected({ kind: "draft", value: { markdownPath: view.manifest?.markdown_path, reviewCount: view.review.length } })}>Details</Button>
          <Button icon={<RefreshCw className="h-4 w-4" />} onClick={regenerateDraft}>
            Regenerate Draft
          </Button>
        </>
      }
    >
      <article className="max-w-none text-sm leading-7 text-ink [&_h1]:mb-3 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-lg [&_h3]:font-semibold [&_li]:ml-5 [&_ol]:list-decimal [&_p]:mb-3 [&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-line [&_td]:p-2 [&_th]:border [&_th]:border-line [&_th]:bg-slate-50 [&_th]:p-2 [&_ul]:list-disc">
        <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
          {view.draft_markdown ?? "No draft.md found."}
        </ReactMarkdown>
      </article>
    </Panel>
  );
}

function IntegrityFindings({ findings, setSelected }: { findings: Finding[]; setSelected: (selected: SelectedDetail) => void }) {
  if (findings.length === 0) {
    return <EmptyPanel>No integrity findings.</EmptyPanel>;
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Severity</Th>
          <Th>Code</Th>
          <Th>Path</Th>
          <Th>Message</Th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={`${finding.code}-${finding.path ?? "package"}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected({ kind: "finding", value: finding })}>
            <Td><StatusBadge value={finding.severity} /></Td>
            <Td>{finding.code}</Td>
            <Td>{finding.path ?? "package"}</Td>
            <Td>{finding.message}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function EmptyPanel({ children }: { children: string }) {
  return <div className="rounded-lg border border-dashed border-line bg-slate-50 p-8 text-center text-sm text-muted">{children}</div>;
}
