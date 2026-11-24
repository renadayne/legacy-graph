# Kế hoạch mfcgraph v0.4: chạy dễ, không quên bước (.vcxproj + cấu hình nhớ sẵn + GUI tùy chọn)

> Cùng quy tắc với `docs/PLAN.md` (mục 0 và 2): mỗi lần một step, mỗi step một commit `S<id>: …`, test pass mới commit,
> ghi ≤6 dòng vào `docs/STATUS.md`, push ngay lên `develop`.

## 1. Bối cảnh (người dùng, 2026-11-24)
Quy trình hiện tại có 3 bước tay, thiếu một bước là hỏng: (1) chép `PreprocessorDefinitions` từ `.vcxproj` ra `--define`,
(2) `index` với đủ cờ `--codepage/--define/--undef-unknown/--exclude`, (3) sửa `.mcp.json` cho `serve --root <đường dẫn>`.
App lớn có rất nhiều `.vcxproj` và nhiều `.sln` con; thường chỉ cần một vài project của module đang điều tra.

## 2. Mục tiêu v0.4
- Tool tự đọc `.vcxproj` / `.sln`: define theo cấu hình (Release|Win32…), danh sách file của project.
- Tool nhớ cấu hình index trong `<root>/.mfcgraph/settings.json`; lần sau chỉ cần `index <root>`.
- Lệnh tạo/ghi mục `mfcgraph` vào `.mcp.json` (chỉ khi người dùng yêu cầu rõ: nút riêng / `--write`; có sao lưu).
- GUI **tùy chọn** (`python mfcgraph.py gui`): hướng dẫn, chọn `.sln/.vcxproj`, chạy index, nút ghi `.mcp.json`.
  Chỉ dùng `tkinter` (thư viện chuẩn, không pip). GUI nằm trong package riêng `mfcgraph_gui/`, chỉ nạp khi gọi `gui`;
  `mfcgraph_core` không import GUI ở đâu khác. Không có tkinter → `gui` báo lỗi một dòng, CLI/MCP chạy bình thường.
- Cam kết với SA thay đổi đúng một điểm: tool **có thể** ghi `.mcp.json` khi người dùng bấm nút / dùng `--write`
  (xem trước, sao lưu `.bak`, chỉ sửa mục của mfcgraph). README mục 1 cập nhật cho khớp.

## 3. Các step

| Step | Việc | Phụ thuộc | Cỡ |
| --- | --- | --- | --- |
| S22 | `vcxproj.py`: đọc `.vcxproj`/`.props`/`.sln`; `index --vcxproj … --config …` | — | M |
| S23 | `settings.json`: lưu/tái dùng cấu hình index | S22 | S |
| S24 | `mcp_config.py` + lệnh `mcp-config [--write FILE]` (gộp, sao lưu) | — | S |
| S25 | GUI tkinter `mfcgraph_gui/` + lệnh `gui` | S22–S24 | M |
| S26 | README (VI), CHANGELOG 0.4.0, VERSION, package.py thêm `mfcgraph_gui` | S25 | S |

### S22 — Đọc .vcxproj
- `vcxproj.read_project(path, config=None) -> Project(name, path, configs, config, defines{}, undefs[], files[], notes[])`.
  - Cấu hình: `ProjectConfiguration Include="Release|Win32"`; mặc định ưu tiên `Release|Win32`, rồi Release đầu tiên, rồi cái đầu.
  - Điều kiện MSBuild: thay `$(Configuration)`, `$(Platform)`, so sánh `==`/`!=`, `and`/`or`. Không tính được → coi là đúng, ghi note.
  - `ItemDefinitionGroup/ClCompile/PreprocessorDefinitions` (+ `UndefinePreprocessorDefinitions`), bỏ `%(…)`, mục còn `$(` → bỏ, ghi note.
  - Ngầm định của MSBuild: `CharacterSet` Unicode → `UNICODE;_UNICODE`, MultiByte → `_MBCS`; `UseOfMfc` Dynamic → `_AFXDLL`;
    DLL → `_WINDLL`; x64 → `_WIN64;_M_X64`, Win32 → `_M_IX86`.
  - `Import`/`ImportGroup` file `.props` (đường dẫn tương đối, `$(MSBuildThisFileDirectory)`, `$(ProjectDir)`, `$(SolutionDir)` nếu biết);
    bỏ qua `$(VCTargetsPath)`, `$(UserRootDir)`…; tối đa sâu 8, không lặp.
  - Files: `ClCompile`, `ClInclude`, `ResourceCompile` (`Include`, tương đối với thư mục project).
