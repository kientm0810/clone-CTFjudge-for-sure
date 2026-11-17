export type NodeType = "input" | "agent" | "database" | "output";

export type WorkflowNode = {
  id: string;
  type: NodeType;
  name?: string;
  inputs?: Record<string, unknown>;
  config: Record<string, unknown>;
  position?: { x: number; y: number };
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

export type WorkflowVersionSummary = {
  id: string;
  workflow_id: string;
  version: number;
  created_at: string;
  is_current: boolean;
};

export type WorkflowVersionDetail = WorkflowVersionSummary & { definition: WorkflowDefinition };

export type WorkflowDeployment = {
  environment: string;
  workflow_id: string;
  workflow_name: string;
  workflow_version_id: string;
  version_number: number;
  published_at: string;
  updated_at: string;
  definition: WorkflowDefinition;
};

export type ExecutionProgress = {
  node_id: string;
  stage: string;
  message: string;
  prompt_tokens?: number | null;
  generated_tokens: number;
  max_tokens?: number | null;
  elapsed_seconds: number;
  heartbeat_at: string;
  started_at: string;
  updated_at: string;
};

export type GoldenSnapshot = {
  id: string;
  workflow_version_id: string;
  frozen_node_id: string;
  status: "PENDING" | "RUNNING" | "READY" | "FAILED" | string;
  content_hash: string;
  collection_name?: string | null;
  embedding_model?: string | null;
  chunk_count: number;
  is_active: boolean;
  error?: string | null;
  frozen_node_ids: string[];
  created_at: string;
  completed_at?: string | null;
  progress: ExecutionProgress[];
};

export type DocumentExtraction = {
  filename: string;
  content: string;
  character_count: number;
  paragraph_count: number;
};

export type OllamaModel = {
  name: string;
  model?: string;
  size?: number;
  capabilities?: string[];
  details?: { parameter_size?: string; family?: string };
};

export type AIModelOption = {
  reference: string;
  name: string;
  provider: "ollama" | "openai-compatible" | string;
  model_name: string;
  capabilities: string[];
  details?: Record<string, string>;
};

export type RegisteredAIModel = {
  id: string;
  reference: string;
  name: string;
  model_name: string;
  endpoint_url: string;
  additional_headers: Record<string, string>;
  timeout_seconds: number;
  supports_json_schema: boolean;
  enabled: boolean;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
};

export type AIModelWrite = {
  name: string;
  model_name: string;
  endpoint_url: string;
  api_key?: string | null;
  additional_headers: Record<string, string>;
  timeout_seconds: number;
  supports_json_schema: boolean;
  enabled: boolean;
};

export type AIModelTestResult = {
  ok: boolean;
  latency_ms: number;
  response_preview: string;
};

export type VectorCollection = {
  name: string;
  chunk_count: number;
  embedding_models: string[];
  updated_at?: string | null;
};

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
  progress?: ExecutionProgress | null;
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

export type RunHistoryItem = WorkflowRun & {
  workflow_id: string;
  version_number: number;
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
  report_type?: "similarity" | "ctfjudge";
  summary_score?: number;
  similarity_score?: number;
  overall_score?: number;
  summary: string;
  golden_chunks?: Array<{ chunk_id: string; content: string; chunk_index?: number }>;
  comparisons: ChunkComparison[];
  challenge_solved?: boolean;
  competency_matrix?: Record<string, string>;
  formula_breakdown?: Record<string, { rating: string; score: number; weight: number; weighted_score: number }>;
  detailed_comparison?: string;
  key_insights?: string;
  failure_analysis?: string;
  failure_keywords?: Array<{ keyword: string; classification: string }>;
};

