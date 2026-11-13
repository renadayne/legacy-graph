# mfcgraph 0.2 (bản Python)

Công cụ dựng **đồ thị mã nguồn** cho codebase C++/MFC lâu năm, chạy **hoàn toàn offline**. Mục đích là giúp AI agent (GitHub Copilot) hỏi đúng chỗ thay vì đọc cả chục file, nhờ đó tốn ít token và credit hơn.

v0.2 thêm một lệnh/tool chính: `explore` (`mfc_explore`). Từ một câu hỏi, tên hàm, ID hoặc thông báo lỗi, `explore` trả về mã nguồn liên quan, luồng gọi và phạm vi ảnh hưởng trong một lần gọi.

- **Chỉ cần Python 3.7 trở lên**, đã có sẵn trên máy. **Chỉ dùng thư viện chuẩn của Python**: không `pip install`, không thư viện ngoài, không kết nối internet.
- **Không cần build**, không có file `.exe` nào để ký số. Chạy thẳng `python mfcgraph.py ...`.

Công cụ hiểu được những chỗ mà công cụ thông thường bỏ sót trong MFC:

- Chuỗi **menu / phím tắt / toolbar → command ID → message map → handler → các hàm nó gọi**.
- **Dialog**: control trong file .rc, biến DDX, handler của từng control.
- `ON_MESSAGE` + `PostMessage/SendMessage`, `ON_COMMAND_RANGE`, `RUNTIME_CLASS`, `IMPLEMENT_DYNCREATE`.
- Các hàm override do framework gọi (`OnInitDialog`, `OnDraw`, `InitInstance`…): đánh dấu là "framework entry", không coi là dead code.
- File `.rc` dạng UTF-16 và mã nguồn ở code page cũ (CP1258 tiếng Việt, CP932…).

---

## 1. Bảo mật: những gì SA cần kiểm tra

| Cam kết | Cách kiểm chứng |
| --- | --- |
| Không có code mạng | `findstr /s /i "socket urllib http requests ftplib smtplib subprocess ctypes pickle" mfcgraph_core\*.py` chỉ ra đúng một dòng comment trong `mcp.py` |
| Chỉ dùng thư viện chuẩn | Toàn bộ lệnh `import` nằm đầu mỗi file: `os`, `sys`, `re`, `json`, `time`, `hashlib`, `unicodedata`, `difflib`, `collections` và các module nội bộ `mfcgraph_core`. Các module `explore*.py` cũng chỉ import thư viện chuẩn |
| Không telemetry, không tự cập nhật | Toàn bộ mã nguồn khoảng 4.800 dòng Python (kể cả comment) trong `mfcgraph_core/`, đọc hết được |
| Cái chạy chính là cái đọc | Không có bước build. File `.py` SA review là file chạy |
| MCP không mở cổng | MCP (tùy chọn) giao tiếp qua stdin/stdout; code MCP chỉ được nạp khi gọi lệnh `serve` |
| Không sửa cấu hình máy | Không ghi vào config của IDE/Copilot |
| Chỉ ghi một chỗ | Ghi duy nhất `<root>\.mfcgraph\index.mfg` (file văn bản, đọc và diff được) |

Có thể kiểm tra thêm bằng Process Monitor (lọc Process Name = python.exe, Operation chứa "TCP"/"UDP").

**File index (`.mfcgraph\index.mfg`) chứa tên lớp, tên hàm và quan hệ gọi của cả codebase**, nên phải bảo vệ như mã nguồn:
- Thêm `.mfcgraph/` vào `.gitignore` / svn:ignore.
- Không để trong thư mục đồng bộ ra ngoài.

---

## 2. Kiểm tra Python

Mở cmd:

```bat
python --version
```

Hoặc `py --version`. Cần 3.7 trở lên. Nếu máy dùng lệnh `py`, thay `python` bằng `py` trong mọi lệnh bên dưới.

## 3. Chạy test

```bat
cd mfcgraph-py
python tests\run_all.py
```

Kết quả mong đợi: dòng cuối là `ALL: OK`. Lệnh này chạy mọi bộ kiểm thử, kể cả đánh giá của `explore`. Dòng đánh giá đó có dạng:

```
mean recall 1.000 (target 0.90); within budget 14/14
```

## 4. Chạy thử với dự án mẫu

`samples\LegacyApp` là một dự án MFC **giả** (không có code công ty), cố ý có đủ các kiểu khó: file .rc dạng UTF-16, file .cpp mã CP1258, `#if 0` chứa ngoặc lệch, message map, DDX…

