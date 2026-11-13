# mfcgraph 0.1 (bản Python)

Công cụ dựng **đồ thị mã nguồn** cho codebase C++/MFC lâu năm, chạy **hoàn toàn offline**. Mục đích là giúp AI agent (GitHub Copilot) hỏi đúng chỗ thay vì đọc cả chục file, nhờ đó tốn ít token và credit hơn.

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
| Chỉ dùng thư viện chuẩn | Toàn bộ lệnh `import` nằm đầu mỗi file: `os`, `sys`, `re`, `json`, `time`, `hashlib`, `tempfile`, `unicodedata` và các module nội bộ `mfcgraph_core` |
| Không telemetry, không tự cập nhật | Toàn bộ mã nguồn khoảng 3.000 dòng Python (kể cả comment) trong `mfcgraph_core/`, đọc hết được |
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

## 3. Chạy test (khoảng 1 giây)

```bat
cd mfcgraph-py
python tests\test_mfcgraph.py
```

Kết quả mong đợi: `38 passed, 0 failed`.

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
| `search <chữ>` | Chỉ biết một từ: tìm lớp, hàm, ID, caption menu/dialog |
| `trace <caption menu \| ID_xxx \| IDD_xxx>` | "Bấm cái này thì code nào chạy?" |
| `node <Lớp::Hàm>` | Vị trí, chữ ký, cờ, mã nguồn của một hàm/lớp |
| `callers <hàm> [--depth 5]` | Ai gọi hàm này (kể cả qua message map, lên đến UI) |
| `callees <hàm> [--depth 2]` | Hàm này gọi gì |
| `impact <hàm>` | Sửa hàm này thì ảnh hưởng những hàm, UI, file nào |
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

**Cách A: "context pack" (không cần MCP, dùng được ngay).**

```bat
python mfcgraph.py context CMainFrame::OnFileExport > ctx.md
python mfcgraph.py trace "Export" >> ctx.md
```

Rồi đưa cho Copilot bằng `#file:ctx.md` thay vì mở nhiều file nguồn.

**Cách B: MCP (tùy chọn, chỉ khi SA đồng ý).**

Điều kiện:
- Admin bật policy **"MCP servers in Copilot"**.
- Visual Studio 2022 17.14 trở lên / VS 2026, hoặc VS Code 1.99 trở lên.
- Copilot Chat ở chế độ **Agent**.

Tạo `.mcp.json` ở thư mục solution (hoặc `.vscode\mcp.json` với VS Code):

```json
{
  "servers": {
    "mfcgraph": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\tools\\mfcgraph-py\\mfcgraph.py", "serve", "--root", "D:\\src\\MyProduct"]
    }
  }
}
```

Hướng dẫn cho Copilot (thêm vào `.github\copilot-instructions.md`):

```markdown
This is a legacy C++/MFC codebase. An MCP server "mfcgraph" indexes it.
- Before reading files, use mfc_trace (menu caption, ID_xxx, IDD_xxx) or mfc_search to locate code.
- Use mfc_context <Class::Method> to get the code plus callers/callees instead of opening whole files.
- Before changing a function, run mfc_impact to see affected functions and UI entry points.
- Functions flagged framework-entry or msg-handler are called by MFC; they are not dead code.
```

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
mfcgraph_core/extract_cpp.py  lớp, hàm, lời gọi, message map, DDX, RUNTIME_CLASS, IDD
mfcgraph_core/extract_rc.py   dialog, menu, accelerator, toolbar, string table
mfcgraph_core/resolve.py    resolve tên, độ tin cậy, override, framework entry
mfcgraph_core/index.py      quét thư mục, lưu/đọc index
mfcgraph_core/query.py      search / node / callers / callees / impact / trace / context / diagnose
mfcgraph_core/mcp.py        MCP server qua stdio (tùy chọn)
mfcgraph_core/cli.py        giao diện dòng lệnh
tests/test_mfcgraph.py      38 kiểm thử trên samples/LegacyApp
```

Định dạng index giống hệt bản C++: hai bản đã được đối chiếu và cho kết quả trùng khớp trên gần 4.000 file C++ thật.
