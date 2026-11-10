"use client";

import { useEffect, useMemo, useState } from "react";
import { activateWorkflowVersion, createWorkflow, getRun, getWorkflow, listWorkflows, listWorkflowVersions, startRun } from "@/lib/api";
import type { WorkflowDefinition, WorkflowDetail, WorkflowRun, WorkflowSummary, WorkflowVersionSummary } from "@/lib/types";
import { ComparisonResult } from "./ComparisonResult";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { WorkflowEditor } from "./WorkflowEditor";

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
    summary_score: { type: "number", minimum: 0, maximum: 1 }, summary: { type: "string" },
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
  required: ["summary_score", "summary", "comparisons"],
};

const ragDefinition: WorkflowDefinition = {
  name: "Golden solution RAG comparison",
  version: 1,
  nodes: [
    { id: "golden-input", type: "input", name: "Golden solution", config: { input_key: "golden", document_type: "golden_solution" } },
    {
      id: "golden-parser", type: "agent", name: "Chunk golden",
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: chunkOutputSchema,
        prompt: "You are a deterministic text segmenter. Split the golden solution into short semantic steps without summarizing or adding facts. Copy document_id from the input document. Create stable chunk_id values such as golden-0, golden-1. Return JSON only.",
      },
    },
    {
      id: "golden-index", type: "database", name: "Index golden",
      config: { operation: "upsert", collection: "comparison-{{run_id}}", embedding_model: "ollama/nomic-embed-text" },
    },
    { id: "student-input", type: "input", name: "Student writeup", config: { input_key: "student", document_type: "student_submission" } },
    {
      id: "student-parser", type: "agent", name: "Chunk writeup",
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: chunkOutputSchema,
        prompt: "You are a deterministic text segmenter. Split the student submission into short semantic steps without judging or adding facts. Copy document_id from the input document. Create stable chunk_id values such as student-0, student-1. Return JSON only.",
      },
    },
    {
      id: "golden-search", type: "database", name: "Retrieve evidence",
      config: { operation: "search", collection: "comparison-{{run_id}}", embedding_model: "ollama/nomic-embed-text", top_k: 3, score_threshold: 0.25 },
    },
    {
      id: "comparison-agent", type: "agent", name: "Similarity judge",
      config: {
        model: "ollama/qwen2.5:3b", temperature: 0, output_schema: comparisonOutputSchema,
        prompt: "Judge every student chunk against its retrieved golden candidates. Similar wording alone is not proof of correctness. Preserve student_content exactly. Put only genuinely relevant candidates in matched_golden and copy their IDs, content, and similarity scores. Classify each chunk, assign score from 0 to 1, explain briefly in Vietnamese, then calculate summary_score as the average. Return JSON only.",
      },
    },
    { id: "report", type: "output", name: "Comparison report", config: { format: "comparison_report" } },
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

  async function selectWorkflow(id: string) {
    setError(null);
    const [detail, history] = await Promise.all([getWorkflow(id), listWorkflowVersions(id)]);
    setSelected(detail);
    setVersions(history);
    setInputs(JSON.stringify(sampleInputs(detail.definition), null, 2));
    setRun(null);
  }

  async function activateVersion(version: number) {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      await activateWorkflowVersion(selected.id, version);
      await refreshWorkflows(selected.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function refreshWorkflows(preferredId?: string) {
    const items = await listWorkflows();
    setWorkflows(items);
    const nextId = preferredId ?? selected?.id ?? items[0]?.id;
    if (nextId) await selectWorkflow(nextId);
  }

  useEffect(() => {
    refreshWorkflows().catch((reason) => setError(String(reason)));
    // Initial data load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createRagDemo() {
    setBusy(true); setError(null);
    try {
      const created = await createWorkflow(ragDefinition, "RAG comparison sử dụng Ollama và pgvector");
      await refreshWorkflows(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function runWorkflow() {
    if (!selected) return;
    setBusy(true); setError(null); setRun(null);
    try {
      const parsedInputs = JSON.parse(inputs) as Record<string, unknown>;
      let current = await startRun(selected.id, parsedInputs);
      setRun(current);
      for (let attempt = 0; attempt < 180; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        current = await getRun(current.id); setRun(current);
        if (["COMPLETED", "FAILED", "CANCELLED"].includes(current.status)) break;
      }
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
        <div><p className="eyebrow">CTFJudge · local workflow lab</p><h1>Golden solution comparison</h1><p className="subtitle">Chunk, vector search và đánh giá writeup bằng Ollama local.</p></div>
        <div className={`status run-${(run?.status ?? "ready").toLowerCase()}`}>{run?.status ?? "READY"}</div>
      </header>
      {error && <div className="error-banner">{error}</div>}
      {editorOpen ? <WorkflowEditor
        workflowId={editorWorkflowId}
        initialDefinition={editorSource}
        onCancel={() => setEditorOpen(false)}
        onSaved={async (workflowId) => { setEditorOpen(false); setEditorSource(undefined); setEditorWorkflowId(undefined); await refreshWorkflows(workflowId); }}
      /> : <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-title"><h2>Workflows</h2><button className="icon-button" onClick={() => refreshWorkflows()} title="Làm mới">↻</button></div>
          <button className="primary-button full" onClick={createRagDemo} disabled={busy}>+ Tạo workflow RAG</button>
          <button className="secondary-button full editor-button" onClick={() => { setEditorWorkflowId(undefined); setEditorSource(undefined); setEditorOpen(true); }}>+ Workflow trống</button>
          <button className="secondary-button full editor-button" disabled={!selected} onClick={() => { setEditorWorkflowId(selected?.id); setEditorSource(selected?.definition); setEditorOpen(true); }}>Sửa & tạo version</button>
          <div className="workflow-list">
            {workflows.map((workflow) => <button key={workflow.id} className={`workflow-item ${selected?.id === workflow.id ? "selected" : ""}`} onClick={() => selectWorkflow(workflow.id)}><span>{workflow.name}</span><small>v{workflow.current_version}</small></button>)}
            {!workflows.length && <p className="muted">Chưa có workflow.</p>}
          </div>
          {!!versions.length && <div className="version-history">
            <h3>Version history</h3>
            {versions.map((version) => <div className={`version-item ${version.is_current ? "current" : ""}`} key={version.id}>
              <div><strong>v{version.version}</strong><small>{new Date(version.created_at).toLocaleString("vi-VN")}</small></div>
              {version.is_current ? <span>ACTIVE</span> : <button disabled={busy} onClick={() => activateVersion(version.version)}>Rollback</button>}
            </div>)}
          </div>}
          <div className="legend"><h3>Node types</h3><span><i className="dot input" />Input</span><span><i className="dot agent" />Agent</span><span><i className="dot database" />Database</span><span><i className="dot output" />Output</span></div>
        </aside>
        <div className="main-panel">
          <div className="panel-heading"><div><p className="section-label">Workflow graph</p><h2>{selected?.name ?? "No workflow selected"}</h2></div>{run && <code className="run-id">run {run.id.slice(0, 8)}</code>}</div>
          <WorkflowCanvas definition={selected?.definition} nodeStatuses={nodeStatuses} />
          <div className="execution-grid">
            <section className="card">
              <div className="card-heading"><div><p className="section-label">Runtime</p><h2>Golden & student input</h2></div><button className="primary-button" onClick={runWorkflow} disabled={busy || !selected}>{busy ? "Đang chạy…" : "▶ Run workflow"}</button></div>
              <textarea value={inputs} onChange={(event) => setInputs(event.target.value)} spellCheck={false} />
            </section>
            <section className="card result-card">
              <div className="card-heading"><div><p className="section-label">Result</p><h2>Similarity report</h2></div>{run && <span className={`mini-status run-${run.status.toLowerCase()}`}>{run.status}</span>}</div>
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
        </div>
      </section>}
    </>
  );
}
