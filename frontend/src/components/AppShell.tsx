import { useState, type ReactNode } from "react";
import { BarChart3, History, PanelLeftClose, PanelLeftOpen, Plug } from "lucide-react";
import type { Page } from "../types";
import { cn } from "../lib/utils";

const navItems: { page: Page; label: string; icon: ReactNode }[] = [
  { page: "plugins", label: "Plugins", icon: <Plug className="h-4 w-4" /> },
  { page: "history", label: "Run History", icon: <History className="h-4 w-4" /> }
];

export type SidebarRenderer = (collapsed: boolean) => ReactNode;

type AppShellProps = {
  page: Page;
  setPage: (page: Page) => void;
  sidebarContent?: SidebarRenderer | null;
  detail?: ReactNode;
  children: ReactNode;
};

export function AppShell({ page, setPage, sidebarContent, detail, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <main
      className={cn(
        "grid min-h-screen grid-cols-1 bg-surface text-ink",
        collapsed
          ? detail
            ? "lg:grid-cols-[64px_minmax(0,1fr)_340px]"
            : "lg:grid-cols-[64px_minmax(0,1fr)]"
          : detail
            ? "lg:grid-cols-[280px_minmax(0,1fr)_340px]"
            : "lg:grid-cols-[280px_minmax(0,1fr)]"
      )}
    >
      <aside className="flex min-h-0 flex-col border-b border-line bg-panel px-3 py-4 lg:h-screen lg:border-b-0 lg:border-r">
        <div className={cn("mb-4 flex items-center gap-2", collapsed && "justify-center")}>
          <button
            className={cn("flex min-w-0 items-center gap-2 rounded-md text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent", collapsed && "justify-center")}
            onClick={() => setPage("workbench")}
            title="F1 Telemetry Charts"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink text-white">
              <BarChart3 className="h-5 w-5" />
            </span>
            {!collapsed && <span className="min-w-0 text-base font-semibold leading-tight">F1 Telemetry Charts</span>}
          </button>
          <button
            className={cn(
              "ml-auto hidden h-9 w-9 items-center justify-center rounded-md text-muted hover:bg-slate-100 hover:text-ink lg:flex",
              collapsed && "ml-0"
            )}
            onClick={() => setCollapsed((value) => !value)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {sidebarContent?.(collapsed)}
        </div>

        <nav className="mt-4 grid gap-2 border-t border-line pt-4">
          {navItems.map((item) => (
            <button
              key={item.page}
              className={cn(
                "flex min-h-10 items-center gap-2 rounded-md px-3 text-left text-sm font-medium text-muted transition hover:bg-slate-100 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                collapsed && "justify-center px-2",
                page === item.page && "bg-teal-50 text-brand"
              )}
              onClick={() => setPage(item.page)}
              title={item.label}
            >
              {item.icon}
              {!collapsed && item.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="min-w-0 px-4 py-4 lg:px-6">
        {children}
      </section>

      {detail && <aside className="min-w-0 border-t border-line bg-panel p-4 lg:border-l lg:border-t-0">{detail}</aside>}
    </main>
  );
}
