import type { ReactNode } from "react";
import { BarChart3, History, PackageOpen, Plug, Settings2 } from "lucide-react";
import type { HealthStatus, Page } from "../types";
import { cn, compactPath } from "../lib/utils";
import { StatusBadge } from "./ui/StatusBadge";

const navItems: { page: Page; label: string; icon: ReactNode }[] = [
  { page: "preview", label: "Package Preview", icon: <PackageOpen className="h-4 w-4" /> },
  { page: "workbench", label: "Workbench", icon: <Settings2 className="h-4 w-4" /> },
  { page: "plugins", label: "Plugins", icon: <Plug className="h-4 w-4" /> },
  { page: "history", label: "Run History", icon: <History className="h-4 w-4" /> }
];

type AppShellProps = {
  page: Page;
  setPage: (page: Page) => void;
  packagePath: string;
  healthStatus?: HealthStatus | "no package";
  detail: ReactNode;
  children: ReactNode;
};

export function AppShell({ page, setPage, packagePath, healthStatus = "no package", detail, children }: AppShellProps) {
  return (
    <main className="grid min-h-screen grid-cols-1 bg-surface text-ink lg:grid-cols-[220px_minmax(0,1fr)_340px]">
      <aside className="border-b border-line bg-panel px-4 py-4 lg:border-b-0 lg:border-r">
        <div className="mb-5 flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink text-white">
            <BarChart3 className="h-5 w-5" />
          </div>
          <h1 className="text-base font-semibold leading-tight">F1 Telemetry Charts</h1>
        </div>
        <nav className="grid gap-2">
          {navItems.map((item) => (
            <button
              key={item.page}
              className={cn(
                "flex min-h-10 items-center gap-2 rounded-md px-3 text-left text-sm font-medium text-muted transition hover:bg-slate-100 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                page === item.page && "bg-teal-50 text-brand"
              )}
              onClick={() => setPage(item.page)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="min-w-0 px-4 py-4 lg:px-6">
        <header className="mb-4 flex min-h-14 flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-panel px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-normal text-muted">Current package</p>
            <p className="truncate text-sm font-medium text-ink" title={packagePath || "No package open"}>
              {compactPath(packagePath) || "No package open"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge value={healthStatus} />
          </div>
        </header>
        {children}
      </section>

      <aside className="min-w-0 border-t border-line bg-panel p-4 lg:border-l lg:border-t-0">{detail}</aside>
    </main>
  );
}
