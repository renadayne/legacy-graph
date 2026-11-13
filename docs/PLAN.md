# Kế hoạch mfcgraph v0.2: `mfc_explore`

> Dành cho Claude Code. Mỗi lần **chỉ làm một step**. Đọc mục 1–3 một lần; khi làm step nào thì chỉ đọc mục của step đó và phụ lục nó trỏ tới.

## 0. Môi trường chạy

- Chạy bằng **Claude Code cloud** trên repo GitHub có sẵn của người dùng. Repo đã chứa code v0.1, `CLAUDE.md` và file này.
- Làm việc trên **nhánh của phiên** (ví dụ `claude/...`), không làm thẳng trên `main`. Mỗi step là một commit trên nhánh đó, push ngay sau mỗi step, và giữ một pull request mở cho nhánh. Người dùng tự merge vào `main`.
- Một phiên có thể làm nhiều step liên tiếp. Nếu phiên mới bắt đầu giữa chừng, đọc `docs/STATUS.md` để biết step tiếp theo.
- Câu lệnh khởi động gợi ý: *"Đọc CLAUDE.md và docs/PLAN.md, rồi làm step tiếp theo theo docs/STATUS.md."*

## 1. Mục tiêu v0.2

Dev chỉ khoanh được vùng bug trong một module lớn. Copilot cần một **bản đồ** để tìm đúng chỗ, với ít token. v0.1 đã có dữ liệu đồ thị MFC tốt (menu → ID → message map → handler, DDX, PostMessage…), nhưng đưa cho agent 9 tool rời rạc. v0.2 làm theo mô hình CodeGraph (xem `docs/research-codegraph.md`):

- **Một tool chính `mfc_explore(query)`.** `query` có thể là: mô tả bug, tên hàm/lớp, `Class::Method`, `File.cpp:120`, thư mục module, caption menu, ID (`ID_FILE_EXPORT`, `IDD_…`), hoặc **chuỗi thông báo lỗi**.
- **Một lần gọi trả về, có trần ký tự:** code có số dòng của các hàm liên quan nhất (cắt cửa sổ, chia ngân sách theo mức liên quan), luồng gọi giữa chúng (kể cả bước MFC), phạm vi ảnh hưởng, danh sách "chưa hiện", và gợi ý tên khi gõ sai.

**Tiêu chí hoàn thành v0.2:**
- Đánh giá ở S9: recall ≥ 0,9 (code cần thiết *có mặt trong phần source*), 100% kết quả nằm trong ngân sách ký tự.
- Mọi test đều đạt; không vi phạm ràng buộc trong `CLAUDE.md`.

## 2. Chính sách phân bổ model (tiết kiệm chi phí)

**Quy tắc quyết định**, áp dụng cho từng step. Chỉ giao cho subagent khi **đủ cả 4 điều kiện**:
1. Spec viết được trọn trong một brief dưới 1 trang (input/output/hành vi rõ ràng).
2. Chạm tối đa 3 file.
3. Kiểm chứng được bằng test tự động.
4. Không cần phán đoán thiết kế: không phải chọn trọng số, thuật toán, hay đánh đổi.

Nếu thiếu bất kỳ điều kiện nào, **model chính tự làm**. Giao việc khó cho model nhỏ thường tốn hơn vì phải làm lại.

| Subagent | Model | Dùng cho |
| --- | --- | --- |
| `implementer` | Sonnet | Code theo brief đã đặc tả rõ |
| `sample-writer` | Sonnet | Viết code MFC giả làm dữ liệu test |
| `doc-writer` | Haiku | README, file hướng dẫn, ví dụ cấu hình |
| (model chính) | Opus | Thiết kế, xếp hạng/phân bổ của explore, tinh chỉnh, review mọi diff |

Nếu model chính của phiên đang là Sonnet thì không cần giao cho `implementer` (cùng model, chỉ thêm chi phí khởi động). Lúc đó chỉ giao việc cho `doc-writer`.

**Mẫu brief** (model chính viết, tối đa 1 trang):
```
TASK <Sx> — <tên>
Goal: <1–2 câu>
Read only: CLAUDE.md, <file>(dòng a–b hoặc tên hàm), <docs/STATUS.md nếu cần>
Modify only: <≤3 file>
Interface: <chữ ký hàm / cấu trúc dữ liệu chính xác>
Spec: <gạch đầu dòng hành vi, gồm cả trường hợp biên>
Tests: <file test + từng case cụ thể>
Done when: python3 tests/test_mfcgraph.py và test mới đều pass; không file nào khác bị đổi
Out of scope: <những gì KHÔNG làm>
```

