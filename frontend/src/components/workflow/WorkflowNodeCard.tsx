"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Handle, Node, NodeProps, Position } from "@xyflow/react";
import type { NodeType, WorkflowDefinition, WorkflowNode } from "@/lib/types";

export type WorkflowNodeData = {
  label: string;
  nodeType: NodeType;
  inputMapping: Record<string, unknown>;
  config: Record<string, unknown>;
  status?: string;
};

export type WorkflowFlowNode = Node<WorkflowNodeData>;

type ContractField = { name: string; type: string; detail?: string };
type NodeContract = { purpose: string; inputs: ContractField[]; use: string; outputs: ContractField[] };

function mappedFields(data: WorkflowNodeData): ContractField[] {
  return Object.entries(data.inputMapping ?? {}).map(([key, raw]) => {
    const expression = typeof raw === "string" ? raw : JSON.stringify(raw);
    const isChunks = /\.chunks\s*}}/.test(expression);
    const isRetrieval = /retrieval_results/.test(expression);
    return {
      name: key,
      type: isChunks ? "array<object>" : isRetrieval ? "array<retrieval_result>" : "theo output nguồn",
      detail: expression,
    };
  });
}

function nodeContract(data: WorkflowNodeData): NodeContract {
  const mapping = mappedFields(data);
  if (data.nodeType === "input") {
    const key = String(data.config.input_key ?? data.label);
    return {
      purpose: "Nhận dữ liệu người dùng khi chạy workflow.",
      inputs: [{ name: `runtime.${key}`, type: "string", detail: "Văn bản người dùng nhập" }],
      use: `Đọc trường “${key}” rồi đóng gói nội dung thành document.`,
      outputs: [
        { name: "document_id", type: "string" },
        { name: "document_type", type: "string" },
        { name: "content", type: "string" },
        { name: "metadata", type: "object" },
      ],
    };
  }
  if (data.nodeType === "agent") {
    const schema = data.config.output_schema as { properties?: Record<string, unknown> } | undefined;
    const fields = Object.keys(schema?.properties ?? {});
    return {
      purpose: "Gửi prompt và dữ liệu đầu vào cho model.",
      inputs: mapping.length ? mapping : ["Chưa cấu hình input mapping"],
      use: `Model ${String(data.config.model ?? "default")} xử lý dữ liệu theo prompt đã cấu hình.`,
      outputs: fields.length ? fields.map((field) => ({ name: field, type: "theo schema đã cấu hình" })) : [{ name: "JSON do model trả về", type: "object" }],
    };
  }
  if (data.nodeType === "database") {
    const upsert = data.config.operation === "upsert";
    const collection = String(data.config.collection ?? "golden-solutions");
    const model = String(data.config.embedding_model ?? "embedding mặc định");
    return {
      purpose: upsert ? "Lưu các chunk dưới dạng vector." : "Tìm các chunk gần nhất trong vector collection.",
      inputs: mapping.length ? mapping : [{
        name: upsert ? "chunks" : "query_chunks",
        type: "array<object>",
        detail: "Mỗi object gồm chunk_id:string, content:string, document_id:string, metadata:object",
      }],
      use: upsert
        ? `Với từng chunk: lấy content, tạo embedding bằng ${model}, rồi lưu text và vector vào collection “${collection}”.`
        : `Với từng query chunk: lấy content, tạo embedding bằng ${model}, tìm top ${String(data.config.top_k ?? 5)} trong “${collection}” và bỏ kết quả dưới ngưỡng ${String(data.config.score_threshold ?? 0.4)}. Mỗi query tạo một retrieval result tương ứng.`,
      outputs: upsert
        ? [
            { name: "collection", type: "string" },
            { name: "indexed_chunks", type: "integer" },
            { name: "embedding_model", type: "string" },
          ]
        : [
            { name: "retrieval_results", type: "array<object>", detail: "Một phần tử cho mỗi query chunk" },
            { name: "student_chunk_id", type: "string", detail: "ID query chunk" },
            { name: "student_content", type: "string", detail: "Nội dung query chunk" },
            { name: "candidates", type: "array<object>", detail: "golden_chunk_id:string, content:string, similarity_score:number" },
          ],
    };
  }
  const format = String(data.config.format ?? "json");
  return {
    purpose: "Gom các giá trị đã map thành kết quả workflow.",
    inputs: mapping.length ? mapping : ["Chưa cấu hình input mapping"],
    use: format === "comparison_report" ? "Chuẩn hóa similarity report và gắn golden evidence với từng student chunk." : `Đóng gói output theo format “${format}”.`,
    outputs: format === "comparison_report"
      ? [
          { name: "report_type", type: '"similarity"' },
          { name: "golden_chunks", type: "array<chunk>" },
          { name: "similarity_score", type: "number · 0–1" },
          { name: "summary_score", type: "number · 0–1" },
          { name: "comparisons", type: "array<student_chunk_comparison>" },
        ]
      : [{ name: "các field đã map", type: "giữ nguyên kiểu dữ liệu" }],
  };
}

