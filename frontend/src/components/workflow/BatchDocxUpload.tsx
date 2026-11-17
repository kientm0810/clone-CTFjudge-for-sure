"use client";

import { useId, useState } from "react";
import { extractDocx } from "@/lib/api";
import type { DocumentExtraction } from "@/lib/types";

const MAX_FILES = 10;
const MAX_FILE_BYTES = 10 * 1024 * 1024;

export function BatchDocxUpload({ onExtract, disabled = false }: {
  onExtract: (documents: DocumentExtraction[]) => void;
  disabled?: boolean;
}) {
  const inputId = useId();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: File[]) {
    setError(null);
    if (!files.length) return;
    if (files.length > MAX_FILES) {
      setError(`Chỉ được chọn tối đa ${MAX_FILES} file DOCX cho một batch.`);
      return;
    }
    const invalid = files.find((file) => !file.name.toLowerCase().endsWith(".docx") || file.size > MAX_FILE_BYTES);
    if (invalid) {
      setError(`File “${invalid.name}” không hợp lệ hoặc lớn hơn 10 MB.`);
      return;
    }

    setBusy(true);
    setProgress(0);
    setTotal(files.length);
    try {
      const documents: DocumentExtraction[] = [];
      for (const file of files) {
        documents.push(await extractDocx(file));
        setProgress(documents.length);
      }
      onExtract(documents);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return <div className="batch-upload" aria-busy={busy}>
    <input
      id={inputId}
      type="file"
      multiple
      accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      disabled={disabled || busy}
      onChange={(event) => {
        const files = Array.from(event.currentTarget.files ?? []);
        event.currentTarget.value = "";
        void handleFiles(files);
      }}
    />
    <label htmlFor={inputId} aria-disabled={disabled || busy}>
      {busy ? `Đang đọc ${progress}/${total} file…` : "Chọn tối đa 10 writeups DOCX"}
    </label>
    <span>Mỗi file tạo một run độc lập và dùng chung Golden Snapshot đang active.</span>
    {error && <p className="docx-error" role="alert">{error}</p>}
  </div>;
}
