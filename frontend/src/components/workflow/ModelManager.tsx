"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createRegisteredAIModel,
  deleteRegisteredAIModel,
  listRegisteredAIModels,
  testRegisteredAIModel,
  updateRegisteredAIModel,
} from "@/lib/api";
import type { AIModelWrite, RegisteredAIModel } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";

type ModelForm = {
  name: string;
  model_name: string;
  endpoint_url: string;
  api_key: string;
  timeout_seconds: number;
  ngrok_skip_warning: boolean;
  supports_json_schema: boolean;
  enabled: boolean;
};

const emptyForm: ModelForm = {
  name: "",
  model_name: "",
  endpoint_url: "",
  api_key: "",
  timeout_seconds: 180,
  ngrok_skip_warning: true,
  supports_json_schema: false,
  enabled: true,
};

function toPayload(form: ModelForm): AIModelWrite {
  return {
    name: form.name.trim(),
    model_name: form.model_name.trim(),
    endpoint_url: form.endpoint_url.trim(),
    api_key: form.api_key.trim() || null,
    additional_headers: form.ngrok_skip_warning ? { "ngrok-skip-browser-warning": "true" } : {},
    timeout_seconds: form.timeout_seconds,
    supports_json_schema: form.supports_json_schema,
    enabled: form.enabled,
  };
}

