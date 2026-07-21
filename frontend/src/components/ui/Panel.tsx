import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

type PanelProps = {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Panel({ title, description, actions, children, className }: PanelProps) {
  return (
    <section className={cn("rounded-lg border border-line bg-panel", className)}>
      {(title || actions || description) && (
        <header className="flex min-h-14 items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="grid gap-1">
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {description && <p className="text-sm text-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
