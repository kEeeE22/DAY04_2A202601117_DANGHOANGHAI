# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. Xong trước 11:30 để làm tài liệu phụ trợ khi demo.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. Có thể hoàn thiện sau buổi debate để nộp bài.

## Team

- Team:
- Members:
  - Đặng Hoàng Hải - 2A202601117
  - Dương Ngọc Tiến - 2A202601401
  - Nguyễn Minh Huy - 2A202601303
  - Nguyễn Mạnh Hiệp - 2A202601319
  - Ngô Phương Nam - 2A202601231
- Provider/model: gpt-4o (OpenAI)

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

**Paper Scout** — trợ lý nghiên cứu chuyên tìm, đọc và trích dẫn bài báo khoa học trên arXiv.

Agent có thể:
- Tìm bài báo theo từ khóa/chủ đề trên arXiv
- Đọc và tóm tắt nội dung bài báo từ arXiv ID hoặc URL
- Tra cứu metadata trích dẫn (authors, venue, BibTeX, references) qua OpenAlex
- Trình bày kết quả thành digest/bản tin có cấu trúc
- Hỏi lại khi thiếu thông tin thay vì đoán
- Tra cứu policy nội bộ về trích dẫn, data privacy, xuất bản

**Link dùng thử (truy cập được trong showdown):**

> URL: _(localhost / demo trực tiếp trên máy trình chiếu)_

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `papers` | Tìm kiếm bài báo khoa học trên arXiv theo từ khóa/chủ đề | Không |
| `paper_text` | Tải và trích xuất nội dung text từ PDF bài báo arXiv | Không |
| `citation_lookup` | Tra cứu metadata trích dẫn (tác giả, venue, năm, BibTeX, references) qua OpenAlex API | **Có** |
| `format` | Trình bày dữ liệu đã có thành văn bản / bản tin có cấu trúc | Không |
| `clarify` | Hỏi lại người dùng khi thiếu thông tin bắt buộc | Không |
| `policy` | Tra cứu chính sách nội bộ công ty (source_citation, data_privacy, external_publishing…) | Không |
| `lookup` | Tìm kiếm web tổng quát | Không |
| `fetch` | Đọc nội dung từ một URL cụ thể | Không |
| `social_search` | Tìm trên mạng xã hội | Không |
| `timeline` | Lấy bài đăng gần đây của một tài khoản | Không |
| `send` | Gửi bản tin đi (Telegram) | Không |

## A3. Câu hỏi mẫu để thử

1. `Tìm cho mình các bài báo mới nhất về LLM reasoning trên ArXiv`
2. `Cho mình xem thông tin trích dẫn của bài báo 2005.14165`
3. `Tải và đọc nội dung bài báo https://arxiv.org/abs/1706.03762`
4. `Tìm kiếm giúp mình một số bài báo mới` _(→ agent sẽ hỏi lại chủ đề)_
5. `Công ty có quy định gì về trích dẫn nguồn khi xuất bản bài báo không?`

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| Tìm bài báo theo chủ đề | `papers(query="LLM reasoning")` | v1→v2: stable routing | `v1_B_group_openai_20260729T120318985025.json` G01 ✅ |
| Tra cứu citation qua arXiv ID | `citation_lookup(arxiv_id="2301.00001")` | Tool mới thêm vào v1 | `v1_B_group_openai_20260729T120318985025.json` G02 ✅ |
| Đọc nội dung bài báo | `paper_text(arxiv_url="https://arxiv.org/abs/2301.00001")` | Phân biệt rõ paper_text vs citation_lookup | `v1_B_group_openai_20260729T120318985025.json` G03 ✅ |
| Thiếu thông tin → clarify | `clarify(response_type="text")` | G09 regression ở v3 cho thấy cần thêm rule | `v3_B_group_openai_20260729T122153922687.json` G09 ❌ |
| Hỏi policy nội bộ | `policy(query="trích dẫn", policy_area="source_citation")` | G10 arg mismatch còn tồn tại cả 3 run | `v1/v2/v3_B_group` G10 ❌ |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: `provider_error_cases` phải bằng `0`; `measured_cases` phải bằng `total_cases`; và bất kỳ `tool_results` nào có error đều phải được review thủ công vì routing PASS không chứng minh tool execution đã đúng.

## B1. Version evidence

Dữ liệu từ `artifacts/version_log.csv` và `runs/*.json`.

