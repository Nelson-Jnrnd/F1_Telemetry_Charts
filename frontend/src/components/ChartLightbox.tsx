import type { Artifact } from "../types";
import { Dialog } from "./ui/Dialog";

type ChartLightboxProps = {
  artifact: Artifact | null;
  onOpenChange: (open: boolean) => void;
  assetBase?: string;
};

export function ChartLightbox({ artifact, onOpenChange, assetBase = "/api/package/assets" }: ChartLightboxProps) {
  return (
    <Dialog
      open={artifact !== null}
      onOpenChange={onOpenChange}
      title={artifact?.artifact_id ?? "Chart"}
      className="w-[min(1180px,calc(100vw-32px))]"
      hideCloseButton
    >
      {artifact?.image_path ? (
        <div className="grid gap-3">
          <img
            src={`${assetBase}/${artifact.image_path}`}
            alt={artifact.artifact_id}
            className="max-h-[calc(100vh-220px)] w-full rounded-md border border-line object-contain"
          />
          <dl className="grid gap-2 rounded-md border border-line bg-slate-50 p-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-normal text-muted">Recipe</dt>
              <dd className="break-words text-ink">{artifact.recipe_id}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-normal text-muted">Image</dt>
              <dd className="break-words text-ink">{artifact.image_path}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-normal text-muted">Metadata</dt>
              <dd className="break-words text-ink">{artifact.metadata_path ?? "None"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-normal text-muted">Title</dt>
              <dd className="break-words text-ink">{artifact.title ?? "None"}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <div className="flex min-h-72 items-center justify-center rounded-md border border-dashed border-line bg-slate-50 text-sm text-muted">No image</div>
      )}
    </Dialog>
  );
}
