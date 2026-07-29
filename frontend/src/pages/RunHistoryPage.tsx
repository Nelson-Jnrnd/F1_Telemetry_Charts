import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import type { HistoryItem, SelectedDetail } from "../types";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Panel } from "../components/ui/Panel";
import { StatusBadge } from "../components/ui/StatusBadge";
import { DataTable, Td, Th } from "../components/ui/Table";
import { compactPath } from "../lib/utils";

type RunHistoryPageProps = {
  history: HistoryItem[];
  historyLoading: boolean;
  clearHistory: () => Promise<void>;
  setSelected: (selected: SelectedDetail) => void;
};

export function RunHistoryPage({ history, historyLoading, clearHistory, setSelected }: RunHistoryPageProps) {
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearPending, setClearPending] = useState(false);

  async function confirmClearHistory() {
    setClearPending(true);
    try {
      await clearHistory();
      setConfirmClear(false);
    } finally {
      setClearPending(false);
    }
  }

  return (
    <div className="grid gap-4">
      <Panel
        title="Run History"
        actions={
          <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} disabled={historyLoading || history.length === 0} onClick={() => setConfirmClear(true)}>
            Clear History
          </Button>
        }
      >
        {historyLoading ? (
          <div className="flex min-h-28 items-center justify-center rounded-md border border-line bg-slate-50 text-sm font-medium text-muted">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Loading history
            </span>
          </div>
        ) : history.length === 0 ? (
          <div className="rounded-md border border-dashed border-line bg-slate-50 p-8 text-center text-sm text-muted">No history</div>
        ) : (
          <DataTable>
            <thead>
              <tr>
                <Th>Action</Th>
                <Th>Path</Th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={`${item.action}-${item.package_path}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected({ kind: "history", value: item })}>
                  <Td><StatusBadge value={item.action} /></Td>
                  <Td><span title={item.package_path}>{compactPath(item.package_path)}</span></Td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </Panel>

      <Dialog open={confirmClear} onOpenChange={setConfirmClear} title="Clear History">
        <div className="flex justify-end gap-2">
          <Button onClick={() => setConfirmClear(false)}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={confirmClearHistory}
            loading={clearPending}
          >
            Clear History
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