- `vcxproj.read_solution(path) -> [(name, vcxproj_path)]` (chỉ `.vcxproj`, sắp xếp).
- `build_index(..., files=None, pp_by_file=None)`: `files` = danh sách file cụ thể (thay cho quét cây); `pp_by_file`
  = {abs path: PPConfig} cho file thuộc từng project (file không thuộc project nào dùng `pp`).
- CLI: `index <root> --vcxproj "a.vcxproj;b.vcxproj" [--config "Release|Win32"] [--vcxproj-scope listed|folders]`.
  `listed` (mặc định): chỉ file project liệt kê; `folders`: mọi file nguồn trong thư mục chứa các project. File ngoài `<root>` bỏ qua (đếm).
  `--define/--undef` cộng thêm vào define của project. Có `--vcxproj` thì mặc định bật `--undef-unknown` (giống trình biên dịch).
- Test: `samples/BigApp/BigApp.vcxproj` + `.props` + `.sln` tổng hợp; define, file list, điều kiện, index chỉ các file đó.

### S23 — settings.json
- `index` ghi `<root>/.mfcgraph/settings.json` (codepage, exclude, define, undef, undef_unknown, vcxproj (tương đối với root nếu được),
  config, vcxproj_scope). `index <root>` không kèm cờ cấu hình → dùng lại settings đã lưu và in `Using saved settings: …`.
  Có bất kỳ cờ cấu hình nào → cấu hình mới chỉ gồm các cờ đó (không trộn ngầm).
- Test: lưu/đọc; index lần 2 không cờ cho cùng kết quả (cùng define trong `D` records).

### S24 — mcp-config
- `mcp_config.server_entry(root, launcher, python)`; `mcp_config.merge(text, name, entry) -> text` (giữ server khác, khóa `servers`);
  `mcp_config.write(path, name, entry) -> backup_path|None`. JSON không đọc được (vd. có comment) → từ chối, không ghi đè.
- CLI: `mcp-config [--root R] [--name mfcgraph] [--write PATH]`: không `--write` → chỉ in JSON; có → gộp, sao lưu `PATH.bak`.
- Test: tạo mới, gộp giữ server khác, sửa mục cũ, từ chối JSON hỏng, có `.bak`.

### S25 — GUI
- `mfcgraph_gui/logic.py` (không import tkinter, test được): từ form → tham số index, chạy index (dùng core), danh sách project của `.sln`.
- `mfcgraph_gui/app.py` (tkinter): tab Hướng dẫn / Dự án; chọn root, `.sln` (tick project) hoặc `.vcxproj`, cấu hình, codepage, define
  thêm; nút Chạy index (thread, log); nút "Ghi vào .mcp.json" (hộp xem trước, chọn file đích) và "Copy cấu hình MCP".
- `cli gui`: import trễ; thiếu tkinter → in hướng dẫn, mã thoát 2.
- Test: logic; CLI/MCP không nạp `tkinter`/`mfcgraph_gui`; `gui` khi tkinter thiếu báo lỗi đẹp.

### S26 — Tài liệu + đóng gói
- README: mục "Cách nhanh: GUI" và "CLI với .vcxproj", cập nhật bảng cam kết SA (`.mcp.json`, `xml.etree`, `tkinter`).
- CHANGELOG 0.4.0, VERSION 0.4.0, `tools/package.py` thêm `mfcgraph_gui`.

## 4. Ngoài phạm vi
- `serve` tự index lại (có thể làm v0.5 nếu cần). Đọc define riêng theo từng file `.cpp` trong `.vcxproj`. Gói `.exe`.
