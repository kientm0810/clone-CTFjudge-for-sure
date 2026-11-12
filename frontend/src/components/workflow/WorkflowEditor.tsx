"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  NodeMouseHandler,
  ReactFlow,
  ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { createWorkflow, createWorkflowVersion, listAIModelOptions, listVectorCollections } from "@/lib/api";
import type { AIModelOption, NodeType, VectorCollection, WorkflowDefinition, WorkflowNode } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { NodeConfigForm, validateNodeConfig } from "./NodeConfigForm";
import { NodeInputMapping } from "./NodeInputMapping";
import { EditorJourney } from "./WorkflowGuide";
import { savedOrTopologicalPosition, topologicalPositions, WorkflowFlowNode, WorkflowNodeContract, workflowNodeTypes } from "./WorkflowNodeCard";

type Props = {
  workflowId?: string;
  initialDefinition?: WorkflowDefinition;
  onCancel: () => void;
  onSaved: (workflowId: string) => Promise<void> | void;
};

const palette: { type: NodeType; label: string; hint: string }[] = [
  { type: "input", label: "Input", hint: "Cửa nhận dữ liệu đầu vào" },
  { type: "agent", label: "Agent", hint: "Bộ não AI có prompt" },
  { type: "database", label: "Database", hint: "Cất hoặc tìm vector" },
  { type: "output", label: "Output", hint: "Đóng gói kết quả cuối" },
];

const defaultConfigs: Record<NodeType, Record<string, unknown>> = {
  input: { input_key: "input", document_type: "generic" },
  agent: { model: "ollama/qwen2.5:3b", temperature: 0, prompt: "Process the upstream data and return JSON only." },
  database: { operation: "search", collection: "comparison-{{run_id}}", embedding_model: "ollama/nomic-embed-text", top_k: 3, score_threshold: 0.25 },
  output: { format: "json" },
};

function initialGraph(definition?: WorkflowDefinition): { nodes: WorkflowFlowNode[]; edges: Edge[] } {
  const source = definition ?? {
    name: "Untitled workflow",
    version: 1,
    nodes: [
      { id: "input-1", type: "input" as const, name: "Input", inputs: {}, config: defaultConfigs.input },
      { id: "output-1", type: "output" as const, name: "Output", inputs: { result: "{{ steps.input-1.output }}" }, config: defaultConfigs.output },
    ],
    edges: [{ source: "input-1", target: "output-1" }],
  };
  const autoPositions = topologicalPositions(source);
  return {
    nodes: source.nodes.map((node) => ({
      id: node.id,
      position: savedOrTopologicalPosition(node, source, autoPositions),
      data: { label: node.name ?? node.id, nodeType: node.type, inputMapping: structuredClone(node.inputs ?? {}), config: structuredClone(node.config), editable: true },
      type: "workflowNode",
    })),
    edges: source.edges.map((edge, index) => ({ id: `editor-edge-${index}-${edge.source}-${edge.target}`, ...edge })),
  };
}

function nextNodeId(type: NodeType, nodes: WorkflowFlowNode[]): string {
  let counter = 1;
  while (nodes.some((node) => node.id === `${type}-${counter}`)) counter += 1;
  return `${type}-${counter}`;
}

function upstreamNodes(nodeId: string, nodes: WorkflowFlowNode[], edges: Edge[]) {
  const incoming = new Map<string, string[]>();
  for (const edge of edges) {
    const sources = incoming.get(edge.target) ?? [];
    sources.push(edge.source);
    incoming.set(edge.target, sources);
  }
  const found = new Set<string>();
  const queue = [...(incoming.get(nodeId) ?? [])];
  while (queue.length) {
    const current = queue.shift()!;
    if (found.has(current)) continue;
    found.add(current);
    queue.push(...(incoming.get(current) ?? []));
  }
  return nodes
    .filter((node) => found.has(node.id))
    .map((node) => ({ id: node.id, name: node.data.label }));
}

