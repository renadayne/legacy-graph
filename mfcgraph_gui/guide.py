"""Built-in user guide shown in the GUI's first tab (Vietnamese, like README)."""

GUIDE = """\
mfcgraph — hướng dẫn nhanh
==========================

mfcgraph đọc mã nguồn C++/MFC/Win32 trên máy bạn và tạo "bản đồ" (index) để Copilot tìm đúng
đoạn code cần xem. Mọi thứ chạy offline. Tool chỉ ghi vào thư mục <root>\\.mfcgraph\\ và, khi bạn
bấm nút riêng, vào file cấu hình MCP bạn chọn.

Bước 1 — Chọn dự án (tab "Index")
  • Thư mục gốc (root): thư mục chứa code cần index. File index nằm ở <root>\\.mfcgraph\\index.mfg.
    Mỗi root có một index.
  • Bấm "Thêm .vcxproj..." để chọn project của module đang điều tra, hoặc "Thêm từ .sln..." rồi tick
    các project cần. Không cần chọn cả app: chỉ chọn module có bug và các module nó dùng (vd. Common).
  • Chưa chọn root thì tool tự lấy thư mục chung của các project.
  • Không chọn project nào: tool quét toàn bộ cây thư mục root (giống trước đây).

Bước 2 — Cấu hình
  • Cấu hình build: để trống thì tool dùng Release|Win32 (hoặc Release đầu tiên). Define (#ifdef) đọc từ
    .vcxproj và các file .props mà nó import, theo đúng cấu hình đã chọn.
  • Phạm vi: "listed" = chỉ các file mà project liệt kê (nhanh, chính xác); "folders" = mọi file nguồn
    trong thư mục chứa project (khi project thiếu header dùng chung).
  • Codepage: dùng cho file không phải UTF-8/UTF-16. 1258 = tiếng Việt, 932 = tiếng Nhật (Shift-JIS).
  • Define thêm / Undef: cộng thêm vào define của project, dạng A;B=1.
  • Bỏ thư mục: tên thư mục không quét (chỉ dùng khi quét cả cây hoặc phạm vi "folders").

Bước 3 — Bấm "Chạy index"
  • Log hiện số file, số define và các "note" (những gì tool không tính được trong .vcxproj).
  • Cấu hình được lưu vào <root>\\.mfcgraph\\settings.json. Lần sau chỉ cần chạy lại:
        python mfcgraph.py index <root>
    hoặc mở GUI và bấm "Chạy index" (các ô được điền sẵn từ lần trước).
  • Code thay đổi nhiều thì index lại. Khi có file đã sửa sau lần index, Copilot sẽ thấy cảnh báo
    "Changed since last index".

Bước 4 — Kết nối Copilot (MCP)
  • Chọn file đích:
      - Visual Studio 2022: <thư mục solution>\\.mcp.json
      - VS Code: <workspace>\\.vscode\\mcp.json
  • "Xem trước & ghi": hiện nội dung mới trước khi ghi. Tool chỉ thêm/sửa mục "mfcgraph" (hoặc tên bạn
    đặt), giữ nguyên các server khác, và lưu bản cũ thành <file>.bak.
    File có comment (không phải JSON thuần) sẽ không bị sửa: hãy dùng "Copy cấu hình" và dán tay.
  • Sau khi ghi: khởi động lại MCP server trong IDE (hoặc mở lại solution). Copilot sẽ có tool
    mfc_explore.
  • Dùng nhiều root (nhiều module) cùng lúc: đặt tên server khác nhau, vd. mfcgraph-billing.

Dùng với Copilot
  • Hỏi bình thường, vd. "bấm Tính lại thì tổng tiền sai trong module Billing", hoặc dán thông báo lỗi.
    Copilot gọi mfc_explore và nhận đúng các hàm liên quan, kèm số dòng.

Không có MCP?
  • Chạy: python mfcgraph.py explore "câu hỏi" --root <root> > ctx.md, rồi đính kèm #file:ctx.md.

Lệnh tương đương (không cần GUI)
  python mfcgraph.py index <root> --vcxproj "A.vcxproj;B.sln" --config "Release|Win32" --codepage 932
  python mfcgraph.py mcp-config --root <root> --write <root>\\.mcp.json
"""
