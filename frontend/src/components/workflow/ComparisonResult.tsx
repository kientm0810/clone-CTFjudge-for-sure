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

function extractReport(run: WorkflowRun | null): ComparisonReport | null {
  const outputs = run?.result?.outputs;
  if (!outputs || typeof outputs !== "object" || Array.isArray(outputs)) return null;
  const report = (outputs as Record<string, unknown>).report;
  if (!report || typeof report !== "object" || Array.isArray(report)) return null;
  const candidate = report as Partial<ComparisonReport>;
  if (!Array.isArray(candidate.comparisons)) return null;
  return {
    summary_score: Number(candidate.summary_score ?? 0),
    summary: String(candidate.summary ?? ""),
    comparisons: candidate.comparisons,
  };
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
    return <pre>{run?.result ? JSON.stringify(run.result, null, 2) : "Kết quả sẽ xuất hiện tại đây."}</pre>;
  }

  return (
    <div className="comparison-report">
      <div className="report-summary">
        <div className="score-ring"><strong>{Math.round(report.summary_score * 100)}</strong><span>%</span></div>
        <p>{report.summary || "Đã hoàn tất phân tích."}</p>
      </div>
      <div className="comparison-list">
        {report.comparisons.map((item, index) => (
          <article className={`comparison-item comparison-${tone(item.classification)}`} key={`${item.student_chunk_id}-${index}`}>
            <div className="comparison-heading">
              <span>Đoạn sinh viên {index + 1}</span>
              <span className="classification">{labels[item.classification] ?? item.classification}</span>
              <strong>{Math.round(Number(item.score) * 100)}%</strong>
            </div>
            <p className="student-content">{item.student_content}</p>
            <p className="explanation">{item.explanation}</p>
            {!!item.matched_golden?.length && (
              <details>
                <summary>{item.matched_golden.length} đoạn golden tương đồng</summary>
                {item.matched_golden.map((match) => (
                  <blockquote key={match.chunk_id}>
                    {match.content}
                    {typeof match.similarity_score === "number" && <small>Vector score: {match.similarity_score.toFixed(3)}</small>}
                  </blockquote>
                ))}
              </details>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