export function WorkflowEditor({ workflowId, initialDefinition, onCancel, onSaved }: Props) {
  const graph = useMemo(() => initialGraph(initialDefinition), [initialDefinition]);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowFlowNode>(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);
  const [instance, setInstance] = useState<ReactFlowInstance<WorkflowFlowNode, Edge> | null>(null);
  const [workflowName, setWorkflowName] = useState(
    initialDefinition ? (workflowId ? initialDefinition.name : `${initialDefinition.name} copy`) : "Untitled workflow",
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [nodeDialogId, setNodeDialogId] = useState<string | null>(null);
  const [dialogConfigText, setDialogConfigText] = useState("");
  const [configPaneWidth, setConfigPaneWidth] = useState(58);
  const [resizingConfigPane, setResizingConfigPane] = useState(false);
  const nodeEditGridRef = useRef<HTMLDivElement | null>(null);
  const [configText, setConfigText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<AIModelOption[]>([]);
  const [collections, setCollections] = useState<VectorCollection[]>([]);
  const [metadataWarning, setMetadataWarning] = useState<string | null>(null);
  const [deleteNodeOpen, setDeleteNodeOpen] = useState(false);

  const selectedNode = nodes.find((node) => node.id === selectedId) ?? null;
  const dialogNode = nodes.find((node) => node.id === nodeDialogId) ?? null;
  useEffect(() => {
    setConfigText(selectedNode ? JSON.stringify(selectedNode.data.config, null, 2) : "");
  }, [selectedNode]);

  useEffect(() => {
    const openNodeSettings = (event: Event) => {
      const nodeId = (event as CustomEvent<{ nodeId: string }>).detail?.nodeId;
      if (!nodeId) return;
      setSelectedId(nodeId);
      setNodeDialogId(nodeId);
    };
    window.addEventListener("workflow-node-edit", openNodeSettings);
    return () => window.removeEventListener("workflow-node-edit", openNodeSettings);
  }, []);

  useEffect(() => {
    setDialogConfigText(dialogNode ? JSON.stringify(dialogNode.data.config, null, 2) : "");
  }, [dialogNode]);

  useEffect(() => {
    if (!resizingConfigPane) return;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    const resize = (event: PointerEvent) => {
      const bounds = nodeEditGridRef.current?.getBoundingClientRect();
      if (!bounds) return;
      const nextWidth = ((event.clientX - bounds.left) / bounds.width) * 100;
      setConfigPaneWidth(Math.min(72, Math.max(42, nextWidth)));
    };
    const stopResizing = () => setResizingConfigPane(false);
    window.addEventListener("pointermove", resize);
    window.addEventListener("pointerup", stopResizing);
    return () => {
      window.removeEventListener("pointermove", resize);
      window.removeEventListener("pointerup", stopResizing);
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
    };
  }, [resizingConfigPane]);

  useEffect(() => {
    Promise.allSettled([listAIModelOptions(), listVectorCollections()]).then(([modelResult, collectionResult]) => {
      const warnings: string[] = [];
      if (modelResult.status === "fulfilled") {
        setModels(modelResult.value.models);
        warnings.push(...modelResult.value.warnings);
      }
      else warnings.push(`Models: ${String(modelResult.reason)}`);
      if (collectionResult.status === "fulfilled") setCollections(collectionResult.value);
      else warnings.push(`Collections: ${String(collectionResult.reason)}`);
      setMetadataWarning(warnings.length ? warnings.join(" · ") : null);
    });
  }, []);

  const onConnect = (connection: Connection) => {
    if (!connection.source || !connection.target || connection.source === connection.target) return;
    const source = nodes.find((node) => node.id === connection.source);
    const target = nodes.find((node) => node.id === connection.target);
    if (!source || !target) return;
    if (source.data.nodeType === "output") {
      setError("Output là node cuối nên không thể nối ra node khác.");
      return;
    }
    if (target.data.nodeType === "input") {
      setError("Input là node bắt đầu nên không thể nhận cạnh đi vào.");
      return;
    }
    if (edges.some((edge) => edge.source === connection.source && edge.target === connection.target)) {
      setError("Hai node này đã được nối.");
      return;
    }
    setError(null);
    setEdges((current) => addEdge({ ...connection, animated: false }, current));
  };

  function addNode(type: NodeType, position?: { x: number; y: number }) {
    setNodes((current) => {
      const id = nextNodeId(type, current);
      return current.concat({
        id,
        position: position ?? { x: 100 + current.length * 28, y: 100 + current.length * 22 },
        data: { label: `${type[0].toUpperCase()}${type.slice(1)}`, nodeType: type, inputMapping: {}, config: structuredClone(defaultConfigs[type]), editable: true },
        type: "workflowNode",
      });
    });
  }

  function updateSelected(updater: (node: WorkflowFlowNode) => WorkflowFlowNode) {
    if (!selectedId) return;
    setNodes((current) => current.map((node) => node.id === selectedId ? updater(node) : node));
  }

  function updateNodeById(nodeId: string, updater: (node: WorkflowFlowNode) => WorkflowFlowNode) {
    setNodes((current) => current.map((node) => node.id === nodeId ? updater(node) : node));
  }

  function applyConfigJson() {
    try {
      const parsed = JSON.parse(configText) as Record<string, unknown>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Config phải là JSON object");
      updateSelected((node) => ({ ...node, data: { ...node.data, config: parsed } }));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  function applyDialogConfigJson() {
    if (!nodeDialogId) return;
    try {
      const parsed = JSON.parse(dialogConfigText) as Record<string, unknown>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Config phải là JSON object");
      updateNodeById(nodeDialogId, (node) => ({ ...node, data: { ...node.data, config: parsed } }));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  function deleteSelected() {
    if (!selectedId) return;
    setNodes((current) => current.filter((node) => node.id !== selectedId));
    setEdges((current) => current.filter((edge) => edge.source !== selectedId && edge.target !== selectedId));
    setSelectedId(null);
    setDeleteNodeOpen(false);
  }

  const onNodeClick: NodeMouseHandler<WorkflowFlowNode> = (_, node) => setSelectedId(node.id);

  async function saveWorkflow() {
    setSaving(true); setError(null);
    try {
      const configErrors = nodes.flatMap((node) =>
        validateNodeConfig(node.data.nodeType, node.data.config).map((message) => `${node.data.label}: ${message}`),
      );
      for (const node of nodes) {
        if (node.data.nodeType !== "input" && !Object.keys(node.data.inputMapping).length) {
          configErrors.push(`${node.data.label}: hãy định nghĩa ít nhất một input mapping.`);
        }
        for (const [key, value] of Object.entries(node.data.inputMapping)) {
          if (!key.trim()) configErrors.push(`${node.data.label}: tên input không được để trống.`);
          if (typeof value === "string" && !value.trim()) configErrors.push(`${node.data.label}: expression của ${key || "input"} không được để trống.`);
        }
      }
      if (configErrors.length) throw new Error(configErrors.join(" "));
      const definition: WorkflowDefinition = {
        name: workflowName.trim() || "Untitled workflow",
        version: 1,
        nodes: nodes.map<WorkflowNode>((node) => ({
          id: node.id,
          type: node.data.nodeType,
          name: node.data.label,
          inputs: node.data.inputMapping,
          config: node.data.config,
          position: node.position,
        })),
        edges: edges.map((edge) => ({ source: edge.source, target: edge.target })),
      };
      const created = workflowId
        ? await createWorkflowVersion(workflowId, definition)
        : await createWorkflow(definition, "Created with the visual workflow editor");
      await onSaved(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setSaving(false); }
  }

  return (
    <section className="editor-shell">
      <div className="editor-toolbar">
        <div><p className="section-label">Trình tạo workflow</p><input className="workflow-name-input" value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} aria-label="Tên workflow" /></div>
        <div className="toolbar-actions"><button className="secondary-button" onClick={onCancel}>Hủy</button><button className="primary-button" onClick={saveWorkflow} disabled={saving}>{saving ? "Đang lưu…" : workflowId ? "Lưu version mới" : "Lưu workflow mới"}</button></div>
      </div>
      <EditorJourney />
      {error && <div className="error-banner editor-error">{error}</div>}
      {metadataWarning && <div className="warning-banner editor-error">Không tải được metadata động: {metadataWarning}. Bạn vẫn có thể dùng Advanced JSON.</div>}
      <div className="editor-layout">
        <aside className="node-palette">
          <p className="section-label">Bước 1</p>
          <h3>Chọn node cần thêm</h3>
          {palette.map((item) => (
            <button
              key={item.type}
              className={`palette-node palette-${item.type}`}
              draggable
              onDragStart={(event) => event.dataTransfer.setData("application/ctfjudge-node", item.type)}
              onClick={() => addNode(item.type)}
            >
              <strong>{item.label}</strong><small>{item.hint}</small>
            </button>
          ))}
          <p className="palette-help"><strong>Cách dễ nhất:</strong> bấm vào node để thêm. Sau đó kéo chấm <b>OUT</b> của node trước tới chấm <b>IN</b> của node sau.</p>
        </aside>
        <div
          className="editor-canvas"
          onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }}
          onDrop={(event) => {
            event.preventDefault();
            const type = event.dataTransfer.getData("application/ctfjudge-node") as NodeType;
            if (!palette.some((item) => item.type === type) || !instance) return;
            addNode(type, instance.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
          }}
        >
          <ReactFlow
            nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} onNodeClick={onNodeClick} onPaneClick={() => setSelectedId(null)} onInit={setInstance}
            nodeTypes={workflowNodeTypes} fitView deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background gap={22} size={1} /><MiniMap pannable zoomable /><Controls />
          </ReactFlow>
        </div>
        <aside className="node-inspector">
          <p className="section-label">Bước 3</p>
          <h3>Cài đặt node</h3>
          {selectedNode ? <>
            <div className={`selected-node-explainer explainer-${selectedNode.data.nodeType}`}>
              <strong>{selectedNode.data.label}</strong>
              <span>Bạn đang sửa node {selectedNode.data.nodeType}. Các thay đổi sẽ được lưu khi bấm nút Lưu phía trên.</span>
            </div>
            <label>ID node<input value={selectedNode.id} disabled /><small className="config-hint">Tên kỹ thuật để hệ thống phân biệt node này.</small></label>
            <label>Tên dễ nhớ<input value={selectedNode.data.label} onChange={(event) => updateSelected((node) => ({ ...node, data: { ...node.data, label: event.target.value } }))} /></label>
            <NodeInputMapping
              type={selectedNode.data.nodeType}
              mapping={selectedNode.data.inputMapping}
              upstreamNodes={upstreamNodes(selectedNode.id, nodes, edges)}
              config={selectedNode.data.config}
              onChange={(inputMapping) => updateSelected((node) => ({ ...node, data: { ...node.data, inputMapping } }))}
            />
            <NodeConfigForm
              type={selectedNode.data.nodeType}
              config={selectedNode.data.config}
              models={models}
              collections={collections}
              onChange={(config) => updateSelected((node) => ({ ...node, data: { ...node.data, config } }))}
            />
            <details className="advanced-config">
              <summary>Cài đặt nâng cao bằng JSON</summary>
              <p className="config-hint">Chỉ cần mở phần này khi bạn đã quen với cấu hình kỹ thuật.</p>
              <label>Config JSON<textarea className="config-editor" value={configText} onChange={(event) => setConfigText(event.target.value)} spellCheck={false} /></label>
              <button className="secondary-button" onClick={applyConfigJson}>Áp dụng JSON</button>
            </details>
            <div className="inspector-actions"><span /><button className="danger-button" onClick={() => setDeleteNodeOpen(true)}>Xóa node</button></div>
          </> : <div className="inspector-empty"><strong>Hãy chọn một node ở giữa</strong><p>Khi bạn bấm vào node, phần này sẽ giải thích từng ô và cho phép sửa tên, prompt hoặc cách lưu/tìm dữ liệu.</p></div>}
        </aside>
      </div>
      {dialogNode && <div className="node-details-backdrop node-edit-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setNodeDialogId(null); }}>
        <section className="node-details-dialog node-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="node-edit-title">
          <header><div><small>{dialogNode.data.nodeType} · CÀI ĐẶT VÀ CẤU TRÚC</small><h2 id="node-edit-title">{dialogNode.data.label}</h2></div><button type="button" onClick={() => setNodeDialogId(null)}>Đóng</button></header>
          <div
            ref={nodeEditGridRef}
            className="node-edit-grid"
            style={{ "--config-pane-width": `${configPaneWidth}%` } as CSSProperties}
          >
            <aside className="node-inspector node-edit-settings">
              <p className="section-label">CÀI ĐẶT NODE</p>
              <div className={`selected-node-explainer explainer-${dialogNode.data.nodeType}`}><strong>{dialogNode.data.label}</strong><span>Các thay đổi được áp dụng ngay vào workflow nháp. Bấm Lưu workflow để lưu version.</span></div>
              <label>ID node<input value={dialogNode.id} disabled /></label>
              <label>Tên dễ nhớ<input value={dialogNode.data.label} onChange={(event) => updateNodeById(dialogNode.id, (node) => ({ ...node, data: { ...node.data, label: event.target.value } }))} /></label>
              <NodeInputMapping type={dialogNode.data.nodeType} mapping={dialogNode.data.inputMapping} upstreamNodes={upstreamNodes(dialogNode.id, nodes, edges)} config={dialogNode.data.config} onChange={(inputMapping) => updateNodeById(dialogNode.id, (node) => ({ ...node, data: { ...node.data, inputMapping } }))} />
              <NodeConfigForm type={dialogNode.data.nodeType} config={dialogNode.data.config} models={models} collections={collections} onChange={(config) => updateNodeById(dialogNode.id, (node) => ({ ...node, data: { ...node.data, config } }))} />
              <details className="advanced-config"><summary>Cài đặt nâng cao bằng JSON</summary><label>Config JSON<textarea className="config-editor" value={dialogConfigText} onChange={(event) => setDialogConfigText(event.target.value)} spellCheck={false} /></label><button className="secondary-button" onClick={applyDialogConfigJson}>Áp dụng JSON</button></details>
              <button className="danger-button" onClick={() => { setSelectedId(dialogNode.id); setNodeDialogId(null); setDeleteNodeOpen(true); }}>Xóa node</button>
            </aside>
            <div
              className={`node-edit-resizer ${resizingConfigPane ? "is-resizing" : ""}`}
              role="separator"
              aria-label="Điều chỉnh chiều rộng phần cài đặt node"
              aria-orientation="vertical"
              aria-valuemin={42}
              aria-valuemax={72}
              aria-valuenow={Math.round(configPaneWidth)}
              tabIndex={0}
              onPointerDown={(event) => { event.preventDefault(); setResizingConfigPane(true); }}
              onDoubleClick={() => setConfigPaneWidth(58)}
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft") { event.preventDefault(); setConfigPaneWidth((width) => Math.max(42, width - 4)); }
                if (event.key === "ArrowRight") { event.preventDefault(); setConfigPaneWidth((width) => Math.min(72, width + 4)); }
                if (event.key === "Home") { event.preventDefault(); setConfigPaneWidth(42); }
                if (event.key === "End") { event.preventDefault(); setConfigPaneWidth(72); }
              }}
            ><span aria-hidden="true" /></div>
            <div className="node-edit-contract"><p className="section-label">NODE NHẬN VÀ TRẢ DỮ LIỆU GÌ?</p><WorkflowNodeContract data={dialogNode.data} /></div>
          </div>
        </section>
      </div>}
      <ConfirmDialog
        open={deleteNodeOpen}
        title={`Xóa node “${selectedNode?.data.label ?? "đã chọn"}”?`}
        description="Node và tất cả đường nối với node này sẽ bị xóa khỏi sơ đồ. Thay đổi chỉ có hiệu lực sau khi bạn lưu workflow."
        confirmLabel="Xóa node"
        onCancel={() => setDeleteNodeOpen(false)}
        onConfirm={deleteSelected}
      />
    </section>
  );
}
