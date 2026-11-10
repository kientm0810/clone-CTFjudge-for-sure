export type NodeType = "input" | "agent" | "database" | "output";

export type WorkflowNode = {
  id: string;
  type: NodeType;
  name?: string;
  config: Record<string, unknown>;
};

export type WorkflowEdge = { source: string; target: string };

export type WorkflowDefinition = {
  name: string;
  version: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
};

export type WorkflowSummary = {
  id: string;
  name: string;
  description?: string | null;
  current_version: number;
  created_at: string;
  updated_at: string;
};

export type WorkflowDetail = WorkflowSummary & { definition: WorkflowDefinition };

export type NodeRun = {
  node_id: string;
  node_type: NodeType;
  sequence: number;
  status: string;
  input_data: Record<string, unknown>;
  output_data: unknown;
  error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

export type WorkflowRun = {
  id: string;
  workflow_version_id: string;
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  celery_task_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  node_runs?: NodeRun[];
};

export type GoldenMatch = {
  chunk_id: string;
  content: string;
  similarity_score?: number;
};

export type ChunkComparison = {
  student_chunk_id: string;
  student_content: string;
  classification: string;
  score: number;
  explanation: string;
  matched_golden: GoldenMatch[];
};

export type ComparisonReport = {
  summary_score: number;
  summary: string;
  comparisons: ChunkComparison[];
};

