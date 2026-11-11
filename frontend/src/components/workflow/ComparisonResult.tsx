import type { ComparisonReport, WorkflowRun } from "@/lib/types";

const labels: Record<string, string> = {
  exact_match: "Trùng khớp",
  paraphrase: "Tương đồng",
  partial_match: "Khớp một phần",
  additional_valid_approach: "Cách làm hợp lệ khác",
  contradiction: "Mâu thuẫn",
  incorrect: "Không chính xác",
  irrelevant: "Không liên quan",
  no_match: "Không tìm thấy",
};

function boundedScore(value: unknown): number {
  let score = Number(value);
  if (!Number.isFinite(score)) return 0;
  if (score > 1 && score <= 10) score /= 10;
  else if (score > 10) score /= 100;
  return Math.max(0, Math.min(score, 1));
}

function extractReport(run: WorkflowRun | null): ComparisonReport | null {
  const outputs = run?.result?.outputs;
  if (!outputs || typeof outputs !== "object" || Array.isArray(outputs)) return null;
  const report = (outputs as Record<string, unknown>).report;
  if (!report || typeof report !== "object" || Array.isArray(report)) return null;
  const candidate = report as Partial<ComparisonReport>;
  if (!Array.isArray(candidate.comparisons)) return null;
  return { ...candidate, summary: String(candidate.summary ?? ""), comparisons: candidate.comparisons } as ComparisonReport;
}

function tone(classification: string): string {
  if (["exact_match", "paraphrase", "additional_valid_approach"].includes(classification)) return "match";
  if (classification === "partial_match") return "partial";
  if (["contradiction", "incorrect"].includes(classification)) return "wrong";
  return "none";
}

export function ComparisonResult({ run }: { run: WorkflowRun | null }) {
  const report = extractReport(run);
  if (!report) {
    if (run?.status === "FAILED") return <div className="result-empty error"><strong>Không thể tạo báo cáo</strong><span>{run.error}</span></div>;
    return <div className="result-empty"><strong>Chưa có kết quả</strong><span>Nhập hai bài và bấm “Chấm bài” để bắt đầu.</span></div>;
  }

  const similarity = boundedScore(report.similarity_score ?? report.summary_score ?? 0);
  const aiScore = boundedScore(report.summary_score ?? report.overall_score ?? 0);
  return <div className="similarity-report">
    <section className="golden-chunk-section">
      <div className="result-section-heading"><div><span>01</span><h3>Golden solution được tách thành</h3></div><small>{report.golden_chunks?.length ?? 0} chunks</small></div>
      <div className="golden-chunk-list">{report.golden_chunks?.map((chunk) => <article key={chunk.chunk_id}><strong>{chunk.chunk_id}</strong><p>{chunk.content}</p></article>)}{!report.golden_chunks?.length && <p className="no-evidence">Workflow chưa trả về golden chunks.</p>}</div>
    </section>

    <section className="score-overview">
      <div className="result-section-heading"><div><span>02</span><h3>Mức độ giống của bài sinh viên</h3></div></div>
      <div className="score-primary"><strong>{Math.round(similarity * 100)}%</strong><div><b>Tương đồng tổng thể</b><span>Trung bình vector match tốt nhất của từng student chunk</span></div></div>
      <div className="score-bar" aria-label={`Tương đồng tổng thể ${Math.round(similarity * 100)} phần trăm`}><span style={{ width: `${similarity * 100}%` }} /></div>
      <p className="ai-score-note">Điểm AI gợi ý: <strong>{Math.round(aiScore * 100)}%</strong></p>
    </section>

    <section className="student-chunk-section">
      <div className="result-section-heading"><div><span>03</span><h3>Đối chiếu từng student chunk</h3></div><small>{report.comparisons.length} chunks</small></div>
      <div className="comparison-list">{report.comparisons.map((item, index) => {
        const best = item.matched_golden?.[0];
        const extra = item.matched_golden?.slice(1) ?? [];
        return <article className={`comparison-item comparison-${tone(item.classification)}`} key={`${item.student_chunk_id}-${index}`}>
          <header><div><span>Chunk {index + 1}</span><strong>{item.student_chunk_id}</strong></div><span className="classification">{labels[item.classification] ?? item.classification}</span></header>
          <div className="chunk-pair">
            <div><small>Bài sinh viên</small><p>{item.student_content}</p></div>
            <div className="best-match"><small>{best ? `Golden gần nhất · ${Math.round(boundedScore(best.similarity_score) * 100)}%` : "Golden gần nhất"}</small><p>{best?.content ?? "Không tìm thấy golden chunk đủ tương đồng."}</p></div>
          </div>
          <p className="chunk-reason"><strong>Nhận xét:</strong> {item.explanation}</p>
          {!!extra.length && <details className="more-matches"><summary>Xem thêm {extra.length} golden chunks liên quan</summary>{extra.map((match) => <p key={match.chunk_id}><strong>{match.chunk_id} · {Math.round(boundedScore(match.similarity_score) * 100)}%</strong>{match.content}</p>)}</details>}
        </article>;
      })}</div>
    </section>
  </div>;
}