**Khi xong mỗi step: tự động commit và push lên GitHub** (chi tiết trong `CLAUDE.md` mục "Finishing a step"):
1. Mọi test pass, rồi ghi tối đa 6 dòng vào `docs/STATUS.md`.
2. `git add` **đúng các file của step**, commit với message `S<id>: <tóm tắt>`, phần thân liệt kê file đã đổi và dòng kết quả test.
3. `git push`. Push lỗi thì không force-push, không thử lại liên tục: báo lỗi và để commit ở máy.
4. Test fail thì **không commit**.
5. Subagent không tự commit; model chính commit sau khi đã review diff.

**Tiết kiệm ngữ cảnh (cho mọi model):**
- Mỗi step xong thì thêm **tối đa 6 dòng** vào `docs/STATUS.md`: đã đổi gì, interface mới, file mới. Step sau đọc `STATUS.md` thay vì đọc lại code.
- Module mới phải có docstring đầu file mô tả interface. Subagent đọc docstring, không đọc cả module.
- Dùng `grep -n` để lấy khoảng dòng cần đọc; không đọc nguyên file lớn (`extract_cpp.py`, `resolve.py`, `query.py`).
- Không nghiên cứu lại CodeGraph; dùng `docs/research-codegraph.md`.

## 3. Tổng quan các step

| Step | Việc | Model | Phụ thuộc | Cỡ |
| --- | --- | --- | --- | --- |
| S0 | Khung golden test cho output CLI | implementer | — | S |
| S1 | Dự án mẫu thứ hai + kịch bản bug | sample-writer, model chính review | S0 | M |
| S2a | Thu chuỗi literal trong thân hàm (extractor) | implementer | S0 | S |
| S2b | Index format v2: chuỗi + mtime/size file | implementer | S2a | S |
| S2c | Tìm theo chuỗi (`search` hiện có) | implementer | S2b | S |
| S3a | Thu tham chiếu biến thành viên đọc/ghi (extractor) | implementer | S0 | S |
| S3b | Resolve tham chiếu → field của lớp, lưu index | implementer | S3a, S2b | S |
| S3c | Lệnh `refs` | implementer | S3b | S |
| S4 | Bộ phân tích câu hỏi explore (`explore_query.py`) | implementer | — | S |
| S5 | Seeding + gợi ý tên (`explore_seed.py`) | implementer, model chính review | S2c, S3b, S4 | M |
| S6 | Xếp hạng + luồng chính (`explore_rank.py`) | **model chính** | S5 | L |
| S7a | Tiện ích cửa sổ code / lược dòng / đánh số dòng | implementer | — | S |
| S7b | Phân bổ ngân sách + ghép kết quả (`explore_render.py`) | **model chính** | S6, S7a | L |
| S8 | Nối vào CLI + MCP (một tool mặc định) | implementer | S7b | S |
| S9 | Bộ đánh giá + tinh chỉnh | harness: implementer; tinh chỉnh: **model chính** | S1, S8 | M |
| S10 | Cảnh báo file đã đổi sau khi index | implementer | S2b, S8 | S |
| S11 | Bổ sung `diagnose` | implementer | S2b, S3b | S |
| S12 | Tài liệu v0.2 + mẫu hướng dẫn Copilot | doc-writer | S8–S11 | S |
| S13 | Đo hiệu năng trên cây lớn | implementer | S8 | S |
| S14 | Script đóng gói + CHANGELOG | doc-writer | S12 | S |

S2, S3 và S4, S7a không phụ thuộc nhau, có thể làm song song.

---

## 4. Chi tiết từng step

### S0 — Khung golden test
- **Mục tiêu:** khóa output hiện tại, để mọi thay đổi sau đều thấy diff.
- **Đọc:** `mfcgraph_core/cli.py` (hàm `main`), danh sách file trong `samples/LegacyApp/`.
- **Sửa/tạo:** `tests/golden_test.py`, `tests/golden/*.txt`.
- **Spec:** danh sách lệnh cố định (trace Export, trace IDD_EXPORT, callers CLegacyDoc::Recalculate, callees RefreshAny, impact CLegacyDoc::ExportCsv, context CExportDlg::OnOK, msgmap CLegacyApp, search recalc, diagnose). Gọi `cli.main([...])` trong tiến trình (không dùng subprocess), bắt stdout. So với file `.txt`; có cờ `--update` để ghi lại. Index vào thư mục tạm, không ghi vào `samples/`.
- **Nghiệm thu:** pass trên code hiện tại; sửa một ký tự trong file golden thì test fail và in diff.

