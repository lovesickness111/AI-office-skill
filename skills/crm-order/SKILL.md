---
name: crm-order
description: "Dùng skill này khi người dùng muốn tạo đơn hàng CRM, nhập thông tin đơn hàng, điền phiếu đặt hàng, hoặc tạo file Excel đơn hàng từ thông tin khách hàng và sản phẩm — dù người dùng nói bằng ngôn ngữ tự nhiên, đọc danh sách, hay viết tắt. Trigger ngay cả khi người dùng chỉ nêu tên khách hàng và sản phẩm mà không đề cập đến file Excel. Skill này tự động xử lý toàn bộ quy trình mà không cần hỏi lại người dùng."
---

# CRM Order — Nhập Đơn Hàng Tự Động

Skill này nhận thông tin đơn hàng từ người dùng (ngôn ngữ tự nhiên, danh sách, câu nói tắt) và **tự động** điền vào file `mau crm.xlsx`, tạo file output mới — không hỏi lại, không chờ xác nhận.

## Template Excel

File gốc: `e:/Sourcecode/AI-office-skill/mau crm.xlsx`  
Thư mục output: `e:/Sourcecode/AI-office-skill/output/`

### Mapping các ô cần điền

| Ô | Nội dung | Prefix |
|---|----------|--------|
| A4 | Tên khách hàng / công ty | `Khách hàng: ` |
| E4 | Ngày đặt hàng (dd/mm/yyyy) | `Ngày đặt hàng: ` |
| A5 | Mã số thuế | `Mã số thuế: ` |
| E5 | Số đơn hàng | `Số đơn hàng: ` |
| A6 | Địa chỉ hóa đơn (merge A6:G6) | `Địa chỉ hóa đơn: ` |
| A9 | Người nhận hàng | `Người nhận hàng: ` |
| E9 | SĐT người nhận | `SĐT người nhận: ` |
| A10 | Địa chỉ giao hàng (merge A10:G10) | `Địa chỉ giao hàng: ` |

### Bảng sản phẩm (từ dòng 14)

| Cột | Nội dung | Ghi chú |
|-----|----------|---------|
| A | STT | Tự tăng 1, 2, 3... |
| B | Ảnh sản phẩm | Để trống |
| C | Tên sản phẩm | |
| D | Đơn vị tính | Cái / Bộ / Chiếc / Hộp... |
| E | Số lượng | Số nguyên |
| F | Đơn giá | Số nguyên (VNĐ) |
| G | Thành tiền | **Công thức** `=E{row}*F{row}` — KHÔNG tính bằng Python |

### Khối tổng (sau vùng sản phẩm)

- Dòng summary+0: `=SUM(G14:G{last_product_row})`
- Dòng summary+3: `=F{summary}-F{summary+1}-F{summary+2}`

---

## Quy trình thực hiện (KHÔNG hỏi lại người dùng)

### Bước 1 — Phân tích văn bản, trích xuất dữ liệu

Đọc toàn bộ nội dung người dùng cung cấp. Nhận diện và trích xuất:

**Thông tin đơn hàng** — nhận dạng theo từ khoá linh hoạt:
- Khách hàng: "khách hàng", "công ty", "đơn vị", "bên mua", "tên"
- Mã số thuế: "MST", "mã số thuế", "tax"
- Địa chỉ hóa đơn: "địa chỉ hóa đơn", "địa chỉ xuất hóa đơn", "địa chỉ công ty"
- Ngày đặt hàng: "ngày đặt", "ngày order", "ngày mua", "date"
- Số đơn hàng: "mã đơn", "số đơn", "đơn số", "order", "DH-..."
- Người nhận: "người nhận", "giao cho", "nhận hàng"
- SĐT: "SĐT", "số điện thoại", "phone", "di động", "liên hệ"
- Địa chỉ giao: "địa chỉ giao", "giao đến", "giao tới", "ship đến"
- Chiết khấu: "chiết khấu", "discount", "CK"
- Thuế GTGT: "thuế", "VAT", "GTGT", "10%"...

**Danh sách sản phẩm** — chấp nhận mọi định dạng:
- `"Tên SP - ĐVT - SL - Đơn giá - Thành tiền"` (có dấu gạch)
- `"1. Tên sp, 2 cái, 100,000đ/cái"` (đánh số)
- `"Tên sp: 3 hộp, 25k/hộp"` (tự do)
- Dạng nói: "ba cái bàn phím, mỗi cái một triệu hai"

**Xử lý số tiền:**
- "15 triệu" / "15tr" / "15,000,000" → 15000000
- "300 nghìn" / "300k" / "300.000" → 300000
- "1 triệu 2" / "1tr2" / "1.2tr" → 1200000
- "25k" → 25000

