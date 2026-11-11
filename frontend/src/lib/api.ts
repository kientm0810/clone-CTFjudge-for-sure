import type { OllamaModel, RunHistoryItem, VectorCollection, WorkflowDefinition, WorkflowDetail, WorkflowRun, WorkflowSummary, WorkflowVersionDetail, WorkflowVersionSummary } from "./types";

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

export async function deleteWorkflow(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/workflows/${id}`, { method: "DELETE" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
}

export const listOllamaModels = async () =>
  (await request<{ models: OllamaModel[] }>("/providers/ollama/models")).models;

export const listVectorCollections = () => request<VectorCollection[]>("/vectors/collections");

export function createWorkflow(definition: WorkflowDefinition, description: string) {
  return request<WorkflowDetail>("/workflows", {
    method: "POST",
    body: JSON.stringify({ definition, description }),
  });
}

export const listWorkflowVersions = (workflowId: string) =>
  request<WorkflowVersionSummary[]>(`/workflows/${workflowId}/versions`);

export const getWorkflowVersion = (workflowId: string, version: number) =>
  request<WorkflowVersionDetail>(`/workflows/${workflowId}/versions/${version}`);

export function createWorkflowVersion(workflowId: string, definition: WorkflowDefinition) {
  return request<WorkflowDetail>(`/workflows/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({ definition }),
  });
}

export function activateWorkflowVersion(workflowId: string, version: number) {
  return request<WorkflowDetail>(`/workflows/${workflowId}/versions/${version}/activate`, { method: "POST" });
}

export function startRun(workflowId: string, inputs: Record<string, unknown>) {
  return request<WorkflowRun>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export const getRun = (runId: string) => request<WorkflowRun>(`/runs/${runId}`);

export const listWorkflowRuns = (workflowId: string) =>
  request<RunHistoryItem[]>(`/workflows/${workflowId}/runs`);

export function retryRun(runId: string) {
  return request<WorkflowRun>(`/runs/${runId}/retry`, { method: "POST" });
}

export async function deleteRun(runId: string): Promise<void> {
  const response = await fetch(`${API_URL}/runs/${runId}`, { method: "DELETE" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
}

