import { FileText } from "lucide-react";
import type { SelectedDetail } from "../types";
import { compactPath } from "../lib/utils";
import { Panel } from "./ui/Panel";
import { StatusBadge } from "./ui/StatusBadge";

function Field({ label, value }: { label: string; value: unknown }) {
  const rendered = Array.isArray(value) ? value.join(", ") : value === null || value === undefined || value === "" ? "None" : String(value);
  return (
    <>
      <dt className="text-xs font-semibold uppercase tracking-normal text-muted">{label}</dt>
      <dd className="mb-3 break-words text-sm text-ink">{rendered}</dd>
    </>
  );
}

export function DetailPanel({ selected }: { selected: SelectedDetail | null }) {
  if (!selected) {
    return (
      <Panel title="Detail">
        <div className="flex min-h-44 items-center justify-center rounded-md border border-dashed border-line bg-slate-50 text-center text-sm text-muted">
          No selection
        </div>
      </Panel>
    );
  }

  if (selected.kind === "observation") {
    const observation = selected.value;
    return (
      <Panel title="Observation Detail" actions={<StatusBadge value={observation.review_status} />}>
        <dl>
          <Field label="Observation ID" value={observation.observation_id} />
          <Field label="Confidence" value={observation.confidence} />
          <Field label="Text" value={observation.text} />
          <Field label="Edited Text" value={observation.edited_text} />
          <Field label="Evidence" value={observation.evidence_artifact_ids ?? []} />
          <Field label="Limitations" value={observation.limitations ?? []} />
        </dl>
      </Panel>
    );
  }

  if (selected.kind === "finding") {
    const finding = selected.value;
    return (
      <Panel title="Integrity Finding" actions={<StatusBadge value={finding.severity} />}>
        <dl>
          <Field label="Code" value={finding.code} />
          <Field label="Path" value={finding.path ?? "package"} />
          <Field label="Message" value={finding.message} />
        </dl>
      </Panel>
    );
  }

  if (selected.kind === "plugin") {
    const plugin = selected.value;
    return (
      <Panel title="Plugin Detail" actions={<StatusBadge value={plugin.status} />}>
        <dl>
          <Field label="Plugin ID" value={plugin.plugin_id} />
          <Field label="Name" value={plugin.display_name} />
          <Field label="Version" value={plugin.version} />
          <Field label="Provider" value={plugin.provider} />
          <Field label="Source" value={`${plugin.source_type}: ${compactPath(plugin.source_location)}`} />
          <Field label="Recipes" value={plugin.recipes.map((recipe) => recipe.recipe_id)} />
          <Field label="Errors" value={plugin.errors} />
          <Field label="Warnings" value={plugin.warnings} />
        </dl>
      </Panel>
    );
  }

  if (selected.kind === "recipe") {
    const recipe = selected.value;
    return (
      <Panel title="Recipe Detail">
        <dl>
          <Field label="Recipe ID" value={recipe.recipe_id} />
          <Field label="Name" value={recipe.display_name} />
          <Field label="Plugin" value={recipe.plugin_id ?? recipe.source ?? "core"} />
          <Field label="Required Data" value={recipe.required_dataset_fields ?? []} />
          <Field label="Outputs" value={recipe.output_artifact_types ?? []} />
          <Field label="Factory" value={recipe.factory ?? "core"} />
        </dl>
      </Panel>
    );
  }

  if (selected.kind === "draft") {
    return (
      <Panel title="Draft Detail" actions={<FileText className="h-4 w-4 text-muted" />}>
        <dl>
          <Field label="Markdown path" value={selected.value.markdownPath} />
          <Field label="Review records" value={selected.value.reviewCount} />
        </dl>
      </Panel>
    );
  }

  return (
    <Panel title="Run Detail" actions={<StatusBadge value={selected.value.action} />}>
      <dl>
        <Field label="Action" value={selected.value.action} />
        <Field label="Package path" value={selected.value.package_path} />
      </dl>
    </Panel>
  );
}