```bat
python mfcgraph.py index samples\LegacyApp
python mfcgraph.py trace Export --root samples\LegacyApp
```

Kết quả:

```
== ID_FILE_EXPORT  (value=32771; text="Export the document to CSV or XML\nExport")
  UI: Toolbar IDR_MAINFRAME button 3  LegacyApp.rc:26
  UI: Menu IDR_MAINFRAME: File > Export...  LegacyApp.rc:37
  UI: Accelerator Ctrl+E  LegacyApp.rc:65
  handler [ON_COMMAND]: CMainFrame::OnFileExport  MainFrm.cpp:57
     -> CLegacyDoc::ExportTo  LegacyDoc.cpp:45
        -> util::FileExists  Util.cpp:19
        -> CLegacyDoc::ExportCsv  LegacyDoc.cpp:67
        -> CLegacyDoc::ExportXml  LegacyDoc.cpp:75
        -> util::LogMessage  Util.cpp:8
     -> util::LogMessage  Util.cpp:8  (see above)
     -> external: AfxMessageBox, CDialog::DoModal, CFrameWnd::GetActiveDocument
  handler [ON_UPDATE_COMMAND_UI]: CMainFrame::OnUpdateFileExport  MainFrm.cpp:74
```

### explore

`explore` là lệnh nên dùng đầu tiên. Ví dụ:

```bat
python mfcgraph.py index samples\LegacyApp
python mfcgraph.py explore "Export failed WriteTextFile" --root samples\LegacyApp
```

Kết quả (phần mã nguồn được rút gọn bằng dòng `...`):

```
Indexed 15 files in 0.01 s -> ...\samples\LegacyApp\.mfcgraph\index.mfg
  classes 6, functions 45, message-map entries 13, dialogs 2, menu items 10
Run 'mfcgraph diagnose' for quality numbers.
```

```
mfc_explore: 10 functions in 3 files (budget 8000, used 4182). Scope: (all)

## Flow
Toolbar IDR_MAINFRAME button 3 / Menu IDR_MAINFRAME: File > Export... / Accelerator Ctrl+E
  -> CMainFrame::OnFileExport  MainFrm.cpp:57
  -> CLegacyDoc::ExportTo  LegacyDoc.cpp:45
  -> CLegacyDoc::ExportCsv  LegacyDoc.cpp:67
  -> util::WriteTextFile  Util.cpp:35

## Source
...

## Blast radius
CMainFrame::OnFileExport ← 0 callers, called by MFC via ID_FILE_EXPORT [ON_COMMAND]; UI entries: Toolbar IDR_MAINFRAME button 3, Menu IDR_MAINFRAME: File > Export..., Accelerator Ctrl+E
util::WriteTextFile ← 2 callers (CLegacyDoc::ExportCsv, CLegacyDoc::ExportXml)
CLegacyDoc::ExportTo ← 1 caller (CMainFrame::OnFileExport); UI entries: Toolbar IDR_MAINFRAME button 3, Menu IDR_MAINFRAME: File > Export..., Accelerator Ctrl+E

## Not shown (ask mfc_explore with these names)
CLegacyDoc::HasData  LegacyDoc.h:19 · CLegacyApp::InitInstance  LegacyApp.cpp:31
```

Ý nghĩa từng phần:

- **Flow**: chuỗi đi từ thao tác trên giao diện (menu, phím tắt, toolbar) tới command ID, handler, rồi tới các hàm handler gọi.
- **Source**: mã nguồn của các hàm liên quan nhất, có số dòng, nhóm theo file. Hàm có nhãn `msg-handler`, `update-ui-handler` hoặc `framework-entry` được MFC gọi. Dòng bị bỏ được ghi dạng `… line 73 elided — mfc_explore "MainFrm.cpp:73" returns it`. Muốn xem đoạn đó, hỏi lại với `MainFrm.cpp:73` hoặc khoảng `MainFrm.cpp:70-76`.
- **Blast radius**: hàm được ai gọi (`← N callers`) và tới những giao diện nào (`UI entries`). Dùng để biết sửa hàm thì ảnh hưởng tới đâu.
- **Not shown**: các hàm liên quan nhưng không in mã nguồn, vì hết ngân sách ký tự. Tên trong mục này dùng để hỏi lại `explore`.
- **Did you mean**: xuất hiện khi tên không khớp với index. Ví dụ, với tên sai `CLegacyDoc::ExportCvs`:

```
mfc_explore: 0 functions in 0 files (budget 8000, used 333). Scope: (all)

No code matched 'CLegacyDoc::ExportCvs'. Name a function, class, ID, file or quote the exact message text.

## Did you mean
CLegacyDoc::ExportCvs → CLegacyDoc::ExportCsv, CLegacyDoc::ExportTo, CLegacyDoc::ExportXml, CLegacyDoc::m_values, CLegacyDoc::HasData
```

