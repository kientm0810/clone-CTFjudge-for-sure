"use client";

import { useEffect, useMemo, useState } from "react";
import { activateWorkflowVersion, createWorkflow, createWorkflowVersion, deleteRun, deleteWorkflow as deleteWorkflowApi, deleteWorkflowVersion, getDeployment, getRun, getWorkflow, getWorkflowVersion, listWorkflowRuns, listWorkflows, listWorkflowVersions, publishWorkflow, retryRun, startRun } from "@/lib/api";
import type { RunHistoryItem, WorkflowDefinition, WorkflowDeployment, WorkflowDetail, WorkflowRun, WorkflowSummary, WorkflowVersionSummary } from "@/lib/types";
import { ComparisonResult } from "./ComparisonResult";
import { ConfirmDialog } from "./ConfirmDialog";
import { RunHistory } from "./RunHistory";
import { RuntimeInputs } from "./RuntimeInputs";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { WorkflowEditor } from "./WorkflowEditor";
import { NodeGuide, WorkflowJourney } from "./WorkflowGuide";
import { WorkflowProgress } from "./WorkflowProgress";

const chunkOutputSchema = {
  type: "object",
  properties: {
    chunks: {
      type: "array",
      items: {
        type: "object",
        properties: {
          chunk_id: { type: "string" }, document_id: { type: "string" }, content: { type: "string" },
          chunk_index: { type: "integer" }, metadata: { type: "object" },
        },
        required: ["chunk_id", "document_id", "content", "chunk_index", "metadata"],
      },
    },
  },
  required: ["chunks"],
};

const comparisonOutputSchema = {
  type: "object",
  properties: {
    summary: { type: "string" },
    comparisons: {
      type: "array",
      items: {
        type: "object",
        properties: {
          student_chunk_id: { type: "string" }, student_content: { type: "string" },
          classification: {
            type: "string",
            enum: ["exact_match", "paraphrase", "partial_match", "additional_valid_approach", "contradiction", "incorrect", "irrelevant", "no_match"],
          },
          score: { type: "number", minimum: 0, maximum: 1 }, explanation: { type: "string" },
          matched_golden: {
            type: "array",
            items: {
              type: "object",
              properties: { chunk_id: { type: "string" }, content: { type: "string" }, similarity_score: { type: "number" } },
              required: ["chunk_id", "content", "similarity_score"],
            },
          },
        },
        required: ["student_chunk_id", "student_content", "classification", "score", "explanation", "matched_golden"],
      },
    },
  },
  required: ["summary", "comparisons"],
};

const ragDefinition: WorkflowDefinition = {
  name: "Golden solution similarity evaluation",
  version: 1,
  nodes: [
    { id: "golden-input", type: "input", name: "Golden solution", config: { input_key: "golden", document_type: "golden_solution" } },
    {
      id: "golden-parser", type: "agent", name: "Chunk golden",
      inputs: { document: "{{ steps.golden-input.output }}" },
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: chunkOutputSchema,
        prompt: "You are a deterministic text segmenter. Split the golden solution into short semantic steps without summarizing or adding facts. Copy document_id from the input document. Create stable chunk_id values such as golden-0, golden-1. Every chunk object must store its exact text in the property named content; never rename content to text or another name. Return JSON only.",
      },
    },
    {
      id: "golden-index", type: "database", name: "Index golden",
      inputs: { chunks: "{{ steps.golden-parser.output.chunks }}" },
      config: { operation: "upsert", collection: "golden-{{run_id}}", freeze: true, embedding_model: "ollama/nomic-embed-text" },
    },
    { id: "student-input", type: "input", name: "Student writeup", config: { input_key: "student", document_type: "student_submission" } },
    {
      id: "student-parser", type: "agent", name: "Chunk writeup",
      inputs: { document: "{{ steps.student-input.output }}" },
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: chunkOutputSchema,
        prompt: "You are a deterministic text segmenter. Split the student submission into short semantic steps without judging or adding facts. Copy document_id from the input document. Create stable chunk_id values such as student-0, student-1. Every chunk object must store its exact text in the property named content; never rename content to text or another name. Return JSON only.",
      },
    },
    {
      id: "golden-search", type: "database", name: "Retrieve evidence",
      inputs: { collection: "{{ steps.golden-index.output.collection }}", query_chunks: "{{ steps.student-parser.output.chunks }}" },
      config: { operation: "search", collection: "comparison-{{run_id}}", embedding_model: "ollama/nomic-embed-text", top_k: 3, score_threshold: 0.25 },
    },
    {
      id: "comparison-agent", type: "agent", name: "Similarity judge",
      inputs: { retrieval_results: "{{ steps.golden-search.output.retrieval_results }}" },
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: comparisonOutputSchema,
        prompt: "You compare one student submission with retrieved golden evidence. student-0, student-1, etc. are chunk IDs from the same submission, never different students. Evaluate every student chunk and refer to it as a chunk or citation. Give score from 0 to 1, one short Vietnamese explanation, and a short Vietnamese summary. Similar wording alone is not proof of correctness. Preserve student_content exactly and copy relevant golden IDs, content, and similarity scores. Return JSON only.",
      },
    },
    {
      id: "report", type: "output", name: "Similarity report",
      inputs: {
        analysis: "{{ steps.comparison-agent.output }}",
        retrieval_results: "{{ steps.golden-search.output.retrieval_results }}",
        golden_chunks: "{{ steps.golden-parser.output.chunks }}",
      },
      config: {
        format: "comparison_report",
      },
    },
  ],
  edges: [
    { source: "golden-input", target: "golden-parser" }, { source: "golden-parser", target: "golden-index" },
    { source: "student-input", target: "student-parser" }, { source: "golden-index", target: "golden-search" },
    { source: "student-parser", target: "golden-search" }, { source: "golden-search", target: "comparison-agent" },
    { source: "comparison-agent", target: "report" },
  ],
};

