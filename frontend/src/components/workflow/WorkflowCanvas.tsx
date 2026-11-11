"use client";

import { Background, Controls, Edge, MiniMap, ReactFlow } from "@xyflow/react";
import type { WorkflowDefinition } from "@/lib/types";
import { savedOrDefaultPosition, WorkflowFlowNode, workflowNodeTypes } from "./WorkflowNodeCard";

type Props = { definition?: WorkflowDefinition; nodeStatuses?: Record<string, string> };

export function WorkflowCanvas({ definition, nodeStatuses = {} }: Props) {
  const workflowNodes = definition?.nodes ?? [];
  const nodes: WorkflowFlowNode[] = workflowNodes.map((node, index) => ({
    id: node.id,
    position: savedOrDefaultPosition(node, index),
    data: {
      label: node.name ?? node.id,
      nodeType: node.type,
      config: node.config,
      status: nodeStatuses[node.id] ?? "idle",
    },
    type: "workflowNode",
  }));
  const edges: Edge[] = (definition?.edges ?? []).map((edge, index) => ({
    id: `edge-${index}-${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    animated: nodeStatuses[edge.target] === "RUNNING",
  }));

  return (
    <div className="canvas">
      {nodes.length ? <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={workflowNodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        fitView
      >
        <Background gap={22} size={1} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
      </ReactFlow> : <div className="empty-canvas">Chọn hoặc tạo một workflow để xem graph.</div>}
    </div>
  );
}