### S1 — Dự án mẫu thứ hai + kịch bản bug
- **Mục tiêu:** dữ liệu đủ "khó" để đánh giá explore. Hiện chỉ có 15 file mẫu.
- **Tạo:** `samples/BigApp/` với 2–3 thư mục module (ví dụ `Billing/`, `Report/`, `Common/`), khoảng 40–60 file; `tests/scenarios.json`.
- **Pattern cần có:**
  - Thông báo lỗi qua `AfxMessageBox(_T(...))`, `AfxMessageBox(IDS_…)` + STRINGTABLE, macro log tự định nghĩa `LOG_ERROR(...)`.
  - Một biến thành viên bị gán ở 3+ nơi (một nơi qua DDX).
  - Hàm `static` trùng tên ở hai file `.cpp`; method overload.
  - MDI: `CMultiDocTemplate`, `CMDIChildWnd`; `CPropertySheet` + 2 `CPropertyPage`.
  - `ON_NOTIFY(LVN_ITEMCHANGED, IDC_LIST, …)` trên `CListCtrl`.
  - Worker thread `AfxBeginThread(ThreadProc, this)` gửi `PostMessage(WM_APP_xxx)` về cửa sổ.
  - Một file `.cpp` mã CP932, một file `.rc2`, một khối `#ifdef` có code thật ở nhánh `#else`.
- **`scenarios.json`:** 12–15 kịch bản điều tra bug, mỗi kịch bản gồm `query` (cách dev thật sự hỏi: "bấm Tính lại thì tổng tiền sai trong module Billing", "thông báo 'Không thể lưu hóa đơn'", `Billing/InvoiceDlg.cpp:88`…), `must_include` (các hàm phải có code trong output), `max_chars`.
- **Phân việc:** model chính viết danh sách kịch bản và cấu trúc thư mục vào brief; `sample-writer` viết code cho khớp; model chính review xem kịch bản có thực tế không.
- **Nghiệm thu:** `index` chạy không lỗi; `diagnose` cho thấy 0 file lệch ngoặc; các hàm trong `must_include` đều tồn tại trong index.

### S2a — Thu chuỗi literal (extractor)
- **Đọc:** `extract_cpp.py` (`scan_body`, `RawFunc`), `model.py` (`RawFunc`).
- **Sửa:** `extract_cpp.py`, `model.py`.
- **Spec:** trong `scan_body`, thu mọi token STRING thành `(line, text)` vào `RawFunc.strings`. Bỏ chuỗi có dưới 3 chữ cái và chuỗi chỉ là format (`"%d"`, `"\r\n"`). Cắt mỗi chuỗi ở 200 ký tự. Ghép các literal liền kề (`"abc" "def"`) thành một.
- **Test:** hàm `CMainFrame::OnFileExport` có chuỗi `Export failed` ở dòng 68.

### S2b — Index format v2
- **Đọc:** `index.py` (`save_graph`, `load_graph`), `resolve.py` (`make_calls` phần cuối), `model.py` (`Graph`).
- **Sửa:** `index.py`, `resolve.py`, `model.py`.
- **Spec:** thêm `Graph.texts = [(func_node, line, text)]` và bản ghi `T\tfunc\tline\ttext`. Bản ghi `F` thêm 2 cột `mtime`, `size` ở cuối. Header `MFCGRAPH\t2`. `load_graph` vẫn đọc được v1 (khi đó các trường mới để rỗng).
- **Test:** vòng lưu/đọc giữ nguyên texts; đọc được một file index v1 mẫu (tạo bằng code cũ, lưu trong `tests/data/`).

### S2c — Tìm theo chuỗi
- **Sửa:** `query.py` (`q_search`), test.
- **Spec:** `search "Export failed"` trả về dòng `[text] "Export failed"  CMainFrame::OnFileExport  MainFrm.cpp:68`. Khớp chuỗi con, không phân biệt hoa thường; tiếng Việt so sánh sau khi chuẩn hóa NFC.

