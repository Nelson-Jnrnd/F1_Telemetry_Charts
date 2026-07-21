import { useState } from "react";
import { Trash2 } from "lucide-react";
import type { HistoryItem, SelectedDetail } from "../types";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Panel } from "../components/ui/Panel";
import { StatusBadge } from "../components/ui/StatusBadge";
import { DataTable, Td, Th } from "../components/ui/Table";

type RunHistoryPageProps = {
  history: HistoryItem[];
  clearHistory: () => Promise<void>;
  setSelected: (selected: SelectedDetail) => void;
  openHistoryPackage: (path: string) => Promise<void>;
};

export function RunHistoryPage({ history, clearHistory, setSelected, openHistoryPackage }: RunHistoryPageProps) {
  const [confirmClear, setConfirmClear] = useState(false);

  return (
    <div className="grid gap-4">
      <Panel
        title="Run History"
        actions={
          <Button variant="destructive" icon={<Trash2 className="h-4 w-4" />} disabled={history.length === 0} onClick={() => setConfirmClear(true)}>
            Clear History
          </Button>
        }
      >
        {history.length === 0 ? (
          <div className="rounded-md border border-dashed border-line bg-slate-50 p-8 text-center text-sm text-muted">No history</div>
        ) : (
          <DataTable>
            <thead>
              <tr>
                <Th>Action</Th>
                <Th>Path</Th>
                <Th>Open</Th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={`${item.action}-${item.package_path}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected({ kind: "history", value: item })}>
                  <Td><StatusBadge value={item.action} /></Td>
                  <Td>{item.package_path}</Td>
                  <Td>
                    <Button onClick={(event) => {
                      event.stopPropagation();
                      openHistoryPackage(item.package_path);
                    }}>
                      Open Package
                    </Button>
                  </Td>
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
            onClick={async () => {
              await clearHistory();
              setConfirmClear(false);
            }}
          >
            Clear History
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
