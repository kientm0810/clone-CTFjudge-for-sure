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

export function WorkflowNodeCard({ data, selected, isConnectable }: NodeProps<WorkflowFlowNode>) {
  const status = (data.status ?? "idle").toLowerCase();
  return (
    <div className={`builder-node builder-${data.nodeType} status-${status} ${selected ? "builder-selected" : ""}`}>
      {data.nodeType !== "input" && <Handle id="input" type="target" position={Position.Left} isConnectable={isConnectable} />}
      <small>{data.nodeType}</small>
      <strong title={data.label}>{data.label}</strong>
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
