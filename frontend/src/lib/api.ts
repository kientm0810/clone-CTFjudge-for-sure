import type { WorkflowDefinition, WorkflowDetail, WorkflowRun, WorkflowSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8400";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const listWorkflows = () => request<WorkflowSummary[]>("/workflows");
export const getWorkflow = (id: string) => request<WorkflowDetail>(`/workflows/${id}`);

export function createWorkflow(definition: WorkflowDefinition, description: string) {
  return request<WorkflowDetail>("/workflows", {
    method: "POST",
    body: JSON.stringify({ definition, description }),
  });
}

export function startRun(workflowId: string, inputs: Record<string, unknown>) {
  return request<WorkflowRun>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export const getRun = (runId: string) => request<WorkflowRun>(`/runs/${runId}`);

