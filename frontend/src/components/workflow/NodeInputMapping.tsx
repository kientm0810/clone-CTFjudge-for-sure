import type { NodeType } from "@/lib/types";

type Mapping = Record<string, unknown>;

function outputDescription(type: NodeType, config: Record<string, unknown>): string {
  if (type === "input") return "Document: document_id, document_type, content, metadata";
  if (type === "agent") {
    const schema = config.output_schema as { properties?: Record<string, unknown> } | undefined;
    const fields = Object.keys(schema?.properties ?? {});
    return schema ? `Structured JSON${fields.length ? `: ${fields.join(", ")}` : " theo Response schema"}` : "JSON do LLM trả về";
  }
  if (type === "database") return config.operation === "upsert"
    ? "collection, indexed_chunks, embedding_model"
    : "retrieval_results[]";
  return "Object cuối cùng được tạo từ Input mapping";
}

function nextKey(mapping: Mapping, base = "input"): string {
  let key = base.replace(/[^A-Za-z0-9_]/g, "_");
  let suffix = 2;
  while (key in mapping) key = `${base}_${suffix++}`.replace(/[^A-Za-z0-9_]/g, "_");
  return key;
}

export function NodeInputMapping({ type, mapping, upstreamNodes, config, onChange }: {
  type: NodeType;
  mapping: Mapping;
  upstreamNodes: Array<{ id: string; name: string }>;
  config: Record<string, unknown>;
  onChange: (mapping: Mapping) => void;
}) {
  function renameKey(oldKey: string, newKey: string) {
    const next: Mapping = {};
    for (const [key, value] of Object.entries(mapping)) next[key === oldKey ? newKey : key] = value;
    onChange(next);
  }

  function updateValue(key: string, value: string) {
    onChange({ ...mapping, [key]: value });
  }

  function remove(key: string) {
    onChange(Object.fromEntries(Object.entries(mapping).filter(([current]) => current !== key)));
  }

  function addReference(nodeId?: string) {
    const key = nextKey(mapping, nodeId ?? "input");
    onChange({ ...mapping, [key]: nodeId ? `{{ steps.${nodeId}.output }}` : "" });
  }

  return <section className="mapping-editor">
    <div className="mapping-heading"><div><span>INPUT</span><strong>Dữ liệu node sẽ nhận</strong></div>{type !== "input" && <button type="button" onClick={() => addReference()}>Thêm field</button>}</div>
    {type === "input" ? <p className="mapping-empty">Input node đọc dữ liệu người dùng theo <code>input_key</code>, nên không cần mapping từ node trước.</p> : <>
      <p className="mapping-help">Đường nối quyết định step nào chạy trước. Expression quyết định chính xác dữ liệu nào được lấy.</p>
      <div className="mapping-rows">{Object.entries(mapping).map(([key, rawValue]) => <div className="mapping-row" key={key}>
        <input aria-label="Tên input" value={key} onChange={(event) => renameKey(key, event.target.value)} placeholder="field_name" />
        <textarea aria-label={`Expression cho ${key}`} value={typeof rawValue === "string" ? rawValue : JSON.stringify(rawValue)} onChange={(event) => updateValue(key, event.target.value)} placeholder="{{ steps.node-id.output.field }}" />
        <button type="button" onClick={() => remove(key)} aria-label={`Xóa input ${key}`}>Xóa</button>
      </div>)}</div>
      {!Object.keys(mapping).length && <p className="mapping-warning">Node chưa có input. Hãy thêm field hoặc chọn một step upstream bên dưới.</p>}
      <div className="upstream-references"><small>Step upstream có thể dùng</small>{upstreamNodes.length ? <div>{upstreamNodes.map((node) => <button type="button" key={node.id} onClick={() => addReference(node.id)} title={`Thêm {{ steps.${node.id}.output }}`}><strong>{node.name}</strong><code>{`{{ steps.${node.id}.output }}`}</code></button>)}</div> : <p>Hãy nối node này với một node phía trước trước.</p>}</div>
    </>}
    <div className="output-contract"><span>OUTPUT</span><div><strong>Node sẽ trả về</strong><p>{outputDescription(type, config)}</p></div></div>
  </section>;
}
