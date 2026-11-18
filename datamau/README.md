# Dataset báo cáo phân tích động (synthetic) – 200 bài

- 200 file .docx theo đúng form 8 mục của bài nộp sinh viên (BÁO CÁO PHÂN TÍCH ĐỘNG).
- Không có ảnh: evidence nằm ở mục "Phụ lục – Evidence (trích log dạng text)", ID E01, E02… khớp với bảng mục 3, 4, 5, 7.
- 8 lab × 25 bài; mỗi lab: 5 excellent, 8 good, 7 average, 5 weak.
- Họ tên/MSSV là giả lập.

## metadata.jsonl (1 dòng / bài)
- file, lab_id, lab_title, sample, student, mssv
- quality_level: excellent | good | average | weak
- variant: privilege (std/admin), runkey (chỉ L01: mẫu có ghi Run key hay không)
- findings_present: các finding chuẩn có trong bài (key theo lab_reference.json)
- issues: lỗi được cài
  - missing:<key>                 thiếu finding
  - noise_claim                   nhận noise (RDP/ubuntu/svchost/Procmon/Defender) là hành vi mẫu
  - unsupported_claim             khẳng định hành vi mẫu không có, không có evidence
  - mixed_conclusion              trộn inferred vào observed
  - privilege_misread             giải thích sai ACCESS DENIED là do Defender
  - evidence_ref_missing          tham chiếu E-ID không tồn tại
  - placeholder_left              còn ô "[...]"
  - timeline_coarse_or_disorder   timeline chỉ giờ:phút và/hoặc đảo thứ tự
  - no_hash                       thiếu SHA-256
- evidence_ids, appendix_items: số khối log trong phụ lục

## lab_reference.json
Danh sách finding chuẩn của từng lab (key, nhóm, essential) để dựng rubric sau.
