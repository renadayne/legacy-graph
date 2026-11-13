> **FROZEN (v0.1 reference).** Ban C++ duoc giu de doi chieu; phat trien tiep o ban Python (thu muc goc). Mau test nam o `../samples/`.

# mfcgraph 0.1 (demo)

Công cụ dựng **đồ thị mã nguồn** cho codebase C++/MFC lâu năm, chạy **hoàn toàn offline**. Mục đích là giúp AI agent (GitHub Copilot) hỏi đúng chỗ thay vì đọc cả chục file, nhờ đó tốn ít token và credit hơn.

Công cụ hiểu được những chỗ mà công cụ thông thường bỏ sót trong MFC:

- Chuỗi **menu / phím tắt / toolbar → command ID → message map → handler → các hàm nó gọi**.
- **Dialog**: control trong file .rc, biến DDX, handler của từng control.
- `ON_MESSAGE` + `PostMessage/SendMessage` (message tự định nghĩa), `ON_COMMAND_RANGE`, `RUNTIME_CLASS`, `IMPLEMENT_DYNCREATE`.
- Các hàm override do framework gọi (`OnInitDialog`, `OnDraw`, `InitInstance`…): công cụ đánh dấu là "framework entry", không coi là dead code.
- File `.rc` dạng UTF-16 và mã nguồn ở code page cũ (CP1258 tiếng Việt, CP932…).

---

## 1. Bảo mật: những gì SA cần kiểm tra

| Cam kết | Cách kiểm chứng |
| --- | --- |
| Không có code mạng | `findstr /s /i "socket winhttp wininet ws2_32 urlmon connect(" src\*` không ra kết quả (chỉ một dòng comment trong `mcp.h`) |
| Không link thư viện mạng | `dumpbin /imports build\mfcgraph.exe`: chỉ thấy DLL hệ thống cơ bản như `KERNEL32.dll`; không có `WS2_32`, `WINHTTP`, `WININET`, `URLMON` |
| Không có telemetry, không tự cập nhật | Toàn bộ mã nguồn khoảng 4.400 dòng trong `src/`, đọc hết được |
| Không phụ thuộc thư viện ngoài | Chỉ dùng thư viện chuẩn C++17 và Windows API. Không có NuGet/vcpkg/npm/pip |
| MCP không mở cổng | Giao tiếp qua stdin/stdout. IDE khởi chạy tiến trình, không có TCP/HTTP |
| Không sửa cấu hình máy | Công cụ không ghi vào config của IDE/Copilot. Người dùng tự thêm (mục 6) |
| Chỉ ghi một chỗ | Ghi duy nhất `<root>\.mfcgraph\index.mfg` (file văn bản, đọc và diff được) |

Có thể kiểm tra thêm bằng cách chạy dưới rule chặn Windows Firewall, hoặc theo dõi bằng Process Monitor (lọc Process Name = mfcgraph.exe, Operation chứa "TCP"/"UDP").

**File index (`.mfcgraph\index.mfg`) chứa tên lớp, tên hàm và quan hệ gọi của cả codebase**, nên phải bảo vệ như mã nguồn:
- Thêm `.mfcgraph/` vào `.gitignore` / svn:ignore.
- Không để trong thư mục đồng bộ ra ngoài (OneDrive…).

---

## 2. Yêu cầu

- Visual Studio **2017 15.7 trở lên** (2019/2022/2026 đều được) để build công cụ. Công cụ cần C++17. Code được phân tích thì thuộc đời nào cũng được (VC6, VS2008, C++14…).
- Không cần cài thêm gì.

## 3. Build

Mở **"x64 Native Tools Command Prompt for VS 20xx"**, rồi chạy:

```bat
cd mfcgraph
build.bat
```

Script build `build\mfcgraph.exe`, build bộ test, rồi chạy test trên dự án mẫu. Kết quả mong đợi: `41 passed, 0 failed`.

Nếu lần build đầu trên MSVC gặp lỗi biên dịch (code được viết và test bằng GCC/Clang), đưa thông báo lỗi cho Copilot sửa. Thường chỉ là thiếu một `#include`.

Hoặc build bằng CMake:

```bat
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
build\Release\mfcgraph_tests.exe samples\LegacyApp
```

Nên copy `mfcgraph.exe` vào một thư mục cố định, ví dụ `C:\tools\mfcgraph\`.

## 4. Chạy thử với dự án mẫu

`samples\LegacyApp` là một dự án MFC **giả** (không có code công ty), cố ý có đủ các kiểu khó: file .rc dạng UTF-16, file .cpp mã CP1258, `#if 0` chứa ngoặc lệch, message map, DDX…

