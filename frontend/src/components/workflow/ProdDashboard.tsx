"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  createGoldenSnapshot,
  getActiveGoldenSnapshot,
  getDeployment,
  getGoldenSnapshot,
  getRun,
  startDeploymentRun,
} from "@/lib/api";
import type { GoldenSnapshot, WorkflowDeployment, WorkflowNode, WorkflowRun } from "@/lib/types";
import { ComparisonResult } from "./ComparisonResult";
import { DocxUpload } from "./DocxUpload";
import { RuntimeInputs } from "./RuntimeInputs";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { ExecutionTelemetry, WorkflowProgress } from "./WorkflowProgress";

function inputKey(node: WorkflowNode): string {
  return String(node.config.input_key ?? node.id);
}

function goldenInputNode(deployment: WorkflowDeployment): WorkflowNode | undefined {
  return deployment.definition.nodes.find((node) =>
    node.type === "input" && (
      node.config.document_type === "golden_solution"
      || inputKey(node).toLowerCase().includes("golden")
    )
  );
}

function freezeNodeId(deployment: WorkflowDeployment): string | undefined {
  return deployment.definition.nodes.find((node) =>
    node.type === "database"
    && node.config.operation === "upsert"
    && (node.config.freeze === true || node.id === "golden-index")
  )?.id;
}

function emptyStudentInputs(deployment: WorkflowDeployment, goldenKey?: string): string {
  return JSON.stringify(Object.fromEntries(
    deployment.definition.nodes
      .filter((node) => node.type === "input" && inputKey(node) !== goldenKey)
      .map((node) => [inputKey(node), ""]),
  ), null, 2);
}