| Version | Suite / Provider | Artifact version | Prompt/tool change | Hypothesis | metric_name | Before | After | Run File |
|---|---|---|---|---|---|---:|---:|---|
| v1 | group / openai gpt-4o | `v1+p853d6882ad55+tb3b6576ab393` | Baseline: system prompt Paper Scout + tools khai báo `citation_lookup`, `papers`, `paper_text` | Agent định tuyến đúng các tool nghiên cứu cơ bản | case_accuracy | — | **0.80** (8/10) | `v1_B_group_openai_20260729T120318985025.json` |
| v2 | group / openai gpt-4o | `v2+p853d6882ad55+tb3b6576ab393` | Re-run group — kiểm tra tính ổn định (prompt/tools **không đổi**, hash giống v1) | Kết quả giữ nguyên → xác nhận tính tái lập | case_accuracy | 0.80 | **0.80** (8/10) | `v2_B_group_openai_20260729T121422634236.json` |
| v3 | group / openai gpt-4o | `v3+p853d6882ad55+tb3b6576ab393` | Re-run group — G09 regression: agent gọi `papers` thay vì `clarify` khi thiếu topic | System prompt chưa đủ rule cho multi-turn ambiguous query | case_accuracy | 0.80 | **0.70** (7/10) | `v3_B_group_openai_20260729T122153922687.json` |

**Nhận xét:** v1 và v2 có cùng `prompt_hash` + `tools_hash` → không có thay đổi artifact thực sự; kết quả ổn định (8/10 cả hai lần). v3 xuất hiện regression ở G09 — lỗi non-determinism của model, không phải do thay đổi artifact.

## B2. Failure analysis

Failures thực tế từ `results[*].result.failures` trong các run files.

| Case ID | Suite | Failure Type | Actual Tool Calls | Expected | What Failed | Fix đề xuất |
|---|---|---|---|---|---|---|
| G07_multi_format_digest | group | wrong_arg_value | `format(template="daily_ai_vn")` | `format(template="sections")` | Agent chọn template `daily_ai_vn` thay vì `sections` khi user nói "bản tin tổng hợp" | Thêm hướng dẫn: "bản tin tổng hợp" → `sections` |
| G09_multi_missing_topic_clarify | group (v3 only) | missing_info | `papers(query=...)` | `clarify(response_type="text")` | v3 regression: agent tự đoán query và gọi `papers` khi user chưa nói chủ đề | Làm rõ trong system prompt: query mơ hồ → phải `clarify` |
| G10_multi_policy_lookup | group | wrong_arg_value | `policy(query="trích dẫn nguồn tài liệu tham khảo")` | `policy(query="trích dẫn")` | Agent truyền query quá dài/chi tiết, không khớp expected exact match | Hướng dẫn dùng keyword ngắn cho `policy query` |

## B3. Team eval cases

10 cases tự thiết kế trong `data/eval_group.json` — 5 single-turn và 5 multi-turn:

| Case ID | What It Tests | Expected Tool/Behavior | Result (v1/v2/v3) |
|---|---|---|---|
| G01_single_paper_search | Routing tìm bài báo theo từ khóa → `papers` | `papers(query="LLM reasoning")` | ✅ / ✅ / ✅ |
| G02_single_citation_lookup | Routing tra cứu citation qua arXiv ID → `citation_lookup` | `citation_lookup(arxiv_id="2301.00001")` | ✅ / ✅ / ✅ |
| G03_single_paper_text_extract | Routing đọc bài báo khi đã có URL → `paper_text` | `paper_text(arxiv_url="https://arxiv.org/abs/2301.00001")` | ✅ / ✅ / ✅ |
| G04_single_missing_paper_id | Thiếu URL/ID → phải `clarify` hỏi lại | `clarify(response_type="text")` | ✅ / ✅ / ✅ |
| G05_single_out_of_scope | Yêu cầu code Python không liên quan → không dùng tool | `no_tool` | ✅ / ✅ / ✅ |
| G06_multi_search_then_cancel | Lượt 2 hỏi về khả năng agent → trả lời trực tiếp, không tool | `no_tool` | ✅ / ✅ / ✅ |
| G07_multi_format_digest | Trình bày danh sách bài báo thành bản tin → `format(template="sections")` | `format(template="sections")` | ❌ / ❌ / ❌ (chọn `daily_ai_vn`) |
| G08_multi_search_specific_arg | Trích xuất đúng `max_results=10` từ lượt hội thoại | `papers(query="Transformer architecture", max_results=10)` | ✅ / ✅ / ✅ |
| G09_multi_missing_topic_clarify | Muốn tìm bài nhưng không nói chủ đề → `clarify` | `clarify(response_type="text")` | ✅ / ✅ / ❌ (v3 regression) |
| G10_multi_policy_lookup | Hỏi policy trích dẫn nội bộ → `policy(policy_area="source_citation")` | `policy(query="trích dẫn", policy_area="source_citation")` | ❌ / ❌ / ❌ (query arg quá dài) |

