# Kế hoạch mfcgraph v0.3: codebase trộn MFC + Win32 + C

> Cùng quy tắc với `docs/PLAN.md` (mục 0 và 2): mỗi lần một step, mỗi step một commit `S<id>: …`, test pass mới commit,
> ghi ≤6 dòng vào `docs/STATUS.md`, push ngay. Không đọc lại code v0.2: đọc `docs/STATUS.md` và docstring đầu module.

## 1. Bối cảnh (từ `diagnose` + số đếm của người dùng, không có code thật)

Một module 49 file: 43 file Shift-JIS (`--codepage 932`), 0 file lệch ngoặc, 19 dialog, 58 menu, 86 chuỗi STRINGTABLE.
- Gần như không có MFC: `BEGIN_MESSAGE_MAP = 1`, `public CDialog = 0`, `public CWnd = 0`. Không phải ATL/WTL.
- Win32 thuần: `CALLBACK = 300`, `case WM_COMMAND = 17` → dispatch bằng `switch (msg)` / `switch (LOWORD(wParam))`.
- `#ifdef 205`, `#ifndef 74`, `#else 329`, `#elif 4`, `#if 0 31`; 48.653 token bị bỏ (tool luôn giữ nhánh đầu).
- Toàn dự án trộn MFC, Win32 và file `.c`.
- Hệ quả: menu/nút → handler không nối được (Flow trống), "framework entry" = 0. Tìm theo chuỗi lỗi vẫn dùng tốt.

## 2. Mục tiêu v0.3
- Win32: nối nút/menu/ID → `case IDC_X:` trong window/dialog procedure → các hàm gọi trong nhánh đó; dialog `IDD_X` ↔ procedure.
- C: file `.c` được phân tích đúng dù dùng `new`, `class`, `this`… làm tên biến; hàm `static` trùng tên giữa các file.
- `#ifdef`: chọn nhánh theo macro người dùng khai báo (`--define/--undef`), thay vì luôn giữ nhánh đầu.
- MFC v0.2 giữ nguyên (golden test không đổi trừ khi step nói rõ).

**Tiêu chí hoàn thành:** đánh giá trên `samples/Win32App` (S20) đạt recall ≥ 0,9 và 100% trong ngân sách; BigApp vẫn ≥ 0,9;
`diagnose` trên dự án thật (người dùng gửi lại) có số "Win32 dispatch cases" > 0 và số token bị bỏ giảm khi dùng `--define`.

## 3. Các step

| Step | Việc | Model | Phụ thuộc | Cỡ |
| --- | --- | --- | --- | --- |
| S15 | Dự án mẫu `samples/Win32App` + `tests/scenarios_win32.json` | sample-writer, model chính review | — | M |
| S16 | Chế độ C cho file `.c` (từ khóa C++ thành identifier) | implementer | S15 | S |
| S17 | `--define/--undef`: tính điều kiện `#if` | model chính | S15 | M |
| S18 | Win32 dispatch: `case` trong procedure → cạnh `handled_by` | model chính | S15 | L |
| S19 | Win32 wiring: DialogBox/CreateDialog/lpfnWndProc/SetWindowLongPtr/callback → procedure | model chính | S18 | M |
| S20 | Explore + đánh giá Win32, tinh chỉnh | model chính | S16–S19 | M |
| S21 | `diagnose` bổ sung + README (VI) + CHANGELOG 0.3 | implementer / doc-writer | S20 | S |

### S15 — Dự án mẫu Win32App
- Khoảng 25–35 file trong `samples/Win32App/`: `Main.c` (WinMain, `wc.lpfnWndProc = MainWndProc`), `MainWnd.cpp`
  (`LRESULT CALLBACK MainWndProc`, `switch (msg)`, `case WM_COMMAND: switch (LOWORD(wParam)) { case IDM_FILE_SAVE: … }`),
  2–3 dialog procedure (`INT_PTR CALLBACK XxxDlgProc`, `WM_INITDIALOG`, `case IDOK`), một file dùng `HANDLE_MSG` của
  windowsx.h, một subclass bằng `SetWindowLongPtr(hEdit, GWLP_WNDPROC, (LONG_PTR)EditSubclassProc)`, worker thread
  `PostMessage(hWnd, WM_APP_DONE, …)` → `case WM_APP_DONE`, một file `.c` có biến tên `new`/`class`, hàm `static` trùng tên ở
  hai file `.c`, một module nhỏ MFC dùng chung `resource.h`, file Shift-JIS, `#ifdef FEATURE_X … #else (code thật) #endif`.