### S3a — Tham chiếu biến thành viên (extractor)
- **Sửa:** `extract_cpp.py`, `model.py`.
- **Spec:** trong thân hàm, ghi `(name, recv, line, mode)` cho identifier không đứng trước `(` và: (a) đứng sau `.` hoặc `->`, hoặc (b) bắt đầu bằng `m_`, `g_`, `s_`. `mode='w'` nếu token kế tiếp là `= += -= *= /= |= &= ^= <<= >>= ++ --`, hoặc ngay trước là `++`/`--`; ngược lại là `'r'`. Không ghi `==`.
- **Test:** trong `CLegacyView::OnViewZoom` có 3 lần ghi `m_nZoom`.

### S3b — Resolve tham chiếu
- **Sửa:** `resolve.py`, `index.py`, `model.py`.
- **Spec:** gắn `name` với field của lớp sở hữu hàm (kể cả lớp cha); có `recv` thì dùng kiểu của receiver như phần resolve lời gọi đang làm. Lưu `Graph.refs = [(func_node, line, "Class::field", mode)]`, bản ghi `R`. DDX cũng tính là ghi (`mode='w'`, ở hàm `DoDataExchange`).
- **Test:** `CExportDlg::m_strPath` được ghi trong `DoDataExchange` (DDX) và trong `OnBnClickedBrowse`.

### S3c — Lệnh `refs`
- **Sửa:** `query.py`, `cli.py`, test.
- **Spec:** `refs CExportDlg::m_strPath` liệt kê nơi ghi trước, nơi đọc sau, mỗi dòng gồm hàm và `file:line`.