Tùy chọn:

- `--budget N`: giới hạn số ký tự của kết quả. Mặc định tùy kích thước dự án (8.000, 12.000 hoặc 16.000). Tăng `N` để có thêm mã nguồn; giảm `N` để tốn ít token hơn.
- `--scope DIR`: ưu tiên các file trong thư mục `DIR`, ví dụ `Billing`. Hàm ngoài thư mục vẫn có thể xuất hiện nhưng bị giảm ưu tiên.

Cảnh báo file đã đổi: nếu file có mã nguồn trong kết quả được sửa sau lần `index`, kết quả có dòng `⚠ Changed since last index: …; re-run index (code of these files not shown)`. Mã nguồn của các file đó không được in. Chạy lại `index` để cập nhật.

Các dạng câu hỏi `explore` nhận:

- Mô tả lỗi bằng tiếng Anh hoặc tiếng Việt.
- Tên hàm hoặc tên lớp.
- `Class::Method`.
- `File.cpp:120` hoặc `File.cpp:100-140`.
- Tên thư mục module, ví dụ `Billing/`.
- Caption của menu hoặc nút bấm.
- ID: `ID_FILE_EXPORT`, `IDD_xxx`, `IDC_xxx`, `IDS_xxx`, `WM_APP_xxx`.
- Nguyên văn thông báo lỗi (nên đặt trong dấu ngoặc kép).

### refs và search

`refs` cho biết hàm nào ghi và hàm nào đọc một biến thành viên. Nhãn `[DDX]` nghĩa là ghi qua DDX của dialog.

```bat
python mfcgraph.py refs CExportDlg::m_strPath --root samples\LegacyApp
```

```
CExportDlg::m_strPath: 3 write(s), 5 read(s)
writes:
  CExportDlg::CExportDlg  ExportDlg.cpp:13
  CExportDlg::DoDataExchange  ExportDlg.cpp:24 [DDX]
  CExportDlg::OnBnClickedBrowse  ExportDlg.cpp:52
reads:
  CExportDlg::DoDataExchange  ExportDlg.cpp:25
  CExportDlg::OnBnClickedBrowse  ExportDlg.cpp:49
  CExportDlg::OnOK  ExportDlg.cpp:65
  CExportDlg::OnOK  ExportDlg.cpp:70
  CMainFrame::OnFileExport  MainFrm.cpp:67
```

`search` cũng tìm chuỗi ký tự trong thân hàm (kết quả có nhãn `[text]`). Tìm không phân biệt chữ hoa, chữ thường. Tiếng Việt được so sánh sau khi chuẩn hóa Unicode NFC, nên chữ có dấu tổ hợp và chữ dựng sẵn vẫn khớp nhau.

```bat
python mfcgraph.py search "export failed" --root samples\LegacyApp
```

```
2 match(es) for 'export failed':
  [text] "Export failed"  CMainFrame::OnFileExport  MainFrm.cpp:69
  [text] "Export failed"  CMainFrame::OnFileExport  MainFrm.cpp:70
```

Thử thêm (thêm `--root samples\LegacyApp`, hoặc `cd samples\LegacyApp` rồi gọi `python ..\..\mfcgraph.py ...`):

```bat
python mfcgraph.py trace IDD_EXPORT --root samples\LegacyApp
python mfcgraph.py callers CLegacyDoc::Recalculate --root samples\LegacyApp
python mfcgraph.py impact CLegacyDoc::ExportCsv --root samples\LegacyApp
python mfcgraph.py context CExportDlg::OnOK --root samples\LegacyApp
python mfcgraph.py diagnose --root samples\LegacyApp
```

## 5. Chạy trên dự án thật

```bat
python mfcgraph.py index D:\src\MyProduct --codepage 1258 -v
python mfcgraph.py diagnose --root D:\src\MyProduct
```

- `--codepage`: code page cho các file **không phải** UTF-8/UTF-16. Mặc định là 1258 (tiếng Việt). Dùng 932 cho tiếng Nhật, 1252 cho Tây Âu.
- `--exclude "ThirdParty;Generated"`: bỏ qua thư mục. Mặc định đã bỏ qua `Debug`, `Release`, `x64`, `.git`, `.svn`, `.vs`, `ipch`, `obj`, `bin`.
- `-v`: in tiến độ sau mỗi 500 file.
- Tốc độ đo được: khoảng 1 triệu dòng (21.000 file) mất khoảng 27 giây, khoảng 350 MB RAM. Index lại khi code thay đổi nhiều.

