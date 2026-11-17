import type { ExecutionProgress, WorkflowDefinition, WorkflowRun } from "@/lib/types";

const statusLabels: Record<string, string> = {
  idle: "Chờ chạy",
  PENDING: "Chờ chạy",
  RUNNING: "Đang chạy",
  COMPLETED: "Hoàn tất",
  FAILED: "Có lỗi",
  CANCELLED: "Đã dừng",
  FROZEN: "Đã freeze",
};

const stageLabels: Record<string, string> = {
  STARTING: "Đang chuẩn bị node",
  LOADING_PROMPT: "Đang nạp prompt",
  GENERATING: "Đang sinh kết quả",
  PARSING: "Đang parse JSON",
  COMPLETED: "Đã hoàn tất",
  FAILED: "Có lỗi khi chạy",
};

function formatElapsed(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(safeSeconds % 60).padStart(2, "0")}`;
}

export function ExecutionTelemetry({ progress, nodeName }: {
  progress?: ExecutionProgress | null;
  nodeName?: string;
}) {
  if (!progress) return null;
  const maxTokens = progress.max_tokens ?? 0;
  const tokenPercent = maxTokens > 0
    ? Math.min(100, Math.round((progress.generated_tokens / maxTokens) * 100))
    : 0;
  const heartbeat = new Date(progress.heartbeat_at).toLocaleTimeString("vi-VN");

  return <section className={`execution-telemetry telemetry-${progress.stage.toLowerCase()}`} role="status" aria-atomic="true">
    <div className="telemetry-heading">
      <div>
        <small>{nodeName ? `Node: ${nodeName}` : "Tiến trình AI"}</small>
        <strong>{stageLabels[progress.stage] ?? progress.message}</strong>
      </div>
      <b>{formatElapsed(progress.elapsed_seconds)}</b>
    </div>
    <p>{progress.message}</p>
    {maxTokens > 0 && <div className="telemetry-token-track" aria-label={`${progress.generated_tokens} trên tối đa ${maxTokens} token`}>
      <span style={{ width: `${tokenPercent}%` }} />
    </div>}
    <div className="telemetry-facts">
      <span><small>Token đã sinh</small><strong>{progress.generated_tokens.toLocaleString("vi-VN")}{maxTokens > 0 ? ` / ${maxTokens.toLocaleString("vi-VN")}` : ""}</strong></span>
      <span><small>Prompt tokens</small><strong>{progress.prompt_tokens?.toLocaleString("vi-VN") ?? "Đang đo"}</strong></span>
      <span><small>Heartbeat cuối</small><strong>{heartbeat}</strong></span>
    </div>
    {progress.stage === "GENERATING" && <small className="telemetry-note">Số token là ước tính cho đến khi model gửi usage cuối cùng.</small>}
  </section>;
}

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

export function WorkflowProgress({ definition, run, frozenNodeIds = [] }: {
  definition: WorkflowDefinition;
  run: WorkflowRun | null;
  frozenNodeIds?: string[];
}) {
  const order = topologicalNodeIds(definition);
  const nodes = Object.fromEntries(definition.nodes.map((node) => [node.id, node]));
  const statuses: Record<string, string> = Object.fromEntries(frozenNodeIds.map((id) => [id, "FROZEN"]));
  for (const node of run?.node_runs ?? []) statuses[node.node_id] = node.status;
  const completed = Object.values(statuses).filter((item) => ["COMPLETED", "FROZEN"].includes(item)).length;
  const percent = Math.round((completed / Math.max(order.length, 1)) * 100);
  const current = order.find((id) => statuses[id] === "RUNNING");
  const currentRun = run?.node_runs?.find((item) => item.node_id === current);
  const message = run?.status === "COMPLETED"
    ? "Workflow đã hoàn tất."
    : run?.status === "FAILED"
      ? "Workflow dừng vì có lỗi."
      : current
        ? `Đang chạy: ${nodes[current]?.name ?? current}.`
        : run
          ? "Đang chuẩn bị workflow."
          : frozenNodeIds.length
            ? "Nhánh golden đã freeze, sẵn sàng chấm bài."
            : "Workflow chưa chạy.";

  return <div className="workflow-progress">
    <div className="progress-summary"><div><strong>{message}</strong><span>{completed}/{order.length} node hoàn tất</span></div><b>{run || frozenNodeIds.length ? percent : 0}%</b></div>
    <div className="progress-track" aria-hidden="true"><span style={{ width: `${run || frozenNodeIds.length ? percent : 0}%` }} /></div>
    <ExecutionTelemetry progress={currentRun?.progress} nodeName={current ? nodes[current]?.name ?? current : undefined} />
    <ol>{order.map((id, index) => {
      const nodeStatus = statuses[id] ?? "idle";
      return <li className={`progress-${nodeStatus.toLowerCase()}`} key={id}><span>{index + 1}</span><div><strong>{nodes[id]?.name ?? id}</strong><small>{statusLabels[nodeStatus] ?? nodeStatus}</small></div></li>;
    })}</ol>
  </div>;
}
