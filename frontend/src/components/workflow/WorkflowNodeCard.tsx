"use client";

import { Handle, Node, NodeProps, Position } from "@xyflow/react";
import type { NodeType, WorkflowNode } from "@/lib/types";

export type WorkflowNodeData = {
  label: string;
  nodeType: NodeType;
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

export function savedOrDefaultPosition(node: WorkflowNode, index: number) {
  return node.position ?? {
    x: 80 + (index % 4) * 220,
    y: 70 + Math.floor(index / 4) * 150,
  };
}
