"use client";

import { useId, useState } from "react";
import { extractDocx } from "@/lib/api";

const MAX_FILE_BYTES = 10 * 1024 * 1024;

export function DocxUpload({ onExtract, disabled = false }: {
  onExtract: (content: string) => void;
  disabled?: boolean;
}) {
  const inputId = useId();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file?: File) {
    if (!file) return;
    setMessage(null);
    setError(null);
    if (!file.name.toLowerCase().endsWith(".docx")) {
      setError("Chỉ hỗ trợ file Microsoft Word có đuôi .docx.");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setError("File DOCX không được lớn hơn 10 MB.");
      return;
    }

    setBusy(true);
    try {
      const result = await extractDocx(file);
      onExtract(result.content);
      setMessage(`${result.filename} · ${result.paragraph_count} đoạn · ${result.table_count} bảng · ${result.character_count.toLocaleString("vi-VN")} ký tự`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return <div className="docx-upload" aria-busy={busy}>
    <input
      id={inputId}
      type="file"
      accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      disabled={disabled || busy}
      onChange={(event) => {
        const file = event.currentTarget.files?.[0];
        event.currentTarget.value = "";
        void handleFile(file);
      }}
    />
    <label htmlFor={inputId} aria-disabled={disabled || busy}>{busy ? "Đang đọc file…" : "Chọn file DOCX"}</label>
    <span>Không ảnh · tối đa 10 MB · nội dung file sẽ điền vào ô văn bản</span>
    {message && <p className="docx-success" role="status">{message}</p>}
    {error && <p className="docx-error" role="alert">{error}</p>}
  </div>;
}
