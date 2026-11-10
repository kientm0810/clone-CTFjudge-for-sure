"use client";

import { useEffect, useMemo, useState } from "react";
import {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  Handle,
  MiniMap,
  Node,
  NodeMouseHandler,
  NodeProps,
  Position,
  ReactFlow,
  ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { createWorkflow, createWorkflowVersion } from "@/lib/api";
import type { NodeType, WorkflowDefinition, WorkflowNode } from "@/lib/types";

type EditorNodeData = {
  label: string;
  nodeType: NodeType;
  config: Record<string, unknown>;
};

type Props = {
  workflowId?: string;
  initialDefinition?: WorkflowDefinition;
  onCancel: () => void;
  onSaved: (workflowId: string) => Promise<void> | void;
};

function BuilderNode({ data, selected }: NodeProps<Node<EditorNodeData>>) {
  return (
    <div className={`builder-node builder-${data.nodeType} ${selected ? "builder-selected" : ""}`}>
      {data.nodeType !== "input" && <Handle id="input" type="target" position={Position.Left} />}
      <small>{data.nodeType}</small>
      <strong>{data.label}</strong>
      {data.nodeType !== "output" && <Handle id="output" type="source" position={Position.Right} />}
    </div>
  );
}

const editorNodeTypes = { workflowNode: BuilderNode };

const palette: { type: NodeType; label: string; hint: string }[] = [
  { type: "input", label: "Input", hint: "Runtime document" },
  { type: "agent", label: "Agent", hint: "Model + prompt" },
  { type: "database", label: "Database", hint: "Vector upsert/search" },
  { type: "output", label: "Output", hint: "Final result" },
];

const defaultConfigs: Record<NodeType, Record<string, unknown>> = {
  input: { input_key: "input", document_type: "generic" },
  agent: { model: "ollama/qwen2.5:3b", temperature: 0, prompt: "Process the upstream data and return JSON only." },
  database: { operation: "search", collection: "comparison-{{run_id}}", embedding_model: "ollama/nomic-embed-text", top_k: 3, score_threshold: 0.25 },
  output: { format: "json" },
};

function initialGraph(definition?: WorkflowDefinition): { nodes: Node<EditorNodeData>[]; edges: Edge[] } {
  const source = definition ?? {
    name: "Untitled workflow",
    version: 1,
    nodes: [
      { id: "input-1", type: "input" as const, name: "Input", config: defaultConfigs.input },
      { id: "output-1", type: "output" as const, name: "Output", config: defaultConfigs.output },
    ],
    edges: [{ source: "input-1", target: "output-1" }],
  };
  return {
    nodes: source.nodes.map((node, index) => ({
      id: node.id,
      position: { x: 80 + (index % 4) * 220, y: 70 + Math.floor(index / 4) * 150 },
      data: { label: node.name ?? node.id, nodeType: node.type, config: structuredClone(node.config) },
      type: "workflowNode",
    })),
    edges: source.edges.map((edge, index) => ({ id: `editor-edge-${index}-${edge.source}-${edge.target}`, ...edge })),
  };
}

function nextNodeId(type: NodeType, nodes: Node<EditorNodeData>[]): string {
  let counter = 1;
  while (nodes.some((node) => node.id === `${type}-${counter}`)) counter += 1;
  return `${type}-${counter}`;
}

export function WorkflowEditor({ workflowId, initialDefinition, onCancel, onSaved }: Props) {
  const graph = useMemo(() => initialGraph(initialDefinition), [initialDefinition]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<EditorNodeData>>(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);
  const [instance, setInstance] = useState<ReactFlowInstance<Node<EditorNodeData>, Edge> | null>(null);
  const [workflowName, setWorkflowName] = useState(
    initialDefinition ? (workflowId ? initialDefinition.name : `${initialDefinition.name} copy`) : "Untitled workflow",
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [configText, setConfigText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedNode = nodes.find((node) => node.id === selectedId) ?? null;
  useEffect(() => {
    setConfigText(selectedNode ? JSON.stringify(selectedNode.data.config, null, 2) : "");
  }, [selectedNode]);

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
        data: { label: `${type[0].toUpperCase()}${type.slice(1)}`, nodeType: type, config: structuredClone(defaultConfigs[type]) },
        type: "workflowNode",
      });
    });
  }

  function updateSelected(updater: (node: Node<EditorNodeData>) => Node<EditorNodeData>) {
    if (!selectedId) return;
    setNodes((current) => current.map((node) => node.id === selectedId ? updater(node) : node));
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

  function deleteSelected() {
    if (!selectedId) return;
    setNodes((current) => current.filter((node) => node.id !== selectedId));
    setEdges((current) => current.filter((edge) => edge.source !== selectedId && edge.target !== selectedId));
    setSelectedId(null);
  }

  const onNodeClick: NodeMouseHandler<Node<EditorNodeData>> = (_, node) => setSelectedId(node.id);

  async function saveWorkflow() {
    setSaving(true); setError(null);
    try {
      let pendingConfig: Record<string, unknown> | null = null;
      if (selectedNode) {
        pendingConfig = JSON.parse(configText) as Record<string, unknown>;
        if (!pendingConfig || typeof pendingConfig !== "object" || Array.isArray(pendingConfig)) {
          throw new Error("Config phải là JSON object");
        }
      }
      const definition: WorkflowDefinition = {
        name: workflowName.trim() || "Untitled workflow",
        version: 1,
        nodes: nodes.map<WorkflowNode>((node) => ({
          id: node.id,
          type: node.data.nodeType,
          name: node.data.label,
          config: node.id === selectedId && pendingConfig ? pendingConfig : node.data.config,
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
        <div><p className="section-label">Visual builder</p><input className="workflow-name-input" value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} aria-label="Workflow name" /></div>
        <div className="toolbar-actions"><button className="secondary-button" onClick={onCancel}>Hủy</button><button className="primary-button" onClick={saveWorkflow} disabled={saving}>{saving ? "Đang lưu…" : workflowId ? "Lưu version mới" : "Lưu workflow mới"}</button></div>
      </div>
      {error && <div className="error-banner editor-error">{error}</div>}
      <div className="editor-layout">
        <aside className="node-palette">
          <h3>Nodes</h3>
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
          <p className="palette-help">Kéo node vào canvas hoặc click để thêm. Kéo từ handle bên phải sang handle bên trái để nối.</p>
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
            nodeTypes={editorNodeTypes} fitView deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background gap={22} size={1} /><MiniMap pannable zoomable /><Controls />
          </ReactFlow>
        </div>
        <aside className="node-inspector">
          <h3>Node settings</h3>
          {selectedNode ? <>
            <label>ID<input value={selectedNode.id} disabled /></label>
            <label>Name<input value={selectedNode.data.label} onChange={(event) => updateSelected((node) => ({ ...node, data: { ...node.data, label: event.target.value } }))} /></label>
            {selectedNode.data.nodeType === "agent" && <label>Prompt<textarea value={String(selectedNode.data.config.prompt ?? "")} onChange={(event) => updateSelected((node) => ({ ...node, data: { ...node.data, config: { ...node.data.config, prompt: event.target.value } } }))} /></label>}
            <label>Config JSON<textarea className="config-editor" value={configText} onChange={(event) => setConfigText(event.target.value)} spellCheck={false} /></label>
            <div className="inspector-actions"><button className="secondary-button" onClick={applyConfigJson}>Apply config</button><button className="danger-button" onClick={deleteSelected}>Xóa node</button></div>
          </> : <p className="muted inspector-empty">Chọn một node để sửa tên, prompt và config.</p>}
        </aside>
      </div>
    </section>
  );
}