function delay(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export function ProdDashboard() {
  const [deployment, setDeployment] = useState<WorkflowDeployment | null>(null);
  const [inputs, setInputs] = useState("{}");
  const [goldenContent, setGoldenContent] = useState("");
  const [snapshot, setSnapshot] = useState<GoldenSnapshot | null>(null);
  const [preparingSnapshot, setPreparingSnapshot] = useState<GoldenSnapshot | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const goldenNode = useMemo(() => deployment ? goldenInputNode(deployment) : undefined, [deployment]);
  const goldenKey = goldenNode ? inputKey(goldenNode) : undefined;
  const frozenNodeIds = snapshot?.frozen_node_ids ?? [];
  const snapshotProgress = useMemo(() => {
    const items = preparingSnapshot?.progress ?? [];
    return [...items].reverse().find((item) => !["COMPLETED", "FAILED"].includes(item.stage)) ?? items[items.length - 1];
  }, [preparingSnapshot]);
  const nodeStatuses = useMemo(() => {
    const statuses: Record<string, string> = Object.fromEntries(frozenNodeIds.map((id) => [id, "FROZEN"]));
    for (const node of run?.node_runs ?? []) statuses[node.node_id] = node.status;
    return statuses;
  }, [frozenNodeIds, run]);

  useEffect(() => {
    getDeployment("prod")
      .then(async (item) => {
        setDeployment(item);
        const key = goldenInputNode(item) ? inputKey(goldenInputNode(item)!) : undefined;
        setInputs(emptyStudentInputs(item, key));
        try {
          setSnapshot(await getActiveGoldenSnapshot("prod"));
        } catch {
          setSnapshot(null);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, []);

  async function prepareGolden() {
    if (!deployment || !goldenKey || !goldenContent.trim()) return;
    const targetNodeId = freezeNodeId(deployment);
    if (!targetNodeId) {
      setError("Workflow chưa có database node để freeze golden solution.");
      return;
    }
    setSnapshotBusy(true);
    setError(null);
    try {
      let current = await createGoldenSnapshot(
        "prod",
        { [goldenKey]: goldenContent.trim() },
        targetNodeId,
      );
      setPreparingSnapshot(current);
      for (let attempt = 0; attempt < 1800; attempt += 1) {
        if (["READY", "FAILED"].includes(current.status)) break;
        await delay(1000);
        current = await getGoldenSnapshot("prod", current.id);
        setPreparingSnapshot(current);
      }
      if (current.status === "FAILED") throw new Error(current.error || "Không thể chuẩn bị golden solution.");
      if (current.status !== "READY") throw new Error("Golden solution chưa hoàn tất trong thời gian chờ.");
      setSnapshot(current);
      setPreparingSnapshot(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSnapshotBusy(false);
    }
  }

  async function gradeSubmission() {
    if (!deployment || !snapshot) return;
    setBusy(true);
    setError(null);
    setRun(null);
    try {
      const parsed = JSON.parse(inputs) as Record<string, unknown>;
      let current = await startDeploymentRun("prod", parsed);
      setRun(current);
      for (let attempt = 0; attempt < 1800; attempt += 1) {
        if (["COMPLETED", "FAILED", "CANCELLED"].includes(current.status)) break;
        await delay(1000);
        current = await getRun(current.id);
        setRun(current);
      }
      if (!["COMPLETED", "FAILED", "CANCELLED"].includes(current.status)) {
        throw new Error("Bài chấm vẫn đang chạy. Bạn có thể kiểm tra lại trong lịch sử execution.");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="prod-page"><div className="prod-empty" role="status">Đang tải workflow đã publish…</div></main>;
  if (!deployment) return <main className="prod-page"><div className="prod-empty"><p className="section-label">Chưa sẵn sàng</p><h1>Chưa có workflow trên prod</h1><p>Vào trang cấu hình, chọn workflow phù hợp rồi bấm <strong>Publish lên prod</strong>.</p><Link className="primary-link" href="/">Đi tới cấu hình</Link>{error && <p className="inline-error">{error}</p>}</div></main>;

  return (
    <main className="prod-page">
      <header className="prod-header">
        <div><p className="eyebrow">CTFJudge · chấm nhiều bài cùng một đáp án</p><h1>Đối chiếu bài sinh viên với golden solution</h1><p className="subtitle">Chuẩn bị đáp án một lần, sau đó chấm lần lượt nhiều bài sinh viên mà không phải vector hóa lại nhánh golden.</p></div>
        <div className="deployment-badge"><span>PROD</span><strong>{deployment.workflow_name}</strong><small>ID {deployment.workflow_id.slice(0, 8)} · version {deployment.version_number}</small></div>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <section className="golden-freeze card">
        <div className="card-heading"><div><p className="section-label">Bước 1</p><h2>Chuẩn bị Golden solution</h2><p className="card-help">Hệ thống parse, tạo embedding và lưu vector một lần. Snapshot đang active sẽ được dùng cho mọi bài chấm tiếp theo.</p></div>{snapshot && <span className="mini-status snapshot-ready">FROZEN</span>}</div>
        {snapshot && <div className="snapshot-card" aria-label="Golden snapshot đang active">
          <div><small>Trạng thái</small><strong>READY · đang active</strong></div>
          <div><small>Số chunks</small><strong>{snapshot.chunk_count}</strong></div>
          <div><small>Embedding model</small><strong>{snapshot.embedding_model || "Mặc định"}</strong></div>
          <div><small>Collection</small><strong className="break-anywhere">{snapshot.collection_name}</strong></div>
        </div>}
        {goldenKey ? <div className="snapshot-input">
          <label htmlFor="golden-solution-input"><strong>{snapshot ? "Thay Golden solution" : (goldenNode?.name ?? "Golden solution")}</strong></label>
          <span>{snapshot ? "Nội dung mới chỉ thay bản đang active sau khi chuẩn bị thành công." : "Dán đáp án chuẩn vào đây để tạo snapshot đầu tiên."}</span>
          <DocxUpload onExtract={setGoldenContent} disabled={snapshotBusy} />
          <textarea id="golden-solution-input" aria-label="Golden solution" value={goldenContent} onChange={(event) => setGoldenContent(event.target.value)} />
        </div> : <p className="inline-error">Workflow không có input dành cho golden solution.</p>}
        <div className="snapshot-actions">
          <button className="primary-button" onClick={prepareGolden} disabled={snapshotBusy || !goldenContent.trim() || !goldenKey}>{snapshotBusy ? "Đang chuẩn bị…" : snapshot ? "Tạo snapshot mới" : "Chuẩn bị & Freeze"}</button>
          {preparingSnapshot && <p role="status" aria-live="polite">{preparingSnapshot.status === "RUNNING" ? "Đang parse và tạo vector cho Golden solution…" : "Đang xếp hàng chuẩn bị Golden solution…"}</p>}
        </div>
        <ExecutionTelemetry
          progress={snapshotProgress}
          nodeName={snapshotProgress ? deployment.definition.nodes.find((node) => node.id === snapshotProgress.node_id)?.name ?? snapshotProgress.node_id : undefined}
        />
      </section>

      <section className="prod-form card">
        <div className="card-heading"><div><p className="section-label">Bước 2</p><h2>Nhập bài sinh viên</h2><p className="card-help">Mỗi lần chạy chấm một bài. Golden snapshot phía trên được giữ nguyên và tái sử dụng.</p></div><button className="primary-button" onClick={gradeSubmission} disabled={busy || !snapshot}>{busy ? "Đang chấm…" : "Chấm bài"}</button></div>
        {!snapshot && <p className="snapshot-notice">Bạn cần chuẩn bị Golden solution trước khi chấm bài.</p>}
        <RuntimeInputs definition={deployment.definition} value={inputs} onChange={setInputs} hiddenKeys={goldenKey ? [goldenKey] : []} />
      </section>

      <section className="prod-workflow card">
        <div className="card-heading"><div><p className="section-label">Bước 3</p><h2>Workflow đang thực thi</h2><p className="card-help">Các node FROZEN đã chạy từ bước 1. Khi chấm bài, hệ thống chỉ chạy nhánh sinh viên, truy vấn evidence và tổng hợp kết quả.</p></div>{run && <span className={`mini-status run-${run.status.toLowerCase()}`}>{run.status}</span>}</div>
        <WorkflowProgress definition={deployment.definition} run={run} frozenNodeIds={frozenNodeIds} />
        <WorkflowCanvas definition={deployment.definition} nodeStatuses={nodeStatuses} readOnly />
      </section>

      <section className="prod-result card">
        <div className="card-heading"><div><p className="section-label">Bước 4</p><h2>Kết quả đối chiếu</h2><p className="card-help">Golden chunks → mức tương đồng toàn bài → đối chiếu từng student chunk.</p></div></div>
        <ComparisonResult run={run} />
      </section>
    </main>
  );
}