Mẹo: tạo file `mfcgraph.bat` để gõ ngắn hơn:

```bat
@python C:\tools\mfcgraph-py\mfcgraph.py %* --root D:\src\MyProduct
```

Sau đó chỉ cần gõ `mfcgraph trace Export`.

### Các lệnh

| Lệnh | Dùng khi |
| --- | --- |
| `explore <câu hỏi \| tên \| File.cpp:120 \| ID \| "thông báo lỗi"> [--budget N] [--scope DIR]` | **Bắt đầu từ đây.** Một lần gọi: mã nguồn liên quan + luồng + ảnh hưởng |
| `search <chữ>` | Chỉ biết một từ: tìm lớp, hàm, ID, caption menu/dialog, chuỗi ký tự trong code |
| `trace <caption menu \| ID_xxx \| IDD_xxx>` | "Bấm cái này thì code nào chạy?" |
| `node <Lớp::Hàm>` | Vị trí, chữ ký, cờ, mã nguồn của một hàm/lớp |
| `callers <hàm> [--depth 5]` | Ai gọi hàm này (kể cả qua message map, lên đến UI) |
| `callees <hàm> [--depth 2]` | Hàm này gọi gì |
| `impact <hàm>` | Sửa hàm này thì ảnh hưởng những hàm, UI, file nào |
| `refs <Lớp::m_field \| m_field>` | Biến thành viên được ghi và đọc ở đâu |
| `msgmap <Lớp>` | Toàn bộ message map của một lớp |
| `context <hàm> [--lines 80]` | Gói ngữ cảnh Markdown để đưa cho AI |
| `diagnose [--show-names]` | Số liệu chất lượng (chỉ con số) |
| `status` | Thông tin index |

Mỗi lời gọi được gắn **độ tin cậy**:
- `exact`: gọi có tên lớp, qua `this`, hoặc biến đã biết kiểu.
- `likely`: cả codebase chỉ có một hàm trùng tên.
- `ambiguous`: nhiều ứng viên, liệt kê tất cả.
- `heuristic`: suy theo mẫu, ví dụ `PostMessage` → handler.
- `external`: thuộc MFC, Win32 hoặc CRT.

## 6. Đưa kết quả cho Copilot

### 6.1. MCP (tùy chọn, chỉ khi SA đồng ý)

Điều kiện:
- Admin bật policy **"MCP servers in Copilot"**.
- Visual Studio 2022 17.14 trở lên / VS 2026, hoặc VS Code 1.99 trở lên.
- Copilot Chat ở chế độ **Agent**.

Mặc định MCP chỉ mở tool `mfc_explore`. Muốn bật thêm tool, đặt biến môi trường `MFCGRAPH_MCP_TOOLS` trong khối `env` của server:
- `explore,refs,trace,callers`: chỉ các tool được liệt kê (có thể bỏ tiền tố `mfc_`).
- `all`: bật mọi tool.

Các tool có thể bật: `mfc_explore`, `mfc_refs`, `mfc_search`, `mfc_node`, `mfc_callers`, `mfc_callees`, `mfc_impact`, `mfc_trace`, `mfc_context`, `mfc_msgmap`, `mfc_status`.

Visual Studio 2022: tạo file `.mcp.json` trong thư mục solution:

```json
{"servers": {"mfcgraph": {"type": "stdio", "command": "python", "args": ["C:\\tools\\mfcgraph-py\\mfcgraph.py", "serve", "--root", "C:\\src\\MyApp"], "env": {"MFCGRAPH_MCP_TOOLS": "explore"}}}}
```

VS Code: tạo file `.vscode\mcp.json`:

```json
{"servers": {"mfcgraph": {"type": "stdio", "command": "python", "args": ["C:\\tools\\mfcgraph-py\\mfcgraph.py", "serve", "--root", "C:\\src\\MyApp"], "env": {"MFCGRAPH_MCP_TOOLS": "explore"}}}}
```

Hướng dẫn cho Copilot: copy file `docs/copilot-instructions.md` của repo này vào `.github\copilot-instructions.md` của repo công ty. File đó bằng tiếng Anh, nhắc Copilot gọi `mfc_explore` trước khi mở file.

### 6.2. Không có MCP (fallback)

Nếu không bật được MCP, tạo file ngữ cảnh bằng `explore`:

```bat
python mfcgraph.py explore "câu hỏi hoặc tên hàm" --root C:\src\MyApp > ctx.md
```