- `.rc` UTF-16 có menu, accelerator, dialog với caption tiếng Nhật và tiếng Việt.
- `tests/scenarios_win32.json`: 12 kịch bản cùng định dạng S1 (query, must_include, max_chars).

### S16 — Chế độ C
- Với file `.c` (và `.h` chỉ được include từ `.c`, nếu xác định được; mặc định `.h` vẫn là C++): `class new delete this
  template namespace typename operator virtual public private protected` là identifier thường.
- Test: hàm `.c` có `struct node *new = …; int class = 0;` vẫn tách đúng và lời gọi bên trong vẫn được ghi nhận.

### S17 — `--define` / `--undef`
- `index --define A;B=1 --undef C`. Tính `#ifdef X`, `#ifndef X`, `#if defined(X)`, `!`, `&&`, `||`, `#if 0/1`, so sánh số
  nguyên đơn giản với macro đã biết. Không tính được (macro chưa khai báo) → giữ hành vi cũ (nhánh đầu) và đếm là "guessed".
- Lưu danh sách define vào header index (index format v3, vẫn đọc v1/v2). `diagnose`: "conditionals: evaluated N, guessed M".
- Gợi ý (không bắt buộc): đọc `PreprocessorDefinitions` từ `.vcxproj` nằm ngoài phạm vi v0.3.

### S18 — Win32 dispatch
- Nhận diện procedure: hàm có `CALLBACK`/`WINAPI` trong chữ ký và tham số `(HWND, UINT, WPARAM, LPARAM)`, hoặc được gán
  vào `lpfnWndProc`/truyền cho DialogBox… (S19).
- Trong procedure: `case WM_xxx:` ở `switch` ngoài → cạnh `WM_xxx handled_by proc` (extra `case@line`); `case ID:` lồng trong
  `case WM_COMMAND`/`WM_NOTIFY` → cạnh `ID handled_by proc` với dòng của `case`; lời gọi nằm trong khối `case` đó → ghi lại
  để explore lấy cửa sổ code đúng đoạn. `HANDLE_MSG(hwnd, WM_X, Fn)` → `WM_X handled_by Fn`.
- Cờ mới `win32-proc` (do Windows gọi). Explore: focus line = dòng `case`.
- Test: menu "File > Save" → `IDM_FILE_SAVE` → `MainWndProc` (dòng case) → hàm lưu.

### S19 — Win32 wiring
- `DialogBox/DialogBoxParam/CreateDialog/CreateDialogParam(…, MAKEINTRESOURCE(IDD_X) | IDD_X, …, Proc)` → `IDD_X` ↔ `Proc`
  (cạnh `uses_dialog` từ procedure tới dialog), để caption/nút của dialog dẫn tới procedure.
- `wc.lpfnWndProc = Proc`, `SetWindowLongPtr/SetWindowLong(…, GWLP_WNDPROC|GWL_WNDPROC, … Proc)`, `CreateThread`/
  `_beginthreadex`/`AfxBeginThread(Proc, …)`, `SetTimer(…, TimerProc)`, `EnumWindows(Proc, …)`: tên hàm được truyền làm tham
  số → cạnh `callback` (heuristic) từ hàm truyền tới hàm được truyền.
- Test: caption dialog tiếng Nhật → `XxxDlgProc`; subclass → `EditSubclassProc`.

### S20 — Đánh giá + tinh chỉnh
- `tests/eval_explore.py --samples samples/Win32App --scenarios tests/scenarios_win32.json` (đã hỗ trợ tham số). Thêm vào `run_all.py`.
- Tinh chỉnh như S9; mỗi thay đổi có nguyên lý chung, ghi STATUS. BigApp không được tụt dưới 0,9.

### S21 — Hoàn thiện
- `diagnose`: số procedure Win32, số `case` dispatch đã nối, số cạnh callback, conditionals evaluated/guessed, file C.
- README: mục Win32/C, `--define`, ví dụ. CHANGELOG 0.3.0, VERSION 0.3.0.

## 4. Câu hỏi còn mở (cần người dùng trả lời trước S17)
- Các nhánh `#ifdef … #else` thường dựa trên macro nào? Macro chuẩn (`_DEBUG`, `UNICODE`, `_WIN64`) ghi thẳng tên; macro riêng
  của công ty có thể đổi tên giả. Hoặc danh sách `PreprocessorDefinitions` trong `.vcxproj` (đã đổi tên giả nếu cần).
- Có dùng `HANDLE_MSG` / windowsx.h không? (đếm `HANDLE_MSG`, `DialogBox`, `CreateDialog`, `lpfnWndProc`, `GWLP_WNDPROC`).
