import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export function DataTable({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-auto rounded-lg border border-line bg-panel", className)}>
      <table className="min-w-full border-separate border-spacing-0 text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return <th className="sticky top-0 border-b border-line bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-normal text-muted">{children}</th>;
}

export function Td({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn("border-b border-line px-3 py-2 align-top text-sm text-ink", className)}>{children}</td>;
}
