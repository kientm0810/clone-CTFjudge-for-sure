import type { RunHistoryItem } from "@/lib/types";
import { getRunHtmlReportUrl } from "@/lib/api";

type Props = {
  runs: RunHistoryItem[];
  selectedRunId?: string;
  busy: boolean;
  onOpen: (runId: string) => void;
  onRetry: (runId: string) => void;
  onDelete: (runId: string) => void;
};

function formatDate(value: string): string {
  return new Date(value).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function RunHistory({ runs, selectedRunId, busy, onOpen, onRetry, onDelete }: Props) {
  return (
    <section className="run-history">
      <div className="panel-heading compact">
        <div><p className="section-label">Executions</p><h2>Run history</h2></div>
        <span className="muted">{runs.length} runs</span>
      </div>
      {runs.length ? <div className="run-history-list">
        {runs.map((item) => {
          const active = ["PENDING", "RUNNING"].includes(item.status);
          return <article className={`run-history-item ${selectedRunId === item.id ? "selected" : ""}`} key={item.id}>
            <button className="run-open" onClick={() => onOpen(item.id)}>
              <code>{item.id.slice(0, 8)}</code>
              <span className={`run-state run-${item.status.toLowerCase()}`}>{item.status}</span>
              <strong>v{item.version_number}</strong>
              <small>{formatDate(item.created_at)}</small>
            </button>
            <div className="run-actions">
              {item.status === "COMPLETED" && <a href={getRunHtmlReportUrl(item.id)}>HTML</a>}
              <button disabled={busy || active} onClick={() => onRetry(item.id)}>Retry</button>
              <button className="delete" disabled={busy || active} onClick={() => onDelete(item.id)}>Delete</button>
            </div>
          </article>;
        })}
      </div> : <div className="empty-history">Workflow này chưa có lần chạy nào.</div>}
    </section>
  );
}
