import type { DocumentExtraction, WorkflowDefinition } from "@/lib/types";
import { DocxUpload } from "./DocxUpload";

export function RuntimeInputs({ definition, value, onChange, hiddenKeys = [], onDocumentExtract }: {
  definition?: WorkflowDefinition;
  value: string;
  onChange: (value: string) => void;
  hiddenKeys?: string[];
  onDocumentExtract?: (key: string, document: DocumentExtraction) => void;
}) {
  let parsed: Record<string, unknown> = {};
  try { parsed = JSON.parse(value); } catch { /* Keep raw editing available. */ }
  const valid = parsed !== null && typeof parsed === "object" && !Array.isArray(parsed);

  return <div>
    {valid && definition?.nodes.filter((node) => {
      const key = String(node.config.input_key ?? node.id);
      return node.type === "input" && !hiddenKeys.includes(key);
    }).map((node) => {
      const key = String(node.config.input_key ?? node.id);
      const textareaId = `runtime-input-${node.id}`;
      const updateContent = (content: string) => onChange(JSON.stringify({ ...parsed, [key]: content }, null, 2));
      return <div className="runtime-input-field" key={node.id}>
        <label htmlFor={textareaId}><strong>{node.name ?? key}</strong></label>
        <p className="card-help">Dán nội dung hoặc chọn file DOCX. Văn bản sẽ được gửi tới node {node.name ?? node.id}.</p>
        <DocxUpload onExtract={(content, document) => {
          updateContent(content);
          onDocumentExtract?.(key, document);
        }} />
        <textarea
          id={textareaId}
          aria-label={node.name ?? key}
          value={typeof parsed[key] === "string" ? parsed[key] as string : JSON.stringify(parsed[key] ?? "")}
          onChange={(event) => updateContent(event.target.value)}
        />
      </div>;
    })}
    <details className="advanced-config"><summary>Dữ liệu JSON nâng cao</summary>
      <textarea aria-label="Dữ liệu JSON nâng cao" value={value} onChange={(event) => onChange(event.target.value)} spellCheck={false} />
    </details>
    {!valid && <p role="alert">Dữ liệu phải là một object JSON. Hãy sửa trong phần nâng cao.</p>}
  </div>;
}