### S4 — Phân tích câu hỏi explore
- **Tạo:** `mfcgraph_core/explore_query.py`, `tests/test_explore_query.py`. Không phụ thuộc module nào khác.
- **Interface:** `parse_query(text) -> list[Term]`, trong đó `Term(kind, value, extra)` với `kind ∈ {anchor, path, qualified, id, quoted, ident, word}`.
- **Spec:**
  - `anchor`: `File.cpp:120` hoặc `File.cpp:100-140` (đường dẫn có `\` hoặc `/` đều được).
  - `path`: token có `/` hoặc `\`, hoặc có đuôi `.cpp/.h/.rc…`; thư mục cũng là `path`.
  - `qualified`: `A::B`, cũng chấp nhận `A.B` khi A là PascalCase.
  - `id`: chữ in hoa bắt đầu bằng `ID_ IDD_ IDC_ IDS_ IDR_ IDM_ WM_ UWM_`.
  - `quoted`: nội dung trong `"…"` hoặc `'…'`, giữ nguyên dấu tiếng Việt.
  - `ident`: CamelCase, có `_`, hoặc bắt đầu bằng `m_`.
  - `word`: phần còn lại, đã lọc stopword tiếng Anh và tiếng Việt (danh sách cố định trong file).
- **Test:** khoảng 20 câu hỏi mẫu, gồm cả tiếng Việt có dấu.

### S5 — Seeding
- **Tạo:** `mfcgraph_core/explore_seed.py`, test.
- **Interface:** `seed(graph, terms, scope_dirs) -> (seeds: dict[node_id → (weight, reason)], pinned_files, unmatched_terms, suggestions)`.
- **Bảng trọng số** (cố định trong file, model chính có thể chỉnh ở S9):

| Term | Ánh xạ tới | Trọng số |
| --- | --- | --- |
| `anchor` | hàm bao quanh dòng đó (hoặc khoảng dòng), đánh dấu exact | 10 |
| `qualified` | đúng hàm/lớp đó, exact | 8 |
| `ident` | hàm/lớp/field trùng tên (≤5 định nghĩa; nhiều hơn thì chia đều) | 6 |
| `id` | handler của ID qua `handled_by`, cộng các hàm gửi message đó | 5 |
| `quoted` | hàm chứa chuỗi literal khớp; nếu khớp caption menu/dialog thì lấy handler | 5 |
| `word` | khớp đoạn tên (tách CamelCase), caption, chuỗi literal | 1 mỗi lần khớp, tối đa 3 |

- `path` là thư mục: trả về `scope_dirs`. `path` là file: đưa vào `pinned_files`.
- Gợi ý tên: dùng `difflib.get_close_matches` trên tập tên, chỉ áp dụng cho `ident`/`qualified` không khớp được.
- **Model chính review** bảng trọng số và các trường hợp biên trước khi merge.

### S6 — Xếp hạng + luồng chính (model chính)
- **Tạo:** `mfcgraph_core/explore_rank.py`.
- **Interface:** `rank(graph, seeds, scope_dirs) -> (scores: dict[node → float], spine: list[path])`.
- **Thiết kế gợi ý** (model chính tự quyết, ghi lý do vào docstring):
  - Đồ thị con trong bán kính K=3 bước từ các seed, theo các cạnh `calls` (hai chiều), `handled_by`, `triggers`, `sends`, `overrides`, `binds`, `uses_dialog`.
  - Personalized PageRank / random walk with restart, restart khoảng 0,3, khoảng 20 vòng lặp.
  - Trọng số cạnh: `exact`=1, `likely`=0,7, `ambiguous`=0,3/n, `heuristic`=0,5, `external`=0 (không đi qua).
  - Có `scope_dirs` thì nhân điểm của node ngoài scope với 0,2.
  - **Luồng chính (spine):** với top 4 seed, BFS đường ngắn nhất (tối đa 6 bước) giữa từng cặp, theo hướng gọi đúng. Node trên spine nhân điểm ×2.
- **Nghiệm thu:** trên `samples/LegacyApp`, query `"Export failed WriteTextFile"` cho spine `OnFileExport → ExportTo → ExportCsv/ExportXml → WriteTextFile`.

### S7a — Tiện ích cửa sổ code
- **Tạo:** `mfcgraph_core/explore_windows.py`, test.
- **Interface:**
  - `windows_for(func_span, focus_lines, max_lines) -> list[(start, end)]`: lấy ±6 dòng quanh mỗi dòng trọng tâm; luôn giữ dòng chữ ký và dấu `}` cuối; gộp các cửa sổ cách nhau ≤3 dòng.
  - `render(lines, windows) -> str`: đánh số dòng kiểu `57\t…`; giữa các cửa sổ chèn `… lines a-b elided — mfc_explore "File.cpp:a-b" returns them`.
  - `signature_only(...)`: chỉ in chữ ký hàm.

### S7b — Phân bổ ngân sách + ghép kết quả (model chính)
- **Tạo:** `mfcgraph_core/explore_render.py`, `mfcgraph_core/explore.py` (hàm `explore(graph, query, budget=None) -> str`).
- **Ngân sách mặc định** theo số file: dưới 300 file là 8.000 ký tự; dưới 3.000 là 12.000; còn lại 16.000. Cho phép ghi đè bằng tham số.
- **Phân bổ** (theo `research-codegraph.md` §3):
  - Trọng số file = tổng điểm các hàm được chọn trong file.
  - File dưới 15% trọng số của file cao nhất: chỉ liệt kê tên file và tên hàm.
  - Mỗi file được tối thiểu 600 ký tự; một file tối đa 70% ngân sách, trừ file được pin.
  - Hàm exact/pinned luôn in đầy đủ trước, trừ khi một mình nó vượt ngân sách (khi đó dùng cửa sổ).
  - Hàm có điểm thấp không nằm trên spine: chỉ in chữ ký.
- **Thứ tự các phần trong kết quả:** xem Phụ lục A. Tuyệt đối không vượt ngân sách.

### S8 — Nối vào CLI + MCP
- **Sửa:** `cli.py` (lệnh `explore <query> [--budget N] [--scope DIR]`), `mcp.py`.
- **Spec:**
  - MCP mặc định chỉ khai báo `mfc_explore`. Biến môi trường `MFCGRAPH_MCP_TOOLS=explore,trace,callers,…` để bật thêm tool khác.
  - Viết lại `INSTRUCTIONS` theo tinh thần CodeGraph, ngắn, dành cho Copilot: gọi `mfc_explore` trước khi mở file; coi source nhận được như đã đọc; cần thêm thì gọi lại với tên cụ thể hơn; hàm có cờ framework-entry/msg-handler là do MFC gọi.
  - Mô tả tool liệt kê các dạng query ở mục 1.

### S9 — Đánh giá + tinh chỉnh
- **Harness** (implementer): `tests/eval_explore.py` đọc `scenarios.json`, chạy `explore`, kiểm tra từng hàm trong `must_include` **có code trong phần source** (không tính trường hợp chỉ nhắc tên), đo số ký tự. In bảng: kịch bản, recall, số ký tự, các hàm bị thiếu.
- **Tinh chỉnh** (model chính): chỉnh trọng số ở S5/S6 và tham số phân bổ ở S7b cho đến khi recall ≥ 0,9 và mọi kết quả nằm trong ngân sách. Ghi các thay đổi tham số và lý do vào `docs/STATUS.md`. Không tinh chỉnh quá mức cho dữ liệu mẫu (overfit): mỗi lần đổi tham số phải giải thích được bằng một nguyên lý chung.

### S10 — Cảnh báo file đã đổi
- Khi chạy explore, so `mtime`/`size` của các file sắp in ra với giá trị trong index. File nào đã đổi: in banner `⚠ Changed since last index: …; re-run index` và không in code của file đó (chỉ in tên).

### S11 — Bổ sung `diagnose`
- Thêm: số chuỗi literal đã index, số tham chiếu field (đọc/ghi), tỉ lệ tham chiếu resolve được về field. Vẫn chỉ in con số.

### S12 — Tài liệu (doc-writer)
- README tiếng Việt: thêm `explore` (ví dụ chạy thật trên `samples/`), `refs`, tìm theo chuỗi.
- Tạo `docs/copilot-instructions.md` (bản tiếng Anh để copy vào `.github/copilot-instructions.md`), ví dụ `.mcp.json` cho Visual Studio và VS Code, và mục "fallback không có MCP": `explore … > ctx.md` rồi dùng `#file:ctx.md`.
- Cập nhật checklist audit cho SA: các module mới vẫn chỉ import thư viện chuẩn.

