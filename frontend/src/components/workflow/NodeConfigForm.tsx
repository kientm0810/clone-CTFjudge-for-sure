import type { ReactNode } from "react";
import type { AIModelOption, NodeType, VectorCollection } from "@/lib/types";

type Props = {
  type: NodeType;
  config: Record<string, unknown>;
  models: AIModelOption[];
  collections: VectorCollection[];
  onChange: (config: Record<string, unknown>) => void;
};

const defaultWeights: Record<string, number> = {
  vulnerability_understanding: 0.17,
  reconnaissance_thoroughness: 0.17,
  exploitation_methodology: 0.17,
  technical_accuracy: 0.17,
  efficiency_approach: 0.16,
  adaptability: 0.16,
};

const weightLabels: Record<string, string> = {
  vulnerability_understanding: "Hiểu lỗ hổng",
  reconnaissance_thoroughness: "Reconnaissance",
  exploitation_methodology: "Phương pháp khai thác",
  technical_accuracy: "Độ chính xác kỹ thuật",
  efficiency_approach: "Hiệu quả tiếp cận",
  adaptability: "Khả năng thích nghi",
};

export function validateNodeConfig(type: NodeType, config: Record<string, unknown>): string[] {
  const errors: string[] = [];
  if (type === "input" && !String(config.input_key ?? "").trim()) errors.push("Input key là bắt buộc.");
  if (type === "agent") {
    if (!String(config.model ?? "").trim()) errors.push("Hãy chọn model.");
    if (!String(config.prompt ?? "").trim()) errors.push("Prompt là bắt buộc.");
  }
  if (type === "database") {
    if (!["upsert", "search"].includes(String(config.operation))) errors.push("Hãy chọn Store hoặc Search.");
    if (!String(config.collection ?? "").trim()) errors.push("Collection là bắt buộc.");
    if (!String(config.embedding_model ?? "").trim()) errors.push("Hãy chọn embedding model.");
    if (config.operation === "search") {
      if (Number(config.top_k) < 1) errors.push("Top K phải lớn hơn 0.");
      const threshold = Number(config.score_threshold);
      if (threshold < 0 || threshold > 1) errors.push("Similarity threshold phải nằm trong khoảng 0–1.");
    }
  }
  if (type === "output") {
    if (!String(config.format ?? "").trim()) errors.push("Hãy chọn output format.");
    if (config.format === "ctfjudge_report") {
      const weights = (config.formula_weights as Record<string, number> | undefined) ?? defaultWeights;
      const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0);
      if (Math.abs(total - 1) > 0.001) errors.push("Tổng rubric weights phải bằng 100%.");
    }
  }
  return errors;
}

function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return <div className="guided-field"><span>{label}</span>{children}{help && <small>{help}</small>}</div>;
}

