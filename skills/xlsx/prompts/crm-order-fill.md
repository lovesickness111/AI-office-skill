# Hướng dẫn điền sản phẩm vào biểu mẫu Đơn Hàng (mau crm.xlsx)

## Cấu trúc file template

File `mau crm.xlsx` có cấu trúc sheet "ĐƠN HÀNG" như sau:

| Dòng | Nội dung |
|------|----------|
| 1-2  | Tiêu đề "ĐƠN HÀNG" (merge A1:G2) |
| 4    | Khách hàng / Ngày đặt hàng |
| 5    | Mã số thuế / Số đơn hàng |
| 6    | Địa chỉ hóa đơn |
| 9    | Người nhận hàng / SĐT |
| 10   | Địa chỉ giao hàng |
| 12   | Lời chào |
| **13** | **Header bảng sản phẩm**: STT (A), ẢNH SẢN PHẨM (B), TÊN SẢN PHẨM (C), ĐVT (D), SL (E), ĐƠN GIÁ (F), THÀNH TIỀN (G) |
| **14+** | **Vùng điền sản phẩm** (bắt đầu từ dòng 14) |
| 16   | Tổng thành tiền (merge A16:C19, D16:E16, F16:G16) - có formula `=SUM(G14:G15)` |
| 17   | Tiền chiết khấu (merge D17:E17, F17:G17) |
| 18   | Thuế GTGT (merge D18:E18, F18:G18) |
| 19   | Tổng tiền thanh toán (merge D19:E19, F19:G19) - có formula `=F16-F17-F18` |
| 20   | Số tiền viết bằng chữ (merge A20:G20) |
| 21+  | Chữ ký |

### Các cột sản phẩm (dòng 13):
- **A**: STT (số thứ tự: 1, 2, 3,...)
- **B**: ẢNH SẢN PHẨM (có thể để trống hoặc chèn ảnh)
- **C**: TÊN SẢN PHẨM
- **D**: ĐVT (đơn vị tính: Cái, Bộ, Chiếc,...)
- **E**: SL (số lượng)
- **F**: ĐƠN GIÁ (đơn giá)
- **G**: THÀNH TIỀN (= SL × ĐƠN GIÁ, dùng công thức Excel)

---

## ⚠️ VẤN ĐỀ QUAN TRỌNG: openpyxl KHÔNG tự di chuyển merged cells

`openpyxl.insert_rows()` chỉ di chuyển dữ liệu ô (cell data) nhưng **KHÔNG** tự động di chuyển các merged cell ranges. Nếu chỉ dùng `insert_rows()` mà không xử lý merge, các merged cells của dòng tổng sẽ nằm chồng lên dòng sản phẩm → **lỗi hiển thị và mất dữ liệu**.

---

## ✅ QUY TRÌNH BẮT BUỘC KHI ĐIỀN SẢN PHẨM (5 BƯỚC)

### Bước 1: Xác định các merged cells cần di chuyển

Tìm tất cả merged cells có `min_row >= 14` (dòng bắt đầu điền sản phẩm). Lưu lại và **unmerge** chúng.

### Bước 2: Insert N dòng mới tại dòng 14

Dùng `ws.insert_rows(14, amount=N)` để chèn N dòng trống. Thao tác này di chuyển dữ liệu ô xuống nhưng **KHÔNG di chuyển merged cells**.

### Bước 3: Re-merge cells tại vị trí mới

Với mỗi merged range đã lưu ở Bước 1, tính vị trí mới bằng cách cộng thêm N vào cả min_row và max_row, rồi merge lại.

### Bước 4: Điền dữ liệu sản phẩm

Điền vào các dòng 14, 15, ..., 14 + N - 1.

### Bước 5: Cập nhật công thức

- Cập nhật `=SUM(G14:G{14+N-1})` ở ô tổng thành tiền
- Cập nhật `=F{summary}-F{summary+1}-F{summary+2}` ở ô tổng thanh toán

---

## 📋 CODE MẪU ĐẦY ĐỦ