const goldenSample = `Ứng dụng ghép trực tiếp tham số id vào câu SQL nên tồn tại lỗ hổng SQL injection.
Dùng dấu nháy đơn để xác nhận lỗi cú pháp, sau đó xác định số cột bằng ORDER BY.
Khai thác bằng UNION SELECT và đọc bảng chứa flag để lấy giá trị cờ.`;
const studentSample = `Em kiểm tra tham số id bằng dấu nháy đơn và thấy ứng dụng báo lỗi cơ sở dữ liệu.
Sau đó em dùng UNION SELECT để ghép kết quả truy vấn và đọc được flag.
Em cũng thử quét thư mục bằng gobuster nhưng không tìm thấy gì hữu ích.`;

function sampleInputs(definition: WorkflowDefinition): Record<string, string> {
  const values: Record<string, string> = {};
  for (const node of definition.nodes.filter((item) => item.type === "input")) {
    const key = String(node.config.input_key ?? node.id);
    values[key] = key === "golden" ? goldenSample : key === "student" ? studentSample : "";
  }
  return values;
}

function formatTime(value?: string | null): string {
  return value ? new Date(value).toLocaleTimeString("vi-VN") : "—";
}

type DeleteTarget =
  | { kind: "workflow"; id: string; name: string }
  | { kind: "run"; id: string; name: string }
  | { kind: "version"; workflowId: string; version: number; name: string };

