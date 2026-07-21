import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { PluginStatus, SelectedDetail } from "../types";
import { Button } from "../components/ui/Button";
import { CheckboxField } from "../components/ui/CheckboxField";
import { TextAreaField } from "../components/ui/Field";
import { Panel } from "../components/ui/Panel";
import { StatusBadge } from "../components/ui/StatusBadge";
import { DataTable, Td, Th } from "../components/ui/Table";

type PluginsPageProps = {
  plugins: PluginStatus[];
  validatePlugins: (enabled: boolean, localPaths: string[], entryPointsEnabled: boolean) => Promise<void>;
  setSelected: (selected: SelectedDetail) => void;
};

export function PluginsPage({ plugins, validatePlugins, setSelected }: PluginsPageProps) {
  const [enabled, setEnabled] = useState(false);
  const [entryPointsEnabled, setEntryPointsEnabled] = useState(false);
  const [pluginPaths, setPluginPaths] = useState("");
  const localPaths = useMemo(() => pluginPaths.split(/\r?\n/).map((path) => path.trim()).filter(Boolean), [pluginPaths]);
  const recipes = plugins.flatMap((plugin) => plugin.recipes.map((recipe) => ({ ...recipe, plugin_id: plugin.plugin_id, source: plugin.display_name ?? plugin.plugin_id, available: plugin.status === "valid" })));

  return (
    <div className="grid gap-4">
      <Panel
        title="Plugin Sources"
        actions={
          <Button variant="primary" icon={<RefreshCw className="h-4 w-4" />} onClick={() => validatePlugins(enabled, localPaths, entryPointsEnabled)}>
            Validate Plugins
          </Button>
        }
      >
        <div className="grid gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="grid gap-3">
            <CheckboxField label="Enable plugins" checked={enabled} onCheckedChange={setEnabled} />
            <CheckboxField label="Discover entry points" checked={entryPointsEnabled} onCheckedChange={setEntryPointsEnabled} />
          </div>
          <TextAreaField label="Local plugin paths" value={pluginPaths} onChange={(event) => setPluginPaths(event.target.value)} placeholder="C:\\path\\to\\plugin" />
        </div>
      </Panel>

      <Panel title="Plugin Status">
        {plugins.length === 0 ? (
          <div className="rounded-md border border-dashed border-line bg-slate-50 p-8 text-center text-sm text-muted">No plugin validation results yet.</div>
        ) : (
          <DataTable>
            <thead>
              <tr>
                <Th>Status</Th>
                <Th>Plugin</Th>
                <Th>Source</Th>
                <Th>Recipes</Th>
                <Th>Errors</Th>
              </tr>
            </thead>
            <tbody>
              {plugins.map((plugin) => (
                <tr key={`${plugin.plugin_id}-${plugin.source_location}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected({ kind: "plugin", value: plugin })}>
                  <Td><StatusBadge value={plugin.status} /></Td>
                  <Td>{plugin.display_name ?? plugin.plugin_id}</Td>
                  <Td>{plugin.source_type}</Td>
                  <Td>{plugin.recipes.length}</Td>
                  <Td>{plugin.errors.length}</Td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </Panel>

      <Panel title="Plugin Recipes">
        {recipes.length === 0 ? (
          <p className="text-sm text-muted">No recipes</p>
        ) : (
          <DataTable>
            <thead>
              <tr>
                <Th>Availability</Th>
                <Th>Recipe ID</Th>
                <Th>Name</Th>
                <Th>Plugin</Th>
                <Th>Required Data</Th>
              </tr>
            </thead>
            <tbody>
              {recipes.map((recipe) => (
                <tr key={`${recipe.plugin_id}-${recipe.recipe_id}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected({ kind: "recipe", value: recipe })}>
                  <Td><StatusBadge value={recipe.available ? "valid" : "invalid"} /></Td>
                  <Td>{recipe.recipe_id}</Td>
                  <Td>{recipe.display_name}</Td>
                  <Td>{recipe.plugin_id}</Td>
                  <Td>{recipe.required_dataset_fields.join(", ") || "none"}</Td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </Panel>
    </div>
  );
}