export function WorkflowNodeCard({ data, selected, isConnectable }: NodeProps<WorkflowFlowNode>) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const status = (data.status ?? "idle").toLowerCase();
  const contract = nodeContract(data);
  useEffect(() => {
    if (!detailsOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDetailsOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [detailsOpen]);
  return (
    <div className={`builder-node builder-${data.nodeType} status-${status} ${selected ? "builder-selected" : ""}`}>
      {data.nodeType !== "input" && <Handle id="input" type="target" position={Position.Left} isConnectable={isConnectable} />}
      <small>{data.nodeType}</small>
      <strong title={data.label}>{data.label}</strong>
      <button
        type="button"
        className="node-info-cue"
        aria-label={`Xem input và output của ${data.label}`}
        aria-haspopup="dialog"
        aria-expanded={detailsOpen}
        onClick={(event) => { event.stopPropagation(); setDetailsOpen(true); }}
      >i</button>
      {detailsOpen && typeof document !== "undefined" && createPortal(
        <div className="node-details-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailsOpen(false); }}>
          <section className="node-details-dialog" role="dialog" aria-modal="true" aria-labelledby={`node-details-title-${data.id}`}>
            <header><div><small>{data.nodeType} · CẤU TRÚC DỮ LIỆU</small><h2 id={`node-details-title-${data.id}`}>{data.label}</h2></div><button type="button" onClick={() => setDetailsOpen(false)} aria-label="Đóng phần giải thích">Đóng</button></header>
            <p className="node-details-purpose">{contract.purpose}</p>
            <section><h3>Input node nhận</h3>{contract.inputs.map((field) => <div className="node-contract-field" key={field.name}><span><code>{field.name}</code><em>{field.type}</em></span>{field.detail && <small>{field.detail}</small>}</div>)}</section>
            <section><h3>Cách node xử lý input</h3><p>{contract.use}</p></section>
            <section><h3>Output node trả về</h3>{contract.outputs.map((field) => <div className="node-contract-field" key={field.name}><span><code>{field.name}</code><em>{field.type}</em></span>{field.detail && <small>{field.detail}</small>}</div>)}</section>
            <footer>Dữ liệu này được lấy từ input mapping và cấu hình hiện tại của node.</footer>
          </section>
        </div>,
        document.body,
      )}
      {data.nodeType !== "output" && <Handle id="output" type="source" position={Position.Right} isConnectable={isConnectable} />}
    </div>
  );
}

export const workflowNodeTypes = { workflowNode: WorkflowNodeCard };

export function topologicalPositions(definition: WorkflowDefinition): Record<string, { x: number; y: number }> {
  const nodeIds = definition.nodes.map((node) => node.id);
  const originalOrder = new Map(nodeIds.map((id, index) => [id, index]));
  const indegree = Object.fromEntries(nodeIds.map((id) => [id, 0]));
  const outgoing = Object.fromEntries(nodeIds.map((id) => [id, [] as string[]]));
  const depth = Object.fromEntries(nodeIds.map((id) => [id, 0]));

  for (const edge of definition.edges) {
    if (!(edge.source in outgoing) || !(edge.target in indegree)) continue;
    outgoing[edge.source].push(edge.target);
    indegree[edge.target] += 1;
  }

  const queue = nodeIds.filter((id) => indegree[id] === 0);
  const ordered: string[] = [];
  while (queue.length) {
    queue.sort((a, b) => (originalOrder.get(a) ?? 0) - (originalOrder.get(b) ?? 0));
    const current = queue.shift()!;
    ordered.push(current);
    for (const target of outgoing[current]) {
      depth[target] = Math.max(depth[target], depth[current] + 1);
      indegree[target] -= 1;
      if (indegree[target] === 0) queue.push(target);
    }
  }

  for (const id of nodeIds) {
    if (!ordered.includes(id)) ordered.push(id);
  }
  const layers = new Map<number, string[]>();
  for (const id of ordered) {
    const layer = layers.get(depth[id]) ?? [];
    layer.push(id);
    layers.set(depth[id], layer);
  }
  const widestLayer = Math.max(1, ...Array.from(layers.values(), (layer) => layer.length));
  const positions: Record<string, { x: number; y: number }> = {};
  for (const [layerIndex, layer] of layers) {
    const verticalOffset = ((widestLayer - layer.length) * 150) / 2;
    layer.forEach((id, row) => {
      positions[id] = { x: 80 + layerIndex * 220, y: 70 + verticalOffset + row * 150 };
    });
  }
  return positions;
}

export function savedOrTopologicalPosition(
  node: WorkflowNode,
  definition: WorkflowDefinition,
  positions = topologicalPositions(definition),
) {
  return node.position ?? positions[node.id] ?? { x: 80, y: 70 };
}