export function NodeConfigForm({ type, config, models, collections, onChange }: Props) {
  const update = (key: string, value: unknown) => onChange({ ...config, [key]: value });
  const chatModels = models.filter((model) => model.capabilities.includes("completion"));
  const embeddingModels = models.filter((model) => model.capabilities.includes("embedding"));
  const errors = validateNodeConfig(type, config);

  if (type === "input") return <div className="guided-config">
    <Field label="Input key" help="Tên biến xuất hiện trên màn hình Run."><input value={String(config.input_key ?? "")} onChange={(event) => update("input_key", event.target.value)} placeholder="student" /></Field>
    <Field label="Document type"><select value={String(config.document_type ?? "generic")} onChange={(event) => update("document_type", event.target.value)}><option value="generic">Generic text</option><option value="golden_solution">Golden solution</option><option value="student_submission">Student writeup</option></select></Field>
    <ValidationMessages errors={errors} />
  </div>;

  if (type === "agent") {
    const currentModel = String(config.model ?? "");
    const ollamaModels = chatModels.filter((model) => model.provider === "ollama");
    const registeredModels = chatModels.filter((model) => model.provider === "openai-compatible");
    return <div className="guided-config">
    <Field label="Chat model" help={chatModels.length ? `${chatModels.length} model khả dụng · thêm model tại tab AI Models` : "Chưa có model khả dụng. Hãy mở tab AI Models để thêm."}>
      <select value={currentModel} onChange={(event) => update("model", event.target.value)}>
        {!chatModels.some((item) => item.reference === config.model) && config.model ? <option value={String(config.model)}>{String(config.model)} · không còn khả dụng</option> : null}
        <option value="">Chọn model…</option>
        {ollamaModels.length ? <optgroup label="Ollama local">{ollamaModels.map((model) => <option value={model.reference} key={model.reference}>{model.name}{model.details?.parameter_size ? ` · ${model.details.parameter_size}` : ""}</option>)}</optgroup> : null}
        {registeredModels.length ? <optgroup label="Model đã thêm">{registeredModels.map((model) => <option value={model.reference} key={model.reference}>{model.name} · {model.model_name}</option>)}</optgroup> : null}
      </select>
    </Field>
    <Field label={`Temperature · ${Number(config.temperature ?? 0).toFixed(1)}`} help="0 ổn định hơn; giá trị cao tạo câu trả lời đa dạng hơn."><input type="range" min="0" max="1" step="0.1" value={Number(config.temperature ?? 0)} onChange={(event) => update("temperature", Number(event.target.value))} /></Field>
    <Field label="Prompt"><textarea value={String(config.prompt ?? "")} onChange={(event) => update("prompt", event.target.value)} placeholder="Mô tả nhiệm vụ của agent…" /></Field>
    <Field label="Response format"><select value={config.output_schema ? "structured" : "json"} onChange={(event) => { if (event.target.value === "json") { const next = { ...config }; delete next.output_schema; onChange(next); } else update("output_schema", { type: "object", properties: {}, required: [] }); }}><option value="json">JSON</option><option value="structured">Structured JSON schema</option></select></Field>
    {config.output_schema ? <p className="config-hint">Schema chi tiết có thể chỉnh trong Advanced JSON.</p> : null}
    <ValidationMessages errors={errors} />
  </div>;
  }

  if (type === "database") {
    const operation = String(config.operation ?? "search");
    const isolated = String(config.collection ?? "").includes("{{run_id}}");
    return <div className="guided-config">
      <Field label="Operation"><div className="operation-toggle"><button className={operation === "upsert" ? "active" : ""} onClick={() => update("operation", "upsert")} type="button">Store vectors</button><button className={operation === "search" ? "active" : ""} onClick={() => update("operation", "search")} type="button">Search vectors</button></div></Field>
      <Field label="Collection" help="Chọn collection hiện có hoặc nhập tên mới."><input list="vector-collections" value={String(config.collection ?? "")} onChange={(event) => update("collection", event.target.value)} placeholder="golden-solutions" /><datalist id="vector-collections">{collections.map((collection) => <option value={collection.name} key={collection.name}>{collection.chunk_count} chunks</option>)}</datalist></Field>
      <Field label="Collection scope"><select value={isolated ? "isolated" : "shared"} onChange={(event) => { const current = String(config.collection ?? "collection").replace(/[-_]?\{\{run_id\}\}/g, ""); update("collection", event.target.value === "isolated" ? `${current || "collection"}-{{run_id}}` : current); }}><option value="isolated">Isolated per run</option><option value="shared">Shared persistent</option></select></Field>
      <Field label="Embedding model" help={embeddingModels.length ? `${embeddingModels.length} embedding model khả dụng` : "Hãy tải embedding model trong Ollama."}><select value={String(config.embedding_model ?? "")} onChange={(event) => update("embedding_model", event.target.value)}>{!embeddingModels.some((item) => item.reference === config.embedding_model) && config.embedding_model ? <option value={String(config.embedding_model)}>{String(config.embedding_model)}</option> : null}<option value="">Chọn embedding model…</option>{embeddingModels.map((model) => <option value={model.reference} key={model.reference}>{model.name}</option>)}</select></Field>
      {operation === "upsert" && <label className="freeze-toggle"><input type="checkbox" checked={config.freeze === true} onChange={(event) => {
        const freeze = event.target.checked;
        const current = String(config.collection ?? "golden");
        onChange({ ...config, freeze, collection: freeze && !current.includes("{{run_id}}") ? `${current || "golden"}-{{run_id}}` : current });
      }} /><span><strong>Freeze làm Golden snapshot</strong><small>Chạy nhánh này một lần trên /prod và tái sử dụng collection cho nhiều bài sinh viên.</small></span></label>}
      {operation === "search" && <>
        <Field label="Top K" help="Số golden chunks gần nhất cho mỗi student chunk."><input type="number" min="1" max="50" value={Number(config.top_k ?? 3)} onChange={(event) => update("top_k", Number(event.target.value))} /></Field>
        <Field label={`Similarity threshold · ${Number(config.score_threshold ?? 0.25).toFixed(2)}`} help="Thấp: nhiều kết quả. Cao: ít kết quả nhưng liên quan hơn."><input type="range" min="0" max="1" step="0.05" value={Number(config.score_threshold ?? 0.25)} onChange={(event) => update("score_threshold", Number(event.target.value))} /></Field>
      </>}
      {!!collections.length && <div className="collection-summary">{collections.map((item) => <span key={item.name}><strong>{item.name}</strong>{item.chunk_count} chunks · {item.embedding_models.join(", ")}</span>)}</div>}
      <ValidationMessages errors={errors} />
    </div>;
  }

  const format = String(config.format ?? "json");
  const weights = (config.formula_weights as Record<string, number> | undefined) ?? defaultWeights;
  const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0);
  return <div className="guided-config">
    <Field label="Output format"><select value={format} onChange={(event) => { const value = event.target.value; onChange(value === "ctfjudge_report" ? { ...config, format: value, formula_weights: config.formula_weights ?? defaultWeights } : { ...config, format: value }); }}><option value="json">Raw JSON</option><option value="comparison_report">Similarity report</option><option value="ctfjudge_report">CTFJudge rubric report</option></select></Field>
    {format === "ctfjudge_report" && <div className="weight-editor"><div className={`weight-total ${Math.abs(total - 1) < 0.001 ? "valid" : "invalid"}`}>Total weight: {Math.round(total * 100)}%</div>{Object.entries(defaultWeights).map(([key]) => <Field label={weightLabels[key]} key={key}><input type="number" min="0" max="1" step="0.01" value={Number(weights[key] ?? 0)} onChange={(event) => update("formula_weights", { ...weights, [key]: Number(event.target.value) })} /></Field>)}</div>}
    <ValidationMessages errors={errors} />
  </div>;
}

function ValidationMessages({ errors }: { errors: string[] }) {
  return errors.length ? <div className="config-validation">{errors.map((error) => <p key={error}>● {error}</p>)}</div> : <div className="config-valid">✓ Cấu hình hợp lệ</div>;
}
