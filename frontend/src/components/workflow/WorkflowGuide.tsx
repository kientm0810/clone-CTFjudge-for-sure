type JourneyProps = {
  hasWorkflow: boolean;
  hasRun: boolean;
  runCompleted: boolean;
};

const steps = [
  { title: "Chọn workflow", description: "Workflow là bản hướng dẫn cho hệ thống biết phải làm việc theo thứ tự nào." },
  { title: "Kiểm tra sơ đồ", description: "Nhìn các đường nối từ Input đến Output. Nếu cần thay đổi, bấm Sửa ở workflow." },
  { title: "Nhập bài làm", description: "Dán golden solution và bài sinh viên vào ô dữ liệu ở phía dưới." },
  { title: "Chạy và đọc kết quả", description: "Bấm Chạy workflow, rồi xem điểm và từng câu được đối chiếu." },
];

export function WorkflowJourney({ hasWorkflow, hasRun, runCompleted }: JourneyProps) {
  const current = !hasWorkflow ? 0 : !hasRun ? 2 : runCompleted ? 4 : 3;
  return (
    <section className="journey-card" aria-labelledby="journey-title">
      <div className="journey-heading">
        <div>
          <p className="section-label">Bắt đầu từ đây</p>
          <h2 id="journey-title">4 bước để chấm một bài</h2>
        </div>
        <span>{Math.min(current + 1, 4)}/4</span>
      </div>
      <ol className="journey-steps">
        {steps.map((step, index) => {
          const done = index < current;
          const active = index === current;
          return (
            <li className={`${done ? "done" : ""} ${active ? "active" : ""}`} key={step.title}>
              <span className="step-number" aria-hidden="true">{done ? "✓" : index + 1}</span>
              <div><strong>{step.title}</strong><small>{step.description}</small></div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

const nodeHelp = [
  { type: "input", name: "Input", plain: "Cửa nhận dữ liệu", detail: "Nhận golden solution hoặc bài làm sinh viên khi bạn bấm Chạy." },
  { type: "agent", name: "Agent", plain: "Bộ não AI", detail: "Gửi dữ liệu cùng prompt cho model. Prompt là lời dặn AI phải làm gì." },
  { type: "database", name: "Database", plain: "Tủ nhớ vector", detail: "Store để cất đoạn golden; Search để tìm đoạn golden gần giống bài sinh viên." },
  { type: "output", name: "Output", plain: "Bàn giao kết quả", detail: "Gom câu trả lời cuối cùng thành báo cáo, điểm số và phần so sánh." },
];

export function NodeGuide() {
  return (
    <details className="node-guide">
      <summary>
        <span><strong>Các node làm gì?</strong><small>Mở hướng dẫn ngắn, không cần biết trước về AI.</small></span>
        <span className="summary-action">Xem giải thích</span>
      </summary>
      <div className="node-guide-grid">
        {nodeHelp.map((node, index) => (
          <article className={`node-help node-help-${node.type}`} key={node.type}>
            <span className="node-order">{index + 1}</span>
            <div><p>{node.name}</p><strong>{node.plain}</strong><small>{node.detail}</small></div>
          </article>
        ))}
      </div>
    </details>
  );
}

export function EditorJourney() {
  return (
    <ol className="editor-journey" aria-label="Các bước tạo workflow">
      <li><span>1</span><strong>Thêm node</strong><small>Bấm node bên trái</small></li>
      <li><span>2</span><strong>Nối node</strong><small>Kéo từ OUT sang IN</small></li>
      <li><span>3</span><strong>Cấu hình</strong><small>Chọn node và điền bên phải</small></li>
      <li><span>4</span><strong>Lưu</strong><small>Tạo workflow hoặc version mới</small></li>
    </ol>
  );
}
