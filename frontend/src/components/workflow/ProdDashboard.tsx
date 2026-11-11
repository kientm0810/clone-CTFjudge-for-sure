"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getDeployment, getRun, startDeploymentRun } from "@/lib/api";
import type { WorkflowDeployment, WorkflowRun } from "@/lib/types";
import { ComparisonResult } from "./ComparisonResult";
import { RuntimeInputs } from "./RuntimeInputs";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { WorkflowProgress } from "./WorkflowProgress";

function emptyInputs(deployment: WorkflowDeployment): string {
  return JSON.stringify(Object.fromEntries(
    deployment.definition.nodes
      .filter((node) => node.type === "input")
      .map((node) => [String(node.config.input_key ?? node.id), ""]),
  ), null, 2);
}

export function ProdDashboard() {
  const [deployment, setDeployment] = useState<WorkflowDeployment | null>(null);
  const [inputs, setInputs] = useState("{}");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDeployment("prod")
      .then((item) => { setDeployment(item); setInputs(emptyInputs(item)); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, []);

  async function gradeSubmission() {
    if (!deployment) return;
    setBusy(true); setError(null); setRun(null);
    try {
      const parsed = JSON.parse(inputs) as Record<string, unknown>;
      let current = await startDeploymentRun("prod", parsed);
      setRun(current);
      for (let attempt = 0; attempt < 180; attempt += 1) {
        if (["COMPLETED", "FAILED", "CANCELLED"].includes(current.status)) break;
        await new Promise((resolve) => setTimeout(resolve, 1000));
        current = await getRun(current.id);
        setRun(current);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  if (loading) return <main className="prod-page"><div className="prod-empty" role="status">Đang tải workflow đã publish…</div></main>;
  if (!deployment) return <main className="prod-page"><div className="prod-empty"><p className="section-label">Chưa sẵn sàng</p><h1>Chưa có workflow trên prod</h1><p>Vào trang cấu hình, chọn workflow phù hợp rồi bấm <strong>Publish lên prod</strong>.</p><Link className="primary-link" href="/">Đi tới cấu hình</Link>{error && <p className="inline-error">{error}</p>}</div></main>;

  return (
    <main className="prod-page">
      <header className="prod-header">
        <div><p className="eyebrow">CTFJudge · chấm một bài làm</p><h1>Đối chiếu bài sinh viên với golden solution</h1><p className="subtitle">Dán hai nội dung, bấm chấm bài và xem từng trích dẫn được đối chiếu với phần nào của đáp án.</p></div>
        <div className="deployment-badge"><span>PROD</span><strong>{deployment.workflow_name}</strong><small>ID {deployment.workflow_id.slice(0, 8)} · version {deployment.version_number}</small></div>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="prod-form card">
        <div className="card-heading"><div><p className="section-label">Bước 1</p><h2>Nhập bài cần chấm</h2><p className="card-help">Mỗi lần chạy chỉ chấm một bài sinh viên. Dữ liệu vector tạm của golden solution sẽ tự xóa khi hoàn tất.</p></div><button className="primary-button" onClick={gradeSubmission} disabled={busy}>{busy ? "Đang chấm…" : "Chấm bài"}</button></div>
        <RuntimeInputs definition={deployment.definition} value={inputs} onChange={setInputs} />
      </section>
      <section className="prod-workflow card">
        <div className="card-heading"><div><p className="section-label">Bước 2</p><h2>Workflow đang thực thi</h2><p className="card-help">Theo dõi hệ thống đang đọc dữ liệu, tạo vector, tìm evidence hay tổng hợp kết quả.</p></div>{run && <span className={`mini-status run-${run.status.toLowerCase()}`}>{run.status}</span>}</div>
        <WorkflowProgress definition={deployment.definition} run={run} />
        <WorkflowCanvas
          definition={deployment.definition}
          nodeStatuses={Object.fromEntries((run?.node_runs ?? []).map((node) => [node.node_id, node.status]))}
          readOnly
        />
      </section>
      <section className="prod-result card">
        <div className="card-heading"><div><p className="section-label">Bước 3</p><h2>Kết quả đối chiếu</h2><p className="card-help">Golden chunks → mức tương đồng toàn bài → đối chiếu từng student chunk.</p></div></div>
        <ComparisonResult run={run} />
      </section>
    </main>
  );
}