export function WorkflowDashboard() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [selected, setSelected] = useState<WorkflowDetail | null>(null);
  const [inputs, setInputs] = useState(JSON.stringify({ golden: goldenSample, student: studentSample }, null, 2));
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorSource, setEditorSource] = useState<WorkflowDefinition | undefined>();
  const [editorWorkflowId, setEditorWorkflowId] = useState<string | undefined>();
  const [versions, setVersions] = useState<WorkflowVersionSummary[]>([]);
  const [runHistory, setRunHistory] = useState<RunHistoryItem[]>([]);
  const [runDefinition, setRunDefinition] = useState<WorkflowDefinition | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deployment, setDeployment] = useState<WorkflowDeployment | null>(null);

  async function selectWorkflow(id: string) {
    setError(null);
    const [detail, history, runs] = await Promise.all([getWorkflow(id), listWorkflowVersions(id), listWorkflowRuns(id)]);
    setSelected(detail);
    setVersions(history);
    setRunHistory(runs);
    setInputs(JSON.stringify(sampleInputs(detail.definition), null, 2));
    setRun(null);
    setRunDefinition(null);
  }

  async function activateVersion(version: number) {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      await activateWorkflowVersion(selected.id, version);
      await refreshWorkflows(selected.id);
      setNotice(`Đã đưa version ${version} thành version đang dùng.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function refreshWorkflows(preferredId?: string) {
    const items = await listWorkflows();
    setWorkflows(items);
    const candidates = [preferredId, selected?.id, items[0]?.id];
    const nextId = candidates.find((id) => id && items.some((item) => item.id === id));
    if (nextId) await selectWorkflow(nextId);
    else {
      setSelected(null);
      setVersions([]);
      setRunHistory([]);
      setRun(null);
      setRunDefinition(null);
    }
  }

  useEffect(() => {
    refreshWorkflows().catch((reason) => setError(String(reason)));
    getDeployment("prod").then(setDeployment).catch(() => setDeployment(null));
    // Initial data load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function publishSelected() {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      const published = await publishWorkflow(selected.id);
      setDeployment(published);
      setNotice(`Đã publish workflow ${published.workflow_id.slice(0, 8)} · version ${published.version_number} lên prod.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function createRagDemo() {
    setBusy(true); setError(null);
    try {
      const created = await createWorkflow(ragDefinition, "CTFJudge rubric evaluation sử dụng Ollama và pgvector");
      await refreshWorkflows(created.id);
      setNotice("Đã tạo workflow mẫu. Bây giờ bạn có thể kiểm tra sơ đồ rồi chạy thử.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function runWorkflow() {
    if (!selected) return;
    setBusy(true); setError(null); setRun(null); setRunDefinition(null);
    try {
      const parsedInputs = JSON.parse(inputs) as Record<string, unknown>;
      const current = await startRun(selected.id, parsedInputs);
      await watchRun(current.id);
      setRunHistory(await listWorkflowRuns(selected.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function watchRun(runId: string) {
    let current = await getRun(runId);
    setRun(current);
    for (let attempt = 0; attempt < 1800; attempt += 1) {
      if (["COMPLETED", "FAILED", "CANCELLED"].includes(current.status)) return;
      await new Promise((resolve) => setTimeout(resolve, 1000));
      current = await getRun(runId);
      setRun(current);
    }
  }

  async function openRun(runId: string) {
    setError(null);
    try {
      const historyItem = runHistory.find((item) => item.id === runId);
      const [detail, version] = await Promise.all([
        getRun(runId),
        historyItem && selected ? getWorkflowVersion(selected.id, historyItem.version_number) : Promise.resolve(null),
      ]);
      setRun(detail);
      setRunDefinition(version?.definition ?? null);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function retryHistoricalRun(runId: string) {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      await retryRun(runId);
      const historyItem = runHistory.find((item) => item.id === runId);
      if (historyItem) {
        const version = await getWorkflowVersion(selected.id, historyItem.version_number);
        setRunDefinition(version.definition);
      }
      await watchRun(runId);
      setRunHistory(await listWorkflowRuns(selected.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function deleteHistoricalRun(runId: string) {
    if (!selected) return;
    setDeleteTarget({ kind: "run", id: runId, name: `run ${runId.slice(0, 8)}` });
  }

  async function performDeleteRun(runId: string) {
    if (!selected) return;
    await deleteRun(runId);
    if (run?.id === runId) { setRun(null); setRunDefinition(null); }
    setRunHistory(await listWorkflowRuns(selected.id));
    setNotice(`Đã xóa run ${runId.slice(0, 8)} và dữ liệu vector riêng của run.`);
  }

  async function editWorkflow(workflowId: string) {
    setBusy(true); setError(null);
    try {
      const detail = await getWorkflow(workflowId);
      setEditorWorkflowId(detail.id);
      setEditorSource(detail.definition);
      setEditorOpen(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function duplicateWorkflow(workflowId: string) {
    setBusy(true); setError(null);
    try {
      const detail = await getWorkflow(workflowId);
      const definition = { ...detail.definition, name: `${detail.name} - bản sao`, version: 1 };
      const created = await createWorkflow(definition, `Bản sao của workflow ${detail.name}`);
      await refreshWorkflows(created.id);
      setNotice("Đã nhân bản workflow. Bạn có thể sửa bản sao mà không ảnh hưởng bản gốc.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function saveWorkflowLayout(positions: Record<string, { x: number; y: number }>) {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      const definition: WorkflowDefinition = {
        ...selected.definition,
        nodes: selected.definition.nodes.map((node) => ({
          ...node,
          position: positions[node.id] ?? node.position,
        })),
      };
      await createWorkflowVersion(selected.id, definition);
      await refreshWorkflows(selected.id);
      setNotice("Đã lưu bố cục thành một version mới.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      throw reason;
    } finally { setBusy(false); }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setBusy(true); setError(null);
    try {
      if (target.kind === "workflow") {
        await deleteWorkflowApi(target.id);
        await refreshWorkflows();
        setNotice(`Đã xóa workflow “${target.name}” và dữ liệu riêng của nó.`);
      } else if (target.kind === "run") {
        await performDeleteRun(target.id);
      } else {
        await deleteWorkflowVersion(target.workflowId, target.version);
        await refreshWorkflows(target.workflowId);
        setNotice(`Đã xóa version ${target.version} và lịch sử chạy thuộc version đó.`);
      }
      setDeleteTarget(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  const nodeStatuses = useMemo(
    () => Object.fromEntries((run?.node_runs ?? []).map((node) => [node.node_id, node.status])), [run],
  );

  return (
    <>
      <header className="app-header">
        <div><p className="eyebrow">CTFJudge · phòng chấm bài AI</p><h1>So sánh bài làm với golden solution</h1><p className="subtitle">Tạo quy trình, chạy bằng model local và xem từng câu được đối chiếu như thế nào.</p></div>
        <div className={`status run-${(run?.status ?? "ready").toLowerCase()}`}>{run?.status ?? "READY"}</div>
      </header>
      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="success-banner" role="status"><span>{notice}</span><button onClick={() => setNotice(null)} aria-label="Đóng thông báo">Đóng</button></div>}
      {editorOpen ? <WorkflowEditor
        workflowId={editorWorkflowId}
        initialDefinition={editorSource}
        onCancel={() => setEditorOpen(false)}
        onSaved={async (workflowId) => { setEditorOpen(false); setEditorSource(undefined); setEditorWorkflowId(undefined); await refreshWorkflows(workflowId); setNotice("Đã lưu workflow. Bạn có thể chạy thử ngay bên dưới."); }}
      /> : <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-title"><div><p className="section-label">Bước 1</p><h2>Workflow của bạn</h2></div><button className="text-button" onClick={() => refreshWorkflows()} title="Tải lại danh sách">Làm mới</button></div>
          <p className="sidebar-intro">Chọn một workflow để xem, sửa hoặc chạy. Mỗi workflow giống như một công thức gồm nhiều node.</p>
          <button className="primary-button full" onClick={createRagDemo} disabled={busy}>Tạo workflow chấm bài mẫu</button>
          <button className="secondary-button full editor-button" onClick={() => { setEditorWorkflowId(undefined); setEditorSource(undefined); setEditorOpen(true); }}>Tạo workflow trống</button>
          <div className="workflow-list">
            {workflows.map((workflow) => <article key={workflow.id} className={`workflow-item ${selected?.id === workflow.id ? "selected" : ""}`}>
              <button className="workflow-open" onClick={() => selectWorkflow(workflow.id)} aria-current={selected?.id === workflow.id ? "true" : undefined}>
                <span>{workflow.name}</span><small>Version {workflow.current_version}</small>
              </button>
              <div className="workflow-actions" aria-label={`Thao tác với ${workflow.name}`}>
                <button onClick={() => selectWorkflow(workflow.id)} disabled={busy}>{selected?.id === workflow.id ? "Đang xem" : "Xem"}</button>
                <button onClick={() => editWorkflow(workflow.id)} disabled={busy}>Sửa</button>
                <button onClick={() => duplicateWorkflow(workflow.id)} disabled={busy}>Nhân bản</button>
                <button className="delete" onClick={() => setDeleteTarget({ kind: "workflow", id: workflow.id, name: workflow.name })} disabled={busy}>Xóa</button>
              </div>
            </article>)}
            {!workflows.length && <div className="empty-workflows"><strong>Chưa có workflow</strong><span>Hãy tạo workflow mẫu để chạy thử nhanh nhất.</span></div>}
          </div>
          {!!versions.length && <div className="version-history">
            <h3>Version history</h3>
            {versions.map((version) => <div className={`version-item ${version.is_current ? "current" : ""}`} key={version.id}>
              <div><strong>v{version.version}</strong><small>{new Date(version.created_at).toLocaleString("vi-VN")}</small></div>
              <div className="version-actions">
                {version.is_current ? <span>ACTIVE</span> : <button disabled={busy} onClick={() => activateVersion(version.version)}>Rollback</button>}
                <button
                  className="delete-version"
                  disabled={busy || version.is_current}
                  title={version.is_current ? "Rollback sang version khác trước khi xóa" : `Xóa version ${version.version}`}
                  onClick={() => selected && setDeleteTarget({ kind: "version", workflowId: selected.id, version: version.version, name: `version ${version.version}` })}
                >Xóa</button>
              </div>
            </div>)}
          </div>}
        </aside>
        <div className="main-panel">
          <WorkflowJourney hasWorkflow={Boolean(selected)} hasRun={Boolean(run)} runCompleted={run?.status === "COMPLETED"} />
          <div className="panel-heading"><div><p className="section-label">Workflow graph</p><h2>{selected?.name ?? "No workflow selected"}</h2>{selected && <p className="publish-state">{deployment?.workflow_id === selected.id && deployment.version_number === selected.current_version ? `Đang ở PROD · ID ${selected.id.slice(0, 8)} · v${selected.current_version}` : "Bản cấu hình này chưa được publish lên PROD"}</p>}</div><div className="panel-actions">{run && <code className="run-id">run {run.id.slice(0, 8)}</code>}<button className="primary-button" onClick={publishSelected} disabled={busy || !selected}>Publish lên prod</button></div></div>
          <WorkflowCanvas
            definition={runDefinition ?? selected?.definition}
            nodeStatuses={nodeStatuses}
            onSaveLayout={!runDefinition && selected ? saveWorkflowLayout : undefined}
          />
          {selected && <WorkflowProgress definition={runDefinition ?? selected.definition} run={run} />}
          <NodeGuide />
          <div className="execution-grid">
            <section className="card">
              <div className="card-heading"><div><p className="section-label">Bước 3</p><h2>Dữ liệu cần chấm</h2><p className="card-help">Điền nội dung sau dấu hai chấm, giữ nguyên tên <code>golden</code> và <code>student</code>.</p></div><button className="primary-button" onClick={runWorkflow} disabled={busy || !selected}>{busy ? "Đang chạy…" : "Chạy workflow"}</button></div>
              <RuntimeInputs definition={selected?.definition} value={inputs} onChange={setInputs} />
            </section>
            <section className="card result-card">
              <div className="card-heading"><div><p className="section-label">Bước 4</p><h2>Kết quả chấm bài</h2><p className="card-help">Xem điểm tổng quát trước, sau đó đọc phần so sánh từng câu.</p></div>{run && <span className={`mini-status run-${run.status.toLowerCase()}`}>{run.status}</span>}</div>
              <ComparisonResult run={run} />
            </section>
          </div>
          <section className="node-runs">
            <div className="panel-heading compact"><div><p className="section-label">Execution trace</p><h2>Node runs</h2></div>{run && <span className="muted">Started {formatTime(run.started_at)}</span>}</div>
            <div className="trace-list">
              {(run?.node_runs ?? []).map((node) => <details className={`trace-item trace-${node.status.toLowerCase()}`} key={node.node_id} open={node.status === "FAILED"}><summary><span className="trace-index">{node.sequence + 1}</span><strong>{node.node_id}</strong><span className="node-type">{node.node_type}</span><span className="trace-status">{node.status}</span></summary><div className="trace-body">{node.error && <p className="node-error">{node.error}</p>}<div><h4>Input</h4><pre>{JSON.stringify(node.input_data, null, 2)}</pre></div><div><h4>Output</h4><pre>{JSON.stringify(node.output_data, null, 2)}</pre></div></div></details>)}
              {(run?.node_runs ?? []).length === 0 && <div className="empty-trace">Chạy workflow để xem trace của từng node.</div>}
            </div>
          </section>
          <RunHistory
            runs={runHistory}
            selectedRunId={run?.id}
            busy={busy}
            onOpen={openRun}
            onRetry={retryHistoricalRun}
            onDelete={deleteHistoricalRun}
          />
        </div>
      </section>}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={deleteTarget?.kind === "workflow" ? `Xóa workflow “${deleteTarget.name}”?` : `Xóa ${deleteTarget?.name ?? "mục này"}?`}
        description={deleteTarget?.kind === "workflow"
          ? "Workflow, toàn bộ version, lịch sử chạy và dữ liệu vector riêng sẽ bị xóa. Thao tác này không thể hoàn tác."
          : deleteTarget?.kind === "version"
            ? "Version, các lần chạy và dữ liệu vector riêng thuộc version này sẽ bị xóa. Workflow và version ACTIVE vẫn được giữ lại."
            : "Kết quả chạy và dữ liệu vector riêng của lần chạy này sẽ bị xóa. Workflow vẫn được giữ lại."}
        confirmLabel={deleteTarget?.kind === "workflow" ? "Xóa workflow" : deleteTarget?.kind === "version" ? "Xóa version" : "Xóa lần chạy"}
        busy={busy}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </>
  );
}
