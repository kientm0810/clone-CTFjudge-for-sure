import type { WorkflowDefinition, WorkflowRun } from "@/lib/types";

const statusLabels: Record<string, string> = {
  idle: "Chờ chạy",
  PENDING: "Chờ chạy",
  RUNNING: "Đang chạy",
  COMPLETED: "Hoàn tất",
  FAILED: "Có lỗi",
  CANCELLED: "Đã dừng",
};

function topologicalNodeIds(definition: WorkflowDefinition): string[] {
  const indegree = Object.fromEntries(definition.nodes.map((node) => [node.id, 0]));
  const outgoing = Object.fromEntries(definition.nodes.map((node) => [node.id, [] as string[]]));
  for (const edge of definition.edges) {
    if (edge.target in indegree && edge.source in outgoing) {
      indegree[edge.target] += 1;
      outgoing[edge.source].push(edge.target);
    }
  }
  const queue = definition.nodes.filter((node) => indegree[node.id] === 0).map((node) => node.id);
  const result: string[] = [];
  while (queue.length) {
    const id = queue.shift()!;
    result.push(id);
    for (const target of outgoing[id]) {
      indegree[target] -= 1;
      if (indegree[target] === 0) queue.push(target);
    }
  }
  return result.length === definition.nodes.length ? result : definition.nodes.map((node) => node.id);
}

export function WorkflowProgress({ definition, run }: { definition: WorkflowDefinition; run: WorkflowRun | null }) {
  const order = topologicalNodeIds(definition);
  const nodes = Object.fromEntries(definition.nodes.map((node) => [node.id, node]));
  const statuses = Object.fromEntries((run?.node_runs ?? []).map((node) => [node.node_id, node.status]));
  const completed = Object.values(statuses).filter((status) => status === "COMPLETED").length;
  const percent = Math.round((completed / Math.max(order.length, 1)) * 100);
  const current = order.find((id) => statuses[id] === "RUNNING");
  const message = run?.status === "COMPLETED"
    ? "Workflow đã hoàn tất."
    : run?.status === "FAILED"
      ? "Workflow dừng vì có lỗi."
      : current
        ? `Đang chạy: ${nodes[current]?.name ?? current}.`
        : run
          ? "Đang chuẩn bị workflow."
          : "Workflow chưa chạy.";

  return <div className="workflow-progress">
    <div className="progress-summary" role="status" aria-atomic="true"><div><strong>{message}</strong><span>{completed}/{order.length} node hoàn tất</span></div><b>{run ? percent : 0}%</b></div>
    <div className="progress-track" aria-hidden="true"><span style={{ width: `${run ? percent : 0}%` }} /></div>
    <ol>{order.map((id, index) => {
      const status = statuses[id] ?? "idle";
      return <li className={`progress-${status.toLowerCase()}`} key={id}><span>{index + 1}</span><div><strong>{nodes[id]?.name ?? id}</strong><small>{statusLabels[status] ?? status}</small></div></li>;
    })}</ol>
  </div>;
}