**Giá trị mặc định nếu thiếu thông tin:**
- Mã số thuế → `""`
- Số đơn hàng → `"DH-{ngày hôm nay}-001"` (format: DH-YYYYMMDD-001)
- Người nhận → lấy tên khách hàng nếu có
- Địa chỉ giao hàng → lấy địa chỉ hóa đơn nếu có
- SĐT → `""`
- Chiết khấu, thuế → 0
- Đơn vị tính → `"Cái"` nếu không rõ

### Bước 2 — Tạo JSON chuẩn

```json
{
  "khach_hang": "...",
  "ma_so_thue": "...",
  "dia_chi_hoa_don": "...",
  "ngay_dat_hang": "dd/mm/yyyy",
  "so_don_hang": "DH-YYYYMMDD-XXX",
  "nguoi_nhan": "...",
  "dia_chi_giao_hang": "...",
  "sdt_nguoi_nhan": "...",
  "chiet_khau": 0,
  "thue_gtgt": 0,
  "san_pham": [
    {"ten": "...", "dvt": "Cái", "sl": 1, "don_gia": 1000000}
  ]
}
```

### Bước 3 — Tạo thư mục output (nếu chưa có)

```powershell
New-Item -ItemType Directory -Path "e:/Sourcecode/AI-office-skill/output" -Force | Out-Null
```

### Bước 4 — Lưu JSON ra file tạm và chạy script

```powershell
# Lưu JSON (thay thế {...} bằng JSON thực tế từ Bước 2)
@'
{...}
'@ | Out-File -FilePath "e:/Sourcecode/AI-office-skill/output/_order_temp.json" -Encoding utf8

# Chạy script điền Excel
python "e:/Sourcecode/AI-office-skill/skills/crm-order/scripts/fill_crm.py" `
  --json-file "e:/Sourcecode/AI-office-skill/output/_order_temp.json" `
  "e:/Sourcecode/AI-office-skill/mau crm.xlsx" `
  "e:/Sourcecode/AI-office-skill/output/don_hang_{so_don_hang}.xlsx"
```

Đặt tên file output: `don_hang_{so_don_hang}.xlsx` (ví dụ: `don_hang_DH-20260411-001.xlsx`)

### Bước 5 — Báo cáo kết quả

Sau khi script chạy thành công, thông báo ngắn gọn:
- ✅ Đường dẫn file output đầy đủ
- 📋 Tóm tắt: tên khách hàng, số đơn, số lượng sản phẩm, và tổng tiền ước tính (tính từ JSON)

---

## Script tham khảo

Script Python xử lý toàn bộ logic chèn dòng, xử lý merged cells, và công thức:

📄 `scripts/fill_crm.py` — Nhận `--json-file <path>` hoặc JSON string inline.

Logic script:
1. Unmerge tất cả merged cells từ dòng 14 trở đi
2. Insert N dòng mới tại dòng 14
3. Re-merge cells tại vị trí mới (dịch xuống N)
4. Điền header (A4, E4, A5, E5, A6, A9, E9, A10)
5. Điền từng sản phẩm với công thức `=E{row}*F{row}` cho cột G
6. Cập nhật `=SUM(...)` và `=F{n}-F{n+1}-F{n+2}` cho khối tổng
7. Kẻ thin border cho tất cả ô sản phẩm (A đến G)

---

## Ví dụ thực tế

**Input người dùng:**
> Khách hàng Thiên Long, MST 0302918399, địa chỉ 123 Đinh Tiên Hoàng HCM. Ngày 15/4/2026, đơn DH-001. Giao anh Minh 0901234567, địa chỉ 789 Lý Thường Kiệt Q10.
> Sản phẩm: Bút bi 50 hộp 25k, Tập 200 trang 30 cuốn 12k, Thước nhựa 20 cái 8k.

**Agent tự suy ra và điền:**

| Trường | Giá trị |
|--------|---------|
| khach_hang | Thiên Long |
| ma_so_thue | 0302918399 |
| dia_chi_hoa_don | 123 Đinh Tiên Hoàng HCM |
| ngay_dat_hang | 15/04/2026 |
| so_don_hang | DH-001 |
| nguoi_nhan | Minh |
| sdt_nguoi_nhan | 0901234567 |
| dia_chi_giao_hang | 789 Lý Thường Kiệt Q10 |

Sản phẩm:
- Bút bi, Hộp, 50, 25000
- Tập 200 trang, Cuốn, 30, 12000
- Thước nhựa, Cái, 20, 8000

**Kết quả:** File `don_hang_DH-001.xlsx` được tạo tự động.