export function ModelManager() {
  const [models, setModels] = useState<RegisteredAIModel[]>([]);
  const [form, setForm] = useState<ModelForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RegisteredAIModel | null>(null);
  const [busy, setBusy] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadModels() {
    try {
      setModels(await listRegisteredAIModels());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  useEffect(() => { void loadModels(); }, []);

  function resetForm() {
    setEditingId(null);
    setForm(emptyForm);
    setError(null);
  }

  function editModel(model: RegisteredAIModel) {
    setEditingId(model.id);
    setForm({
      name: model.name,
      model_name: model.model_name,
      endpoint_url: model.endpoint_url,
      api_key: "",
      timeout_seconds: model.timeout_seconds,
      ngrok_skip_warning: model.additional_headers["ngrok-skip-browser-warning"] === "true",
      supports_json_schema: model.supports_json_schema,
      enabled: model.enabled,
    });
    setNotice(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveModel(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null); setNotice(null);
    try {
      const saved = editingId
        ? await updateRegisteredAIModel(editingId, toPayload(form))
        : await createRegisteredAIModel(toPayload(form));
      await loadModels();
      resetForm();
      setNotice(`Đã lưu “${saved.name}”. Model này đã xuất hiện trong dropdown của node Agent.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function testModel(model: RegisteredAIModel) {
    setTestingId(model.id); setError(null); setNotice(null);
    try {
      const result = await testRegisteredAIModel(model.id);
      setNotice(`Kết nối “${model.name}” thành công trong ${(result.latency_ms / 1000).toFixed(1)} giây. Phản hồi: ${result.response_preview}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setTestingId(null); }
  }

  async function removeModel() {
    if (!deleteTarget) return;
    setBusy(true); setError(null);
    try {
      await deleteRegisteredAIModel(deleteTarget.id);
      if (editingId === deleteTarget.id) resetForm();
      setNotice(`Đã xóa “${deleteTarget.name}” khỏi danh sách model.`);
      setDeleteTarget(null);
      await loadModels();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  return <main className="models-page">
    <header className="models-header">
      <div><p className="eyebrow">CTFJudge · AI connections</p><h1>Quản lý model AI</h1><p className="subtitle">Thêm một API tương thích OpenAI, kiểm tra kết nối rồi chọn model đó trong node Agent.</p></div>
      <div className="model-flow"><span>1</span><strong>Thêm API</strong><b>→</b><span>2</span><strong>Kiểm tra</strong><b>→</b><span>3</span><strong>Chọn trong Agent</strong></div>
    </header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {notice && <div className="success-banner" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice(null)}>Đóng</button></div>}
    <div className="models-layout">
      <form className="model-form card" onSubmit={saveModel}>
        <div className="card-heading"><div><p className="section-label">BƯỚC 1</p><h2>{editingId ? "Sửa kết nối model" : "Thêm model mới"}</h2><p className="card-help">Điền URL API kết thúc bằng <code>/v1/chat/completions</code>. Backend sẽ gửi JSON trực tiếp tới URL này.</p></div>{editingId && <button className="secondary-button" type="button" onClick={resetForm}>Thêm mới</button>}</div>
        <label>Tên hiển thị<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Qwen3.8 27B Ridge" /><small>Tên dễ nhớ sẽ xuất hiện trong dropdown của Agent.</small></label>
        <label>Model identifier<input required value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} placeholder="qwen3.8-27b-ridge" /><small>Giá trị được gửi trong trường <code>model</code> của request.</small></label>
        <label>API URL<input required type="url" value={form.endpoint_url} onChange={(event) => setForm({ ...form, endpoint_url: event.target.value })} placeholder="https://your-host.ngrok-free.dev/v1/chat/completions" /></label>
        <label>API key <span className="optional-label">không bắt buộc</span><input type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder={editingId ? "Để trống để giữ key hiện tại" : "sk-..."} /><small>Key không được trả về frontend sau khi lưu.</small></label>
        <label>Timeout (giây)<input required type="number" min="5" max="1800" value={form.timeout_seconds} onChange={(event) => setForm({ ...form, timeout_seconds: Number(event.target.value) })} /></label>
        <div className="model-checks">
          <label><input type="checkbox" checked={form.ngrok_skip_warning} onChange={(event) => setForm({ ...form, ngrok_skip_warning: event.target.checked })} /><span><strong>Ngrok endpoint</strong><small>Gửi header <code>ngrok-skip-browser-warning: true</code>.</small></span></label>
          <label><input type="checkbox" checked={form.supports_json_schema} onChange={(event) => setForm({ ...form, supports_json_schema: event.target.checked })} /><span><strong>Hỗ trợ JSON Schema</strong><small>Chỉ bật nếu server hỗ trợ <code>response_format.json_schema</code>.</small></span></label>
          <label><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} /><span><strong>Cho phép sử dụng</strong><small>Model được hiển thị trong dropdown Agent.</small></span></label>
        </div>
        <button className="primary-button model-save" type="submit" disabled={busy}>{busy ? "Đang lưu…" : editingId ? "Lưu thay đổi" : "Thêm model"}</button>
      </form>
      <section className="model-list card">
        <div className="card-heading"><div><p className="section-label">BƯỚC 2</p><h2>Model đã thêm</h2><p className="card-help">Kiểm tra từng kết nối trước khi dùng trong workflow.</p></div><span className="model-count">{models.length} model</span></div>
        {models.length ? <div className="model-cards">{models.map((model) => <article className="model-card" key={model.id}>
          <header><div><span className={model.enabled ? "model-status enabled" : "model-status"}>{model.enabled ? "ĐANG BẬT" : "ĐANG TẮT"}</span><h3>{model.name}</h3></div><code>{model.model_name}</code></header>
          <dl><div><dt>API</dt><dd>{model.endpoint_url}</dd></div><div><dt>Reference</dt><dd>{model.reference}</dd></div><div><dt>Xác thực</dt><dd>{model.has_api_key ? "Có API key" : "Không có API key"}</dd></div></dl>
          <footer><button className="secondary-button" type="button" onClick={() => void testModel(model)} disabled={testingId === model.id}>{testingId === model.id ? "Đang kiểm tra…" : "Kiểm tra kết nối"}</button><button className="text-button" type="button" onClick={() => editModel(model)}>Sửa</button><button className="danger-button" type="button" onClick={() => setDeleteTarget(model)}>Xóa</button></footer>
        </article>)}</div> : <div className="models-empty"><strong>Chưa có model được thêm</strong><p>Điền form bên trái. Sau khi lưu, model sẽ xuất hiện tại đây và trong dropdown của node Agent.</p></div>}
      </section>
    </div>
    <ConfirmDialog open={Boolean(deleteTarget)} title={`Xóa model “${deleteTarget?.name ?? ""}”?`} description="Các workflow đang tham chiếu model này sẽ không chạy được cho tới khi bạn chọn model khác." confirmLabel="Xóa model" onCancel={() => setDeleteTarget(null)} onConfirm={() => void removeModel()} />
  </main>;
}