**Tổng kết group eval:** 8/10 (v1, v2), 7/10 (v3)

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Run File | Outcome |
|---|---|---|---|---|
| G01 — Tìm bài về LLM reasoning | v1 | `papers(query="LLM reasoning", max_results=5)` | `v1_B_group_openai_...` | ✅ PASS |
| G02 — Citation lookup arXiv 2301.00001 | v1 | `citation_lookup(arxiv_id="2301.00001")` | `v1_B_group_openai_...` | ✅ PASS |
| G03 — Đọc nội dung bài 2301.00001 | v1 | `paper_text(arxiv_url="https://arxiv.org/abs/2301.00001")` | `v1_B_group_openai_...` | ✅ PASS |
| G04 — Thiếu ID bài báo | v1 | `clarify(response_type="text")` | `v1_B_group_openai_...` | ✅ PASS |
| G07 — Format digest | v1 | `format(template="daily_ai_vn")` ← sai | `v1_B_group_openai_...` | ❌ FAIL |
| G09 — Thiếu topic multi-turn | v3 | `papers(query="...")` thay vì `clarify` | `v3_B_group_openai_...` | ❌ FAIL (regression) |
| G10 — Policy trích dẫn | v1 | `policy(query="trích dẫn nguồn tài liệu tham khảo")` ← arg dài | `v1_B_group_openai_...` | ❌ FAIL |


## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới `citation_lookup` | `v1_B_group_openai_...json` — G02 PASS | Tra cứu đúng arXiv ID `2301.00001` → trả về title, authors, BibTeX, references qua OpenAlex API | OpenAlex không có BibTeX sẵn → tool tự sinh từ metadata; cần review thủ công nếu venue thiếu |
| Optional built-in: `papers` | G01, G08 PASS (cả 3 runs) | Tìm đúng bài theo query, truyền đúng `max_results=10` khi user nói rõ | arXiv rate-limit 3s/request; tool đã có retry logic |
| Optional built-in: `paper_text` | G03 PASS (cả 3 runs) | Đọc đúng bài từ URL arXiv đầy đủ | PDF scraping có thể thất bại với bài scan/hình ảnh |
| Optional built-in: `policy` | G10 FAIL — arg mismatch | Routing đúng tool (policy), đúng `policy_area="source_citation"` | `query` arg quá dài so với expected → cần normalize keyword ngắn |
| Optional built-in: `format` | G07 FAIL — sai template | Routing đúng tool `format` | Agent chọn `daily_ai_vn` thay vì `sections`; system prompt cần liệt kê rõ khi nào dùng template nào |

## B6. Reflection

**Những fix thuộc về `system_prompt.md`:**
- Thêm rule rõ ràng: khi query tìm bài báo mơ hồ (không có từ khóa) → phải `clarify` trước, không được tự đoán và gọi `papers` (fix G09 regression)
- Thêm hướng dẫn template: "bản tin tổng hợp" / "digest" → `format(template="sections")`, không phải `daily_ai_vn` (fix G07)
- Hướng dẫn `policy query` dùng keyword ngắn (1–3 từ), không copy nguyên câu user (fix G10)

**Những fix thuộc về `tools.yaml`:**
- Thêm ví dụ trong description của `citation_lookup` để phân biệt với `paper_text`
- Thêm note trong `policy` description: `query` nên ngắn, là keyword (không phải câu đầy đủ)
- Thêm note trong `format` description: giải thích rõ từng template (`sections` = bản tin có mục, `daily_ai_vn` = định dạng cụ thể)

**Những failure cần review thủ công thay vì grading tự động:**
- G10: routing đúng tool + đúng `policy_area`, chỉ fail vì `query` arg dài hơn expected exact string → grading tự động quá strict; kết quả thực tế vẫn có thể đúng về mặt semantic
- G07: agent chọn `daily_ai_vn` thay vì `sections` — cả hai đều là template hợp lệ, chỉ khác về định dạng output; cần human review xem output có phù hợp không

**Sẽ cải thiện gì tiếp theo:**
1. Fix G09/G07/G10 bằng cách chỉnh system prompt theo phân tích ở trên
2. Thêm test case covering `citation_lookup` với DOI và title (hiện tại chỉ test arXiv ID)
3. Thêm `max_results` default guard trong `papers` tool để tránh trả về quá nhiều kết quả
4. Cân nhắc thêm semantic matching cho `policy query` thay vì exact string match trong eval