### S13 — Hiệu năng
- `tests/tools/make_big_tree.py`: nhân bản `samples/BigApp` thành khoảng 20.000 file, đổi tên lớp để tránh trùng hàng loạt.
- Đo thời gian index, RAM, thời gian `explore`. Nếu RAM > 1,5 GB hoặc explore > 2 giây: ghi đề xuất chuyển sang `sqlite3` (cũng là thư viện chuẩn) vào `docs/STATUS.md`, không tự làm trong v0.2.

### S14 — Đóng gói
- `tools/package.py` (dùng `zipfile`): tạo `dist/mfcgraph-py-0.2.zip`, loại `__pycache__`, `.mfcgraph`, `cpp-reference/`. Thêm `CHANGELOG.md`.

---

## Phụ lục A — Định dạng output của `mfc_explore` (minh họa)

```
mfc_explore: 5 functions in 3 files (budget 8000, used 3150). Scope: (all)

## Flow
Menu IDR_MAINFRAME: File > Export... / Accelerator Ctrl+E
  -> ID_FILE_EXPORT [ON_COMMAND] -> CMainFrame::OnFileExport  MainFrm.cpp:57
  -> CLegacyDoc::ExportTo  LegacyDoc.cpp:45
  -> CLegacyDoc::ExportCsv  LegacyDoc.cpp:67 | CLegacyDoc::ExportXml  LegacyDoc.cpp:75
  -> util::WriteTextFile  Util.cpp:35
Text "Export failed": MainFrm.cpp:68 (in CMainFrame::OnFileExport)

## Source
### MainFrm.cpp — CMainFrame::OnFileExport (msg-handler)
57	void CMainFrame::OnFileExport()
...
68			AfxMessageBox(_T("Export failed"));
...
72	}
### LegacyDoc.cpp — CLegacyDoc::ExportTo, ExportCsv; ExportXml (signature only)
45	BOOL CLegacyDoc::ExportTo(const CString& strPath, int nFormat, BOOL bOverwrite)
…
### Util.cpp — util::WriteTextFile
35	BOOL WriteTextFile(const CString& path, const CString& text)
…

## Blast radius
CLegacyDoc::ExportTo ← 1 caller; UI entries: Menu File > Export..., Accelerator Ctrl+E, Toolbar button 3

## Not shown (ask mfc_explore with these names)
util::FileExists  Util.cpp:19 · util::LogMessage  Util.cpp:8 · CExportDlg::OnOK  ExportDlg.cpp:62
```

Quy tắc: phần Source dùng định dạng `số_dòng<TAB>nội dung`. Các phần Flow, Blast radius, Not shown mỗi phần tối đa khoảng 10 dòng. Có tên không khớp thì thêm `## Did you mean`.

## Phụ lục B — Ngoài phạm vi v0.2
- Lượt phân tích bằng Clang, đọc `.vcxproj/.dsp`, index tăng dần, theo dõi file (watcher).
- Liên kết virtual dispatch từ lớp cha xuống lớp con (để v0.3).
- Chuyển index sang SQLite (chỉ làm nếu S13 cho thấy cần).