Rồi trong Copilot Chat gõ `#file:ctx.md` để đính kèm file. Có thể dùng `python mfcgraph.py context <hàm> > ctx.md` để lấy gói ngữ cảnh của một hàm.

`ctx.md` chứa mã nguồn công ty: giữ trên máy, không commit vào repo.

## 7. Gửi phản hồi để cải thiện (không lộ mã nguồn)

```bat
python mfcgraph.py diagnose --root D:\src\MyProduct > diag.txt
```

`diag.txt` chỉ chứa con số. **Bạn đọc kiểm tra trước khi gửi ra ngoài.**

Cách đánh giá nhanh:

| Chỉ số | Tốt | Cần xem lại |
| --- | --- | --- |
| `NOT FOUND` (handler message map) | dưới 5% | trên 10% |
| `unrecognised ON_ macros` | 0 hoặc rất ít | nhiều: dự án có macro riêng |
| `files with unbalanced braces` | dưới 1% số file | nhiều |
| `ambiguous` (call sites) | dưới 15% | cao |
| `external` | 60–80% là bình thường | (lời gọi MFC/Win32) |

Khi thấy công cụ hiểu sai một đoạn code, hãy viết lại cấu trúc đó **với tên giả** thành một file nhỏ rồi gửi file đó.

## 8. Giới hạn của bản demo

- Là bộ phân tích **dựa trên mẫu** (heuristic), không phải trình biên dịch: không khai triển macro tự định nghĩa, không hiểu template phức tạp. Chỗ không chắc được gắn nhãn `ambiguous`/`likely`.
- Với `#if/#ifdef`, công cụ luôn lấy **nhánh đầu tiên**, riêng `#if 0` thì bỏ qua.
- Chưa đọc file project (`.vcxproj/.dsp`) mà quét toàn bộ cây thư mục.
- Chưa có index tăng dần: muốn cập nhật thì chạy lại `index`.
- Chưa liên kết virtual dispatch từ lớp cha xuống lớp con.

## 9. Cấu trúc mã nguồn

```
mfcgraph.py                 lệnh chạy
mfcgraph_core/encoding.py   nhận diện UTF-8/UTF-16/ANSI code page
mfcgraph_core/lexer.py      lexer C++/RC chịu lỗi, lọc #if
mfcgraph_core/extract_cpp.py  lớp, hàm, lời gọi, message map, DDX, RUNTIME_CLASS, IDD, chuỗi, biến
mfcgraph_core/extract_rc.py   dialog, menu, accelerator, toolbar, string table
mfcgraph_core/resolve.py    resolve tên, độ tin cậy, override, framework entry
mfcgraph_core/index.py      quét thư mục, lưu/đọc index
mfcgraph_core/query.py      search / node / callers / callees / impact / trace / refs / context / diagnose
mfcgraph_core/explore_query.py  tách câu hỏi của explore thành các thành phần (tên, đường dẫn, ID, cụm trong ngoặc kép, từ khóa)
mfcgraph_core/explore_seed.py   tìm các hàm xuất phát từ thành phần câu hỏi, có trọng số
mfcgraph_core/explore_rank.py   xếp hạng hàm (PageRank cá nhân trên đồ thị con) và tìm đường gọi chính (spine)
mfcgraph_core/explore_windows.py chọn các đoạn dòng quanh điểm quan trọng, giữ chữ ký, đánh dấu dòng bị bỏ
mfcgraph_core/explore_render.py phân bổ ngân sách ký tự, dựng Flow/Source/Blast radius/Not shown/Did you mean, kiểm tra file đã đổi
mfcgraph_core/explore.py    ghép các bước: phân tích → tìm hàm xuất phát → xếp hạng → dựng kết quả
mfcgraph_core/mcp.py        MCP server qua stdio (tùy chọn)
mfcgraph_core/cli.py        giao diện dòng lệnh
tests/test_mfcgraph.py      kiểm thử trên samples/LegacyApp
tests/run_all.py            chạy mọi bộ kiểm thử
tests/golden_test.py        so sánh output CLI với tests/golden/*.txt (--update để ghi lại)
tests/eval_explore.py       đo recall của explore trên tests/scenarios.json; lỗi nếu recall trung bình < 0.9 hoặc vượt budget
tests/scenarios.json        14 kịch bản: câu hỏi + hàm bắt buộc phải có trong kết quả
samples/BigApp/             dự án mẫu thứ hai (47 file, MDI, nhiều module), dùng cho kịch bản explore
```

Định dạng index giống hệt bản C++: hai bản đã được đối chiếu và cho kết quả trùng khớp trên gần 4.000 file C++ thật.
