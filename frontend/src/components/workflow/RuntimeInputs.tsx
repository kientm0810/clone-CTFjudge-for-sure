import type { WorkflowDefinition } from "@/lib/types";

export function RuntimeInputs({ definition, value, onChange }: {
  definition?: WorkflowDefinition; value: string; onChange: (value: string) => void;
}) {
  let parsed: Record<string, unknown> = {};
  try { parsed = JSON.parse(value); } catch { /* Keep raw editing available. */ }
  const valid = parsed !== null && typeof parsed === "object" && !Array.isArray(parsed);
  return <div>
    {valid && definition?.nodes.filter((node) => node.type === "input").map((node) => {
      const key = String(node.config.input_key ?? node.id);
      return <label key={node.id} style={{ display: "block", marginTop: 16 }}>
        <strong>{node.name ?? key}</strong>
        <p className="card-help">Dán nội dung vào đây. Dữ liệu này sẽ được gửi tới node {node.name ?? node.id}.</p>
        <textarea aria-label={node.name ?? key} value={typeof parsed[key] === "string" ? parsed[key] as string : JSON.stringify(parsed[key] ?? "")}
          onChange={(event) => onChange(JSON.stringify({ ...parsed, [key]: event.target.value }, null, 2))} />
      </label>;
    })}
    <details className="advanced-config"><summary>Dữ liệu JSON nâng cao</summary>
      <textarea aria-label="Dữ liệu JSON nâng cao" value={value} onChange={(event) => onChange(event.target.value)} spellCheck={false} />
    </details>
    {!valid && <p role="alert">Dữ liệu phải là một object JSON. Hãy sửa trong phần nâng cao.</p>}
  </div>;
}
