"use client";

import { useEffect, useMemo, useState } from "react";
import { Background, Controls, Edge, MiniMap, NodeChange, Panel, ReactFlow, ReactFlowInstance, useNodesState } from "@xyflow/react";
import type { WorkflowDefinition } from "@/lib/types";
import { savedOrTopologicalPosition, topologicalPositions, WorkflowFlowNode, workflowNodeTypes } from "./WorkflowNodeCard";

type NodePositions = Record<string, { x: number; y: number }>;
type Props = {
  definition?: WorkflowDefinition;
  nodeStatuses?: Record<string, string>;
  onSaveLayout?: (positions: NodePositions) => Promise<void>;
  readOnly?: boolean;
};

function graphNodes(
  definition: WorkflowDefinition | undefined,
  nodeStatuses: Record<string, string>,
  preferSaved: boolean,
): WorkflowFlowNode[] {
  if (!definition) return [];
  const automatic = topologicalPositions(definition);
  return definition.nodes.map((node) => ({
    id: node.id,
    position: preferSaved ? savedOrTopologicalPosition(node, definition, automatic) : automatic[node.id],
    data: {
      label: node.name ?? node.id,
      nodeType: node.type,
      inputMapping: node.inputs ?? {},
      config: node.config,
      status: nodeStatuses[node.id] ?? "idle",
    },
    type: "workflowNode",
  }));
}

export function WorkflowCanvas({ definition, nodeStatuses = {}, onSaveLayout, readOnly = false }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowFlowNode>([]);
  const [instance, setInstance] = useState<ReactFlowInstance<WorkflowFlowNode, Edge> | null>(null);
  const [layoutChanged, setLayoutChanged] = useState(false);
  const [saving, setSaving] = useState(false);
  const edges: Edge[] = useMemo(() => (definition?.edges ?? []).map((edge, index) => ({
    id: `edge-${index}-${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    animated: nodeStatuses[edge.target] === "RUNNING",
  })), [definition, nodeStatuses]);

  useEffect(() => {
    setNodes(graphNodes(definition, {}, true));
    setLayoutChanged(false);
  }, [definition, setNodes]);

  useEffect(() => {
    setNodes((current) => current.map((node) => ({
      ...node,
      data: { ...node.data, status: nodeStatuses[node.id] ?? "idle" },
    })));
  }, [nodeStatuses, setNodes]);

  function handleNodesChange(changes: NodeChange<WorkflowFlowNode>[]) {
    if (changes.some((change) => change.type === "position")) setLayoutChanged(true);
    onNodesChange(changes);
  }

  function autoArrange() {
    setNodes(graphNodes(definition, nodeStatuses, false));
    setLayoutChanged(true);
    requestAnimationFrame(() => instance?.fitView({ padding: 0.18, duration: 300 }));
  }

  async function saveLayout() {
    if (!onSaveLayout) return;
    setSaving(true);
    try {
      await onSaveLayout(Object.fromEntries(nodes.map((node) => [node.id, node.position])));
      setLayoutChanged(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="canvas">
      {nodes.length ? <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={workflowNodeTypes}
        nodesConnectable={false}
        nodesDraggable={!readOnly}
        onNodesChange={handleNodesChange}
        onInit={setInstance}
        fitView
      >
        <Background gap={22} size={1} />
        {!readOnly && <MiniMap pannable zoomable />}
        <Controls showInteractive={false} />
        {!readOnly && <Panel position="top-right" className="graph-toolbar">
          <span>Kéo node để chỉnh vị trí</span>
          <button type="button" onClick={autoArrange}>Sắp xếp tự động</button>
          {onSaveLayout && <button type="button" onClick={saveLayout} disabled={!layoutChanged || saving}>
            {saving ? "Đang lưu…" : "Lưu bố cục"}
          </button>}
        </Panel>}
      </ReactFlow> : <div className="empty-canvas">Chọn hoặc tạo một workflow để xem graph.</div>}
    </div>
  );
}
