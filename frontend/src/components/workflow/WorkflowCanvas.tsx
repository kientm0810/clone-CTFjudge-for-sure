"use client";

import { Background, Controls, Edge, Node, ReactFlow } from "@xyflow/react";
import type { WorkflowDefinition } from "@/lib/types";

type Props = { definition?: WorkflowDefinition; nodeStatuses?: Record<string, string> };

export function WorkflowCanvas({ definition, nodeStatuses = {} }: Props) {
  const workflowNodes = definition?.nodes ?? [];
  const depthById = Object.fromEntries(workflowNodes.map((node) => [node.id, 0]));
  for (let pass = 0; pass < workflowNodes.length; pass += 1) {
    for (const edge of definition?.edges ?? []) {
      depthById[edge.target] = Math.max(depthById[edge.target] ?? 0, (depthById[edge.source] ?? 0) + 1);
    }
  }
  const layerIndexes: Record<number, number> = {};
  const nodes: Node[] = workflowNodes.map((node) => {
    const depth = depthById[node.id] ?? 0;
    const row = layerIndexes[depth] ?? 0;
    layerIndexes[depth] = row + 1;
    return {
    id: node.id,
    position: { x: 40 + depth * 220, y: 45 + row * 145 },
    data: { label: node.name ?? node.id },
    className: `flow-${node.type} status-${(nodeStatuses[node.id] ?? "idle").toLowerCase()}`,
    };
  });
  const edges: Edge[] = (definition?.edges ?? []).map((edge, index) => ({
    id: `edge-${index}-${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    animated: nodeStatuses[edge.target] === "RUNNING",
  }));

  return (
    <div className="canvas">
      {nodes.length ? <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background gap={22} size={1} />
        <Controls />
      </ReactFlow> : <div className="empty-canvas">Chọn hoặc tạo một workflow để xem graph.</div>}
    </div>
  );
}

