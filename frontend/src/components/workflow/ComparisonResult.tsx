import type { ComparisonReport, WorkflowRun } from "@/lib/types";

const labels: Record<string, string> = {
  exact_match: "Trùng khớp", paraphrase: "Tương đồng", partial_match: "Khớp một phần",
  additional_valid_approach: "Cách làm hợp lệ khác", contradiction: "Mâu thuẫn",
  incorrect: "Không chính xác", irrelevant: "Không liên quan", no_match: "Không tìm thấy",
};
const competencyLabels: Record<string, string> = {
  vulnerability_understanding: "Hiểu lỗ hổng", reconnaissance_thoroughness: "Reconnaissance",
  exploitation_methodology: "Phương pháp khai thác", technical_accuracy: "Độ chính xác kỹ thuật",
  efficiency_approach: "Hiệu quả tiếp cận", adaptability: "Khả năng thích nghi",
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
  if (!report) return <pre>{run?.result ? JSON.stringify(run.result, null, 2) : "Kết quả sẽ xuất hiện tại đây."}</pre>;
  const score = boundedScore(report.overall_score ?? report.summary_score ?? 0);
  return <div className="comparison-report">
    <div className="report-summary"><div className="score-ring"><strong>{Math.round(score * 100)}</strong><span>%</span></div><div><small className="score-caption">Điểm AI gợi ý cho toàn bài</small><p>{report.summary || "Đã hoàn tất phân tích."}</p>{typeof report.challenge_solved === "boolean" && <span className={`solved-badge ${report.challenge_solved ? "solved" : "unsolved"}`}>{report.challenge_solved ? "SOLVED" : "NOT SOLVED"}</span>}</div></div>
    {report.competency_matrix && <div className="competency-grid">{Object.entries(report.competency_matrix).map(([key, rating]) => { const detail = report.formula_breakdown?.[key]; return <article className="competency-item" key={key}><span>{competencyLabels[key] ?? key}</span><strong>{rating}</strong>{detail && <small>{Math.round(boundedScore(detail.score) * 100)}% · trọng số {Math.round(detail.weight * 100)}%</small>}</article>; })}</div>}
    {(report.detailed_comparison || report.key_insights) && <div className="judge-notes">{report.detailed_comparison && <div><h4>Đánh giá tổng quan</h4><p>{report.detailed_comparison}</p></div>}{report.key_insights && <div><h4>Nhận xét chính</h4><p>{report.key_insights}</p></div>}</div>}
    {report.challenge_solved === false && report.failure_analysis && <div className="failure-panel"><h4>Phân tích phần còn thiếu</h4><p>{report.failure_analysis}</p></div>}
    <div className="comparison-list">{report.comparisons.map((item, index) => {
      const aiScore = boundedScore(item.score);
      const vectorScore = Math.max(0, ...(item.matched_golden ?? []).map((match) => boundedScore(match.similarity_score)));
      return <article className={`comparison-item comparison-${tone(item.classification)}`} key={`${item.student_chunk_id}-${index}`}>
        <div className="comparison-heading"><span>Trích dẫn · {item.student_chunk_id}</span><span className="classification">{labels[item.classification] ?? item.classification}</span></div>
        <p className="student-content">“{item.student_content}”</p>
        <div className="chunk-scores"><div><span>Độ giống vector cao nhất</span><strong>{Math.round(vectorScore * 100)}%</strong></div><div><span>Điểm AI gợi ý</span><strong>{Math.round(aiScore * 100)}%</strong></div></div>
        <p className="explanation">{item.explanation}</p>
        {!!item.matched_golden?.length ? <div className="golden-citations"><h4>Đối chiếu với golden solution</h4>{item.matched_golden.map((match) => <blockquote key={match.chunk_id}><div><strong>{match.chunk_id}</strong>{typeof match.similarity_score === "number" && <span>{Math.round(boundedScore(match.similarity_score) * 100)}% tương đồng</span>}</div><p>{match.content}</p></blockquote>)}</div> : <p className="no-evidence">Không tìm thấy đoạn golden đủ tương đồng.</p>}
      </article>;
    })}</div>
  </div>;
}
