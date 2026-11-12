"use client";

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

function nodeContract(data: WorkflowNodeData): { purpose: string; inputs: string[]; use: string; outputs: string[] } {
  const mapping = Object.entries(data.inputMapping ?? {}).map(([key, value]) =>
    `${key} ← ${typeof value === "string" ? value : JSON.stringify(value)}`,
  );
  if (data.nodeType === "input") {
    const key = String(data.config.input_key ?? data.label);
    return {
      purpose: "Nhận dữ liệu người dùng khi chạy workflow.",
      inputs: [`runtime.${key}`],
      use: `Đọc trường “${key}” rồi đóng gói nội dung thành document.`,
      outputs: ["document_id", "document_type", "content", "metadata"],
    };
  }
  if (data.nodeType === "agent") {
    const schema = data.config.output_schema as { properties?: Record<string, unknown> } | undefined;
    const fields = Object.keys(schema?.properties ?? {});
    return {
      purpose: "Gửi prompt và dữ liệu đầu vào cho model.",
      inputs: mapping.length ? mapping : ["Chưa cấu hình input mapping"],
      use: `Model ${String(data.config.model ?? "default")} xử lý dữ liệu theo prompt đã cấu hình.`,
      outputs: fields.length ? fields : ["JSON do model trả về"],
    };
  }
  if (data.nodeType === "database") {
    const upsert = data.config.operation === "upsert";
    const collection = String(data.config.collection ?? "golden-solutions");
    const model = String(data.config.embedding_model ?? "embedding mặc định");
    return {
      purpose: upsert ? "Lưu các chunk dưới dạng vector." : "Tìm các chunk gần nhất trong vector collection.",
      inputs: mapping.length ? mapping : [upsert ? "chunks: danh sách chunk cần lưu" : "query_chunks: chunk dùng để tìm kiếm"],
      use: upsert
        ? `Tạo embedding bằng ${model}, rồi lưu nội dung và vector vào collection “${collection}”.`
        : `Tạo embedding cho từng query, tìm top ${String(data.config.top_k ?? 5)} trong “${collection}”, bỏ kết quả dưới ngưỡng ${String(data.config.score_threshold ?? 0.4)}.`,
      outputs: upsert
        ? ["collection", "indexed_chunks", "embedding_model"]
        : ["retrieval_results[]", "student_chunk_id", "student_content", "candidates[]: golden_chunk_id, content, similarity_score"],
    };
  }
  const format = String(data.config.format ?? "json");
  return {
    purpose: "Gom các giá trị đã map thành kết quả workflow.",
    inputs: mapping.length ? mapping : ["Chưa cấu hình input mapping"],
    use: format === "comparison_report" ? "Chuẩn hóa similarity report và gắn golden evidence với từng student chunk." : `Đóng gói output theo format “${format}”.`,
    outputs: format === "comparison_report"
      ? ["report_type", "golden_chunks[]", "similarity_score", "summary_score", "comparisons[]"]
      : ["Các field đã khai báo trong Input mapping"],
  };
}

export function WorkflowNodeCard({ data, selected, isConnectable }: NodeProps<WorkflowFlowNode>) {
  const status = (data.status ?? "idle").toLowerCase();
  const contract = nodeContract(data);
  return (
    <div className={`builder-node builder-${data.nodeType} status-${status} ${selected ? "builder-selected" : ""}`}>
      {data.nodeType !== "input" && <Handle id="input" type="target" position={Position.Left} isConnectable={isConnectable} />}
      <small>{data.nodeType}</small>
      <strong title={data.label}>{data.label}</strong>
      <span className="node-info-cue" aria-hidden="true">i</span>
      <aside className="node-contract-tooltip" role="tooltip">
        <strong>{data.label}</strong>
        <p>{contract.purpose}</p>
        <section><b>INPUT THỰC TẾ</b>{contract.inputs.map((item, index) => <code key={`${item}-${index}`}>{item}</code>)}</section>
        <p><b>Node dùng input thế nào?</b><br />{contract.use}</p>
        <section><b>OUTPUT</b>{contract.outputs.map((item) => <code key={item}>{item}</code>)}</section>
        <small>Chọn node để chỉnh Input mapping và cấu hình.</small>
      </aside>
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
