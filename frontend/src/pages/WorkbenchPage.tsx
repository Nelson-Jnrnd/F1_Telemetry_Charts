import { useEffect, useMemo, useState } from "react";
import { Controller, type Resolver, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Play, RotateCcw, Save, ShieldCheck } from "lucide-react";
import type { PluginStatus, ProjectConfigForm, SelectedDetail, ValidationResponse } from "../types";
import { apiIssuePathToField } from "../lib/utils";
import { configSchema, coreRecipes, defaultConfig } from "../schemas";
import { Button } from "../components/ui/Button";
import { CheckboxField } from "../components/ui/CheckboxField";
import { Dialog } from "../components/ui/Dialog";
import { Field, TextAreaField } from "../components/ui/Field";
import { Panel } from "../components/ui/Panel";
import { SelectField } from "../components/ui/SelectField";
import { StatusBadge } from "../components/ui/StatusBadge";

type WorkbenchPageProps = {
  validation: ValidationResponse | null;
  plugins: PluginStatus[];
  onValidate: (config: ProjectConfigForm) => Promise<void>;
  onSave: (path: string, config: ProjectConfigForm) => Promise<void>;
  onRun: (config: ProjectConfigForm) => Promise<void>;
  setSelected: (selected: SelectedDetail | null) => void;
};

type FieldErrors = Record<string, { message?: string }>;

