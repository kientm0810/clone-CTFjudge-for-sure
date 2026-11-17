import type { AIModelOption, AIModelTestResult, AIModelWrite, BatchRunItem, DocumentExtraction, GoldenSnapshot, OllamaModel, RegisteredAIModel, RunHistoryItem, VectorCollection, WorkflowDefinition, WorkflowDeployment, WorkflowDetail, WorkflowRun, WorkflowSummary, WorkflowVersionDetail, WorkflowVersionSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8800";

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

export const listAIModelOptions = () => request<{ models: AIModelOption[]; warnings: string[] }>("/providers/models");
export const listRegisteredAIModels = () => request<RegisteredAIModel[]>("/providers/registered-models");
export const createRegisteredAIModel = (payload: AIModelWrite) => request<RegisteredAIModel>("/providers/registered-models", { method: "POST", body: JSON.stringify(payload) });
export const updateRegisteredAIModel = (id: string, payload: AIModelWrite) => request<RegisteredAIModel>(`/providers/registered-models/${id}`, { method: "PUT", body: JSON.stringify(payload) });
export const testRegisteredAIModel = (id: string) => request<AIModelTestResult>(`/providers/registered-models/${id}/test`, { method: "POST" });

export async function deleteRegisteredAIModel(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/providers/registered-models/${id}`, { method: "DELETE" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
}

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

export async function deleteWorkflowVersion(workflowId: string, version: number): Promise<void> {
  const response = await fetch(`${API_URL}/workflows/${workflowId}/versions/${version}`, { method: "DELETE" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
}

export function createWorkflowVersion(workflowId: string, definition: WorkflowDefinition) {
  return request<WorkflowDetail>(`/workflows/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({ definition }),
  });
}

export function activateWorkflowVersion(workflowId: string, version: number) {
  return request<WorkflowDetail>(`/workflows/${workflowId}/versions/${version}/activate`, { method: "POST" });
}

export function publishWorkflow(workflowId: string) {
  return request<WorkflowDeployment>(`/workflows/${workflowId}/publish`, { method: "POST" });
}

export const getDeployment = (environment = "prod") =>
  request<WorkflowDeployment>(`/deployments/${environment}`);

export const getActiveGoldenSnapshot = (environment = "prod") =>
  request<GoldenSnapshot>(`/deployments/${environment}/golden-snapshot`);

export function createGoldenSnapshot(
  environment: string,
  inputs: Record<string, unknown>,
  frozenNodeId: string,
) {
  return request<GoldenSnapshot>(`/deployments/${environment}/golden-snapshots`, {
    method: "POST",
    body: JSON.stringify({ inputs, frozen_node_id: frozenNodeId }),
  });
}

export const getGoldenSnapshot = (environment: string, snapshotId: string) =>
  request<GoldenSnapshot>(`/deployments/${environment}/golden-snapshots/${snapshotId}`);

export async function extractDocx(file: File): Promise<DocumentExtraction> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_URL}/documents/extract-docx`, { method: "POST", body });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
  return response.json() as Promise<DocumentExtraction>;
}

export function startDeploymentRun(environment: string, inputs: Record<string, unknown>) {
  return request<WorkflowRun>(`/deployments/${environment}/runs`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export function startDeploymentBatch(
  environment: string,
  submissions: Array<{ filename: string; inputs: Record<string, unknown> }>,
) {
  return request<BatchRunItem[]>(`/deployments/${environment}/runs/batch`, {
    method: "POST",
    body: JSON.stringify({ submissions }),
  });
}

export function startRun(workflowId: string, inputs: Record<string, unknown>) {
  return request<WorkflowRun>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

export const getRun = (runId: string) => request<WorkflowRun>(`/runs/${runId}`);
export const getRunHtmlReportUrl = (runId: string) => `${API_URL}/runs/${runId}/report.html`;

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