```bat
build\mfcgraph.exe index samples\LegacyApp
cd samples\LegacyApp
..\..\build\mfcgraph.exe trace Export
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

Thử thêm:

```bat
mfcgraph trace IDD_EXPORT                 :: dialog: control, biến DDX, handler
mfcgraph callers CLegacyDoc::Recalculate   :: ai gọi, đến tận menu/phím tắt
mfcgraph impact CLegacyDoc::ExportCsv      :: sửa hàm này thì ảnh hưởng đâu
mfcgraph context CExportDlg::OnOK          :: gói ngữ cảnh Markdown cho AI
mfcgraph diagnose                          :: số liệu chất lượng
```

## 5. Chạy trên dự án thật

```bat
mfcgraph index D:\src\MyProduct --codepage 1258
```

- `--codepage`: code page cho các file **không phải** UTF-8/UTF-16. Mặc định là 1258 (tiếng Việt). Dùng 932 cho tiếng Nhật, 1252 cho Tây Âu.
- `--exclude "ThirdParty;Generated"`: bỏ qua các thư mục (không phân biệt hoa thường). Mặc định đã bỏ qua `Debug`, `Release`, `x64`, `.git`, `.svn`, `.vs`, `ipch`, `obj`, `bin`.
- `-v`: in tiến độ.
- Index lại khi code thay đổi nhiều. Bản demo chạy lại toàn bộ; trên máy test, khoảng 1 triệu dòng (21.000 file) mất khoảng 9 giây.

Sau khi index, chạy các lệnh truy vấn trong thư mục dự án (công cụ tự tìm `.mfcgraph` ở thư mục cha), hoặc thêm `--root D:\src\MyProduct`.

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

## 6. Kết nối GitHub Copilot qua MCP

**Điều kiện:**
- Admin của tổ chức phải bật policy **"MCP servers in Copilot"** (mặc định tắt với gói Business/Enterprise).
- Visual Studio 2022 **17.14** trở lên / VS 2026, hoặc VS Code 1.99 trở lên.
- Copilot Chat đang ở chế độ **Agent**.

**Visual Studio:** tạo file `.mcp.json` ở thư mục solution (hoặc `%USERPROFILE%\.mcp.json` để dùng cho mọi solution):

```json
{
  "servers": {
    "mfcgraph": {
      "type": "stdio",
      "command": "C:\\tools\\mfcgraph\\mfcgraph.exe",
      "args": ["serve", "--root", "D:\\src\\MyProduct"]
    }
  }
}
```

**VS Code:** cùng nội dung, đặt ở `.vscode\mcp.json`.

Kiểm tra: trong Copilot Chat (Agent), bấm biểu tượng công cụ, phải thấy các tool `mfc_search`, `mfc_trace`, `mfc_context`, `mfc_callers`, `mfc_callees`, `mfc_impact`, `mfc_node`, `mfc_msgmap`, `mfc_status`.

**Hướng dẫn cho Copilot dùng công cụ** (nên thêm vào `.github\copilot-instructions.md` của repo):

```markdown
This is a legacy C++/MFC codebase. An MCP server "mfcgraph" indexes it.
- Before reading files, use mfc_trace (menu caption, ID_xxx, IDD_xxx) or mfc_search to locate code.
- Use mfc_context <Class::Method> to get the code plus callers/callees instead of opening whole files.
- Before changing a function, run mfc_impact to see affected functions and UI entry points.
- Functions flagged framework-entry or msg-handler are called by MFC; they are not dead code.
```

## 7. Nếu MCP bị chặn: dùng "context pack"

```bat
mfcgraph context CMainFrame::OnFileExport > ctx.md
mfcgraph trace "Export" >> ctx.md
```

Rồi đưa `ctx.md` cho Copilot (`#file:ctx.md`) thay vì mở nhiều file nguồn.

## 8. Gửi phản hồi để cải thiện (không lộ mã nguồn)

```bat
mfcgraph diagnose > diag.txt
```

`diag.txt` chỉ chứa con số: số file, encoding, tỉ lệ resolve lời gọi, tỉ lệ handler tìm thấy, số macro `ON_` không nhận ra. Mặc định không có tên nào. **Bạn đọc kiểm tra trước khi gửi ra ngoài.**

Khi thấy công cụ hiểu sai một đoạn code, hãy viết lại cấu trúc đó **với tên giả** thành một file nhỏ (bản "repro") rồi gửi file đó, không gửi code thật.

## 9. Giới hạn của bản demo

- Là bộ phân tích **dựa trên mẫu** (heuristic), không phải trình biên dịch: không khai triển macro tự định nghĩa, không hiểu template phức tạp, không suy kiểu của biểu thức phức tạp. Những chỗ không chắc được gắn nhãn `ambiguous`/`likely` thay vì đoán bừa.
- Với `#if/#ifdef`, công cụ luôn lấy **nhánh đầu tiên**, riêng `#if 0` thì bỏ qua. Code chỉ có trong nhánh `#else` sẽ không được index.
- Chưa đọc file project (`.vcxproj/.vcproj/.dsp`) mà quét toàn bộ cây thư mục.
- Chưa có index tăng dần hay theo dõi thay đổi file: muốn cập nhật thì chạy lại `index`.
- Chưa liên kết virtual dispatch từ lớp cha xuống các lớp con override (mới chỉ có quan hệ `overrides`).
- Kết quả trên code thật chắc chắn sẽ lộ thêm các pattern chưa xử lý. Đó là mục đích của vòng `diagnose` → repro → sửa.

## 10. Cấu trúc mã nguồn

```
src/util.*         chuỗi, file, hash, escape
src/encoding.*     nhận diện UTF-8/UTF-16/ANSI code page, chuyển về UTF-8
src/lexer.*        lexer C++/RC chịu lỗi, lọc #if
src/extract_cpp.cpp lớp, hàm, lời gọi, message map, DDX, RUNTIME_CLASS, IDD
src/extract_rc.cpp dialog, menu, accelerator, toolbar, string table
src/resolve.*      resolve tên, độ tin cậy, override, framework entry
src/index.*        quét thư mục, lưu/đọc index (file văn bản)
src/query.*        search / node / callers / callees / impact / trace / context / diagnose
src/json.*, mcp.*  MCP server qua stdio (JSON-RPC 2.0)
src/main.cpp       giao diện dòng lệnh
tests/test_main.cpp  41 kiểm thử trên samples/LegacyApp
```