export function WorkbenchPage({ validation, plugins, onValidate, onSave, onRun, setSelected }: WorkbenchPageProps) {
  const [configPath, setConfigPath] = useState("configs/ui-run.json");
  const [driverText, setDriverText] = useState(defaultConfig.driver_selection.drivers.join(", "));
  const [pluginPathText, setPluginPathText] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [showPayload, setShowPayload] = useState(false);

  const form = useForm<ProjectConfigForm>({
    resolver: zodResolver(configSchema) as Resolver<ProjectConfigForm>,
    defaultValues: defaultConfig,
    mode: "onBlur"
  });
  const { register, handleSubmit, control, setValue, watch, reset, formState } = form;
  const values = watch();

  useEffect(() => {
    setValue(
      "driver_selection.drivers",
      driverText
        .split(",")
        .map((driver) => driver.trim().toUpperCase())
        .filter(Boolean),
      { shouldDirty: true, shouldValidate: true }
    );
  }, [driverText, setValue]);

  useEffect(() => {
    setValue(
      "plugins.local_paths",
      pluginPathText
        .split(/\r?\n/)
        .map((path) => path.trim())
        .filter(Boolean),
      { shouldDirty: true, shouldValidate: true }
    );
  }, [pluginPathText, setValue]);

  const selectedRecipeIds = useMemo(() => new Set(values.recipes.map((recipe) => recipe.recipe_id)), [values.recipes]);
  const validPluginRecipes = plugins.flatMap((plugin) =>
    plugin.status === "valid"
      ? plugin.recipes.map((recipe) => ({
          ...recipe,
          plugin_id: plugin.plugin_id,
          source: plugin.display_name ?? plugin.plugin_id
        }))
      : []
  );
  const allRecipeOptions = [
    ...coreRecipes.map((recipe) => ({ ...recipe, source: "core", required_dataset_fields: [], output_artifact_types: ["png", "json"], factory: "core" })),
    ...validPluginRecipes
  ];
  const backendIssues = validation?.issues ?? [];
  const fieldErrors = formState.errors as unknown as FieldErrors;

  function toggleRecipe(recipeId: string, enabled: boolean) {
    const existing = values.recipes.filter((recipe) => recipe.recipe_id !== recipeId);
    setValue("recipes", enabled ? [...existing, { recipe_id: recipeId, enabled: true, title: null }] : existing, {
      shouldDirty: true,
      shouldValidate: true
    });
  }

  function toggleFormat(format: "png" | "json", enabled: boolean) {
    const formats = values.exports.formats.filter((item) => item !== format);
    setValue("exports.formats", enabled ? [...formats, format] : formats, { shouldDirty: true, shouldValidate: true });
  }

  function backendFieldError(field: string) {
    return backendIssues.find((issue) => apiIssuePathToField(issue.path) === field)?.message;
  }

  return (
    <form className="grid gap-4" onSubmit={(event) => event.preventDefault()}>
      <Panel
        title="Workbench"
        actions={
          <>
            {validation && <StatusBadge value={validation.status} />}
            <Button icon={<ShieldCheck className="h-4 w-4" />} onClick={handleSubmit(onValidate)}>
              Validate
            </Button>
            <Button icon={<Save className="h-4 w-4" />} onClick={handleSubmit((data) => onSave(configPath, data))}>
              Save
            </Button>
            <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={handleSubmit(onRun)}>
              Run
            </Button>
          </>
        }
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_280px]">
          <Field label="Config path" value={configPath} onChange={(event) => setConfigPath(event.target.value)} />
          <div className="flex items-end gap-2">
            <Button type="button" icon={<RotateCcw className="h-4 w-4" />} disabled={!formState.isDirty} onClick={() => setConfirmReset(true)}>
              Revert
            </Button>
            <Button type="button" onClick={() => setShowPayload((current) => !current)}>
              Raw Payload
            </Button>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Project">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Project ID" error={fieldErrors.project_id?.message ?? backendFieldError("project_id")} {...register("project_id")} />
            <Field label="Output directory" error={fieldErrors.output_dir?.message ?? backendFieldError("output_dir")} {...register("output_dir")} />
          </div>
        </Panel>

        <Panel title="Session">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Season" type="number" error={backendFieldError("session.season")} {...register("session.season", { valueAsNumber: true })} />
            <Field label="Event" error={backendFieldError("session.event")} {...register("session.event")} />
            <Field label="Session" error={backendFieldError("session.session")} {...register("session.session")} />
          </div>
        </Panel>

        <Panel title="Drivers">
          <TextAreaField label="Driver codes" value={driverText} onChange={(event) => setDriverText(event.target.value)} error={backendFieldError("driver_selection.drivers")} />
        </Panel>

        <Panel title="Cache">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Cache directory" error={backendFieldError("data_cache.directory")} {...register("data_cache.directory")} />
            <Controller
              control={control}
              name="data_cache.mode"
              render={({ field }) => (
                <SelectField
                  label="Cache mode"
                  value={field.value}
                  onValueChange={field.onChange}
                  options={[
                    { value: "cache-or-fetch", label: "Cache or fetch" },
                    { value: "cache-only", label: "Cache only" }
                  ]}
                />
              )}
            />
            <Field label="Fixture path" className="sm:col-span-2" error={backendFieldError("data_cache.fixture_path")} {...register("data_cache.fixture_path")} />
          </div>
        </Panel>

        <Panel title="Theme And Export">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Theme name" error={backendFieldError("theme.name")} {...register("theme.name")} />
            <Field label="Width" type="number" step="0.1" error={backendFieldError("theme.figure_width")} {...register("theme.figure_width", { valueAsNumber: true })} />
            <Field label="Height" type="number" step="0.1" error={backendFieldError("theme.figure_height")} {...register("theme.figure_height", { valueAsNumber: true })} />
            <Field label="DPI" type="number" error={backendFieldError("theme.dpi")} {...register("theme.dpi", { valueAsNumber: true })} />
            <Field label="Background" type="color" error={backendFieldError("theme.background_color")} {...register("theme.background_color")} />
            <Field label="Foreground" type="color" error={backendFieldError("theme.foreground_color")} {...register("theme.foreground_color")} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Controller control={control} name="theme.grid" render={({ field }) => <CheckboxField label="Grid" checked={field.value} onCheckedChange={field.onChange} />} />
            <CheckboxField label="PNG export" checked={values.exports.formats.includes("png")} onCheckedChange={(checked) => toggleFormat("png", checked)} />
            <CheckboxField label="JSON export" checked={values.exports.formats.includes("json")} onCheckedChange={(checked) => toggleFormat("json", checked)} />
          </div>
        </Panel>

        <Panel title="Plugins">
          <div className="grid gap-3">
            <Controller control={control} name="plugins.enabled" render={({ field }) => <CheckboxField label="Enable plugins" checked={field.value} onCheckedChange={field.onChange} />} />
            <Controller control={control} name="plugins.entry_points_enabled" render={({ field }) => <CheckboxField label="Python entry points" checked={field.value} onCheckedChange={field.onChange} />} />
            <TextAreaField label="Local plugin paths" value={pluginPathText} onChange={(event) => setPluginPathText(event.target.value)} />
          </div>
        </Panel>
      </div>

      <Panel title="Recipes">
        <div className="grid gap-2 md:grid-cols-2">
          {allRecipeOptions.map((recipe) => (
            <CheckboxField
              key={`${recipe.source}-${recipe.recipe_id}`}
              label={recipe.display_name}
              checked={selectedRecipeIds.has(recipe.recipe_id)}
              onCheckedChange={(checked) => toggleRecipe(recipe.recipe_id, checked)}
              description={`${recipe.recipe_id} - ${recipe.source}`}
              className="cursor-pointer"
            />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {allRecipeOptions.map((recipe) => (
            <Button key={`detail-${recipe.source}-${recipe.recipe_id}`} type="button" variant="ghost" onClick={() => setSelected({ kind: "recipe", value: recipe })}>
              {recipe.recipe_id}
            </Button>
          ))}
        </div>
      </Panel>

      {validation && (
        <Panel title="Validation" actions={<StatusBadge value={validation.status} />}>
          {backendIssues.length === 0 ? (
            <p className="text-sm text-muted">No backend validation issues.</p>
          ) : (
            <div className="grid gap-2">
              {backendIssues.map((issue) => (
                <div key={`${issue.path}-${issue.message}`} className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-950">
                  <strong>{issue.path}</strong>: {issue.message}
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {showPayload && (
        <Panel title="Advanced Raw Payload">
          <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-50">{JSON.stringify(values, null, 2)}</pre>
        </Panel>
      )}

      <Dialog open={confirmReset} onOpenChange={setConfirmReset} title="Revert Changes">
        <div className="flex justify-end gap-2">
          <Button onClick={() => setConfirmReset(false)}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => {
              reset(defaultConfig);
              setDriverText(defaultConfig.driver_selection.drivers.join(", "));
              setPluginPathText("");
              setConfirmReset(false);
            }}
          >
            Revert
          </Button>
        </div>
      </Dialog>
    </form>
  );
}
