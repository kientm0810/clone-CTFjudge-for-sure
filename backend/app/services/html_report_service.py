import json
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

from app.models.workflow import ExecutionProgress, WorkflowRun
from app.schemas.workflow import WorkflowDefinition


VIETNAM_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Saigon")


def _bounded_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0
    if score > 1 and score <= 10:
        score /= 10
    elif score > 10:
        score /= 100
    return min(max(score, 0), 1)


def _submission_label(score: float) -> str:
    if score >= 0.85:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "average"
    return "weak"


def _duration_seconds(started_at: datetime | None, completed_at: datetime | None) -> float:
    if started_at is None or completed_at is None:
        return 0
    return max((completed_at - started_at).total_seconds(), 0)


def _duration_label(seconds: float) -> str:
    minutes, remainder = divmod(max(seconds, 0), 60)
    if minutes >= 1:
        return f"{int(minutes)} phút {remainder:.1f} giây"
    return f"{remainder:.2f} giây"


def _date_label(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(VIETNAM_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")


def _text(value: Any) -> str:
    return escape(str(value if value is not None else "")).replace("\n", "<br>")


def _extract_report(result: dict[str, Any] | None) -> dict[str, Any]:
    outputs = (result or {}).get("outputs")
    if not isinstance(outputs, dict):
        return {}
    direct = outputs.get("report")
    if isinstance(direct, dict):
        return direct
    return next(
        (
            value
            for value in outputs.values()
            if isinstance(value, dict) and isinstance(value.get("comparisons"), list)
        ),
        {},
    )


def _normal_result_html(report: dict[str, Any]) -> str:
    if not report:
        return '<p class="empty">Run không có similarity report có cấu trúc.</p>'

    golden_chunks = report.get("golden_chunks") or []
    comparisons = report.get("comparisons") or []
    golden_html = "".join(
        f'<article class="chunk"><strong>{_text(item.get("chunk_id", "Golden chunk"))}</strong>'
        f'<p>{_text(item.get("content", ""))}</p></article>'
        for item in golden_chunks
        if isinstance(item, dict)
    ) or '<p class="empty">Không có golden chunks trong output.</p>'

    comparison_html: list[str] = []
    for index, item in enumerate(comparisons, 1):
        if not isinstance(item, dict):
            continue
        matches = item.get("matched_golden") or []
        match_html = "".join(
            '<li><strong>{} · {:.0f}%</strong><span>{}</span></li>'.format(
                _text(match.get("chunk_id", "Golden")),
                _bounded_score(match.get("similarity_score")) * 100,
                _text(match.get("content", "")),
            )
            for match in matches
            if isinstance(match, dict)
        ) or "<li>Không có golden evidence tương đồng.</li>"
        comparison_html.append(
            f'<article class="comparison"><header><span>Student chunk {index}</span>'
            f'<strong>{_text(item.get("classification", "unknown"))}</strong></header>'
            f'<div class="student-answer">{_text(item.get("student_content", ""))}</div>'
            f'<p><b>Điểm chunk:</b> {_bounded_score(item.get("score")) * 100:.0f}%</p>'
            f'<p><b>Nhận xét:</b> {_text(item.get("explanation", ""))}</p>'
            f'<details><summary>Golden evidence ({len(matches)})</summary><ul>{match_html}</ul></details>'
            "</article>"
        )

    return f"""
      <section>
        <h2>Kết quả chấm bài</h2>
        <p class="summary">{_text(report.get("summary", ""))}</p>
      </section>
      <section>
        <h2>Golden solution chunks</h2>
        <div class="chunk-grid">{golden_html}</div>
      </section>
      <section>
        <h2>Đối chiếu từng phần bài làm</h2>
        <div class="comparison-list">{''.join(comparison_html) or '<p class="empty">Không có comparison.</p>'}</div>
      </section>
    """


def build_run_html_report(
    run: WorkflowRun,
    definition: WorkflowDefinition,
    progress_items: list[ExecutionProgress],
    model_names: dict[str, str],
) -> str:
    report = _extract_report(run.result)
    score = _bounded_score(
        report.get("summary_score", report.get("overall_score", report.get("similarity_score", 0)))
    )
    label = _submission_label(score)
    progress_by_node = {item.node_id: item for item in progress_items}
    definitions = {node.id: node for node in definition.nodes}

    phase_rows: list[str] = []
    agent_rows: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_inference_seconds = 0.0
    used_models: list[str] = []

    for node_run in run.node_runs:
        node = definitions.get(node_run.node_id)
        duration = _duration_seconds(node_run.started_at, node_run.completed_at)
        phase_rows.append(
            f"<tr><td>{node_run.sequence + 1}</td><td>{_text(node.name if node and node.name else node_run.node_id)}</td>"
            f"<td>{_text(node_run.node_type)}</td><td>{_text(node_run.status)}</td>"
            f"<td>{_duration_label(duration)}</td></tr>"
        )
        if node_run.node_type != "agent":
            continue

        progress = progress_by_node.get(node_run.node_id)
        input_tokens = int(progress.prompt_tokens or 0) if progress else 0
        output_tokens = int(progress.generated_tokens or 0) if progress else 0
        inference_seconds = float(progress.elapsed_seconds or duration) if progress else duration
        speed = output_tokens / inference_seconds * 60 if inference_seconds > 0 else 0
        model_name = model_names.get(node_run.node_id, "Không xác định")
        if model_name not in used_models:
            used_models.append(model_name)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_inference_seconds += inference_seconds
        agent_rows.append(
            f"<tr><td>{_text(node.name if node and node.name else node_run.node_id)}</td>"
            f"<td>{_text(model_name)}</td><td>{input_tokens:,}</td><td>{output_tokens:,}</td>"
            f"<td>{speed:,.1f} token/phút</td></tr>"
        )

    total_duration = _duration_seconds(run.started_at, run.completed_at)
    average_speed = (
        total_output_tokens / total_inference_seconds * 60
        if total_inference_seconds > 0
        else 0
    )
    raw_json = escape(json.dumps(run.result or {}, ensure_ascii=False, indent=2))

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CTFJudge report · {escape(run.id[:8])}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#071217; --panel:#0d2027; --line:#294650; --text:#dcebed; --muted:#87a1aa; --accent:#65d6c0; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.55 Arial,sans-serif; }}
    main {{ width:min(1120px,calc(100% - 32px)); margin:32px auto 72px; }} h1,h2,p {{ margin-top:0; }} h1 {{ margin-bottom:6px; }} h2 {{ font-size:18px; }}
    .muted,.empty {{ color:var(--muted); }} section {{ margin-top:18px; border:1px solid var(--line); border-radius:14px; padding:20px; background:var(--panel); }}
    .hero {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }} .label {{ border:1px solid var(--accent); border-radius:999px; padding:7px 12px; color:var(--accent); font-weight:800; text-transform:uppercase; }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-top:18px; }} .metric {{ border:1px solid var(--line); border-radius:10px; padding:13px; background:#09191f; }}
    .metric small {{ display:block; color:var(--muted); text-transform:uppercase; font-size:10px; }} .metric strong {{ display:block; margin-top:5px; font-size:19px; overflow-wrap:anywhere; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }} th {{ color:var(--accent); font-size:11px; text-transform:uppercase; }}
    .table-wrap {{ overflow:auto; }} .summary {{ font-size:16px; }} .chunk-grid,.comparison-list {{ display:grid; gap:10px; }}
    .chunk,.comparison {{ border:1px solid var(--line); border-radius:10px; padding:14px; background:#09191f; }} .chunk p {{ margin:7px 0 0; }}
    .comparison header {{ display:flex; justify-content:space-between; gap:12px; color:var(--accent); }} .student-answer {{ margin-top:12px; border-left:3px solid var(--accent); padding:9px 12px; background:#0d252b; }}
    details {{ margin-top:10px; }} li {{ margin:8px 0; }} li span {{ display:block; color:#b5c9ce; }} pre {{ max-height:640px; overflow:auto; white-space:pre-wrap; word-break:break-word; color:#b9d0d5; }}
    @media (max-width:700px) {{ .hero {{ flex-direction:column; }} }}
  </style>
</head>
<body><main>
  <div class="hero"><div><p class="muted">CTFJudge · Báo cáo một bài làm</p><h1>Kết quả chấm bài</h1><p class="muted">Run {escape(run.id)} · {_date_label(run.completed_at)}</p></div><span class="label">{label}</span></div>
  <div class="metrics">
    <div class="metric"><small>Điểm gợi ý AI</small><strong>{score * 100:.0f}%</strong></div>
    <div class="metric"><small>Tổng thời gian</small><strong>{_duration_label(total_duration)}</strong></div>
    <div class="metric"><small>Input tokens</small><strong>{total_input_tokens:,}</strong></div>
    <div class="metric"><small>Output tokens</small><strong>{total_output_tokens:,}</strong></div>
    <div class="metric"><small>Inference trung bình</small><strong>{average_speed:,.1f} token/phút</strong></div>
    <div class="metric"><small>Model chấm</small><strong>{_text(', '.join(used_models) or 'Không xác định')}</strong></div>
  </div>
  {_normal_result_html(report)}
  <section><h2>Thời gian từng phase</h2><div class="table-wrap"><table><thead><tr><th>#</th><th>Phase</th><th>Loại</th><th>Trạng thái</th><th>Thời gian</th></tr></thead><tbody>{''.join(phase_rows)}</tbody></table></div></section>
  <section><h2>Token và model theo agent</h2><div class="table-wrap"><table><thead><tr><th>Agent</th><th>Model</th><th>Input token</th><th>Output token</th><th>Tốc độ</th></tr></thead><tbody>{''.join(agent_rows)}</tbody></table></div><p class="muted">Tốc độ được tính theo output token / toàn bộ thời gian gọi model, bao gồm nạp prompt và truyền dữ liệu.</p></section>
  <section><details><summary>Raw JSON output</summary><pre>{raw_json}</pre></details></section>
</main></body></html>"""