```python
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

# Dữ liệu sản phẩm cần điền
products = [
    {"ten": "Sản phẩm A", "dvt": "Cái", "sl": 2, "don_gia": 100000},
    {"ten": "Sản phẩm B", "dvt": "Bộ", "sl": 1, "don_gia": 250000},
    {"ten": "Sản phẩm C", "dvt": "Chiếc", "sl": 5, "don_gia": 50000},
]

wb = load_workbook('mau crm.xlsx')
ws = wb.active
n = len(products)
insert_at = 14  # Dòng bắt đầu điền sản phẩm

# ================================================================
# BƯỚC 1: Lưu và unmerge tất cả merged cells từ dòng insert_at trở đi
# ================================================================
merges_to_move = []
for merge_range in list(ws.merged_cells.ranges):
    if merge_range.min_row >= insert_at:
        merges_to_move.append(str(merge_range))
        ws.unmerge_cells(str(merge_range))

# ================================================================
# BƯỚC 2: Insert N dòng mới tại dòng insert_at
# ================================================================
ws.insert_rows(insert_at, amount=n)

# ================================================================
# BƯỚC 3: Re-merge cells tại vị trí mới (shift xuống n dòng)
# ================================================================
for merge_str in merges_to_move:
    min_col, min_row, max_col, max_row = range_boundaries(merge_str)
    new_range = (
        f"{get_column_letter(min_col)}{min_row + n}"
        f":{get_column_letter(max_col)}{max_row + n}"
    )
    ws.merge_cells(new_range)

# ================================================================
# BƯỚC 4: Điền dữ liệu sản phẩm
# ================================================================
for i, product in enumerate(products):
    row = insert_at + i
    ws.cell(row=row, column=1, value=i + 1)                      # STT
    # ws.cell(row=row, column=2)                                  # Ảnh (bỏ trống)
    ws.cell(row=row, column=3, value=product["ten"])              # Tên SP
    ws.cell(row=row, column=4, value=product["dvt"])              # ĐVT
    ws.cell(row=row, column=5, value=product["sl"])               # SL
    ws.cell(row=row, column=6, value=product["don_gia"])          # Đơn giá
    ws.cell(row=row, column=7).value = f'=E{row}*F{row}'         # Thành tiền

# ================================================================
# BƯỚC 5: Cập nhật công thức
# ================================================================
summary_row = 16 + n           # Dòng "Tổng thành tiền" sau khi insert
last_product_row = insert_at + n - 1
payment_row = 19 + n           # Dòng "Tổng tiền thanh toán" sau khi insert

ws.cell(row=summary_row, column=6).value = f'=SUM(G{insert_at}:G{last_product_row})'
ws.cell(row=payment_row, column=6).value = f'=F{summary_row}-F{summary_row+1}-F{summary_row+2}'

wb.save('don_hang_output.xlsx')
```

---

## ❌ CÁC LỖI THƯỜNG GẶP - KHÔNG ĐƯỢC LÀM

### Lỗi 1: Chỉ dùng insert_rows mà không xử lý merge

```python
# ❌ SAI: insert_rows KHÔNG di chuyển merged cells
ws.insert_rows(14, amount=3)
# Merged cells A16:C19 vẫn nằm tại chỗ cũ → chồng lên sản phẩm!
```

### Lỗi 2: Ghi trực tiếp vào dòng có sẵn mà không insert

```python
# ❌ SAI: Dòng 16 là dòng tổng có merged cells → bị ghi đè
ws.cell(row=14, column=3, value="SP 1")
ws.cell(row=15, column=3, value="SP 2")
ws.cell(row=16, column=3, value="SP 3")  # GHI ĐÈ DÒNG TỔNG!
```

### Lỗi 3: Insert từng dòng rồi điền xen kẽ

```python
# ❌ SAI: Offset bị lệch sau mỗi lần insert
for i, product in enumerate(products):
    ws.insert_rows(14 + i)  # Mỗi lần insert làm offset thay đổi!
    ws.cell(row=14 + i, ...)
```

---

## 🔑 TÓM TẮT

1. **MUST unmerge** → insert → re-merge (3 bước xử lý merged cells)
2. Insert **tất cả N dòng cùng lúc** bằng `ws.insert_rows(14, amount=N)`
3. Sản phẩm điền từ **dòng 14** trở đi
4. Sau khi insert, **cập nhật tất cả công thức** (SUM, tổng thanh toán)
5. Dùng **công thức Excel** cho cột Thành tiền: `=E{row}*F{row}`
