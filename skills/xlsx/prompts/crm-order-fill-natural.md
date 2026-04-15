# Hướng dẫn điền sản phẩm vào biểu mẫu Đơn Hàng

## Mô tả biểu mẫu

Biểu mẫu đơn hàng (mau crm.xlsx) là một file Excel có 1 sheet tên "ĐƠN HÀNG". Bố cục từ trên xuống dưới gồm:

- Phần đầu: tiêu đề "ĐƠN HÀNG", thông tin khách hàng, ngày đặt hàng, mã số thuế, số đơn hàng, địa chỉ, người nhận hàng, số điện thoại, lời chào.
- Dòng 13: tiêu đề các cột của bảng sản phẩm gồm STT, ẢNH SẢN PHẨM, TÊN SẢN PHẨM, ĐVT, SL, ĐƠN GIÁ, THÀNH TIỀN (tương ứng cột A đến G). Tất cả các ô từ cột A đến G đều có viền mỏng (thin border) ở cả 4 cạnh.
- Dòng 14 trở đi: vùng để điền danh sách sản phẩm. Các dòng sản phẩm mẫu (14-15) cũng có viền mỏng ở cả 4 cạnh giống dòng tiêu đề.
- Ngay sau vùng sản phẩm: khối tổng hợp gồm 4 dòng liên tiếp chứa "Tổng thành tiền", "Tiền chiết khấu", "Thuế GTGT", "Tổng tiền thanh toán". Trong template gốc khối này nằm ở dòng 16-19. Khối này có các ô được gộp (merged cells) và chứa công thức tính toán.
- Cuối cùng: dòng số tiền viết bằng chữ và phần chữ ký.

## Điều quan trọng cần biết

Khối tổng hợp (từ dòng 16 trong template gốc) có nhiều ô được gộp lại với nhau. Đây là điểm gây lỗi chính: nếu bạn ghi dữ liệu sản phẩm trực tiếp vào dòng có ô gộp, dữ liệu sẽ bị mất hoặc hiển thị sai.

Thư viện openpyxl có một đặc điểm quan trọng: khi bạn dùng lệnh chèn dòng mới (insert_rows), dữ liệu trong các ô sẽ được di chuyển xuống đúng, nhưng các vùng ô gộp (merged cells) thì KHÔNG tự động di chuyển theo. Chúng vẫn nằm nguyên ở vị trí cũ. Vì vậy bạn phải tự tay xử lý việc di chuyển các vùng ô gộp.

## Quy trình bắt buộc khi điền sản phẩm

Khi nhận yêu cầu điền N sản phẩm vào biểu mẫu, bạn phải thực hiện đúng 6 bước sau theo đúng thứ tự. Không được bỏ qua hay thay đổi thứ tự bất kỳ bước nào.

### Bước 1 — Gỡ các vùng ô gộp

Trước tiên, hãy tìm tất cả các vùng ô gộp (merged cells) trong sheet mà có dòng bắt đầu từ dòng 14 trở đi. Ghi nhớ danh sách các vùng ô gộp này. Sau đó gỡ (unmerge) tất cả chúng ra. Việc này giúp tránh xung đột khi chèn dòng mới.

### Bước 2 — Chèn dòng mới

Chèn đúng N dòng trống mới tại vị trí dòng 14. Phải chèn tất cả N dòng cùng một lúc, không chèn từng dòng một. Sau khi chèn, toàn bộ nội dung từ dòng 14 cũ trở đi sẽ bị đẩy xuống dưới N dòng. Lúc này các dòng 14 đến 14+N-1 là các dòng trống mới sẵn sàng cho bạn điền sản phẩm.

### Bước 3 — Gộp lại các ô ở vị trí mới

Với mỗi vùng ô gộp đã ghi nhớ ở Bước 1, hãy tính lại vị trí mới bằng cách cộng thêm N vào số dòng. Ví dụ: nếu trước đó vùng gộp ở dòng 16 đến 19, và bạn chèn 3 sản phẩm, thì vị trí mới sẽ là dòng 19 đến 22. Cột giữ nguyên, chỉ thay đổi dòng. Sau đó gộp (merge) lại các ô ở vị trí mới.

### Bước 4 — Điền dữ liệu sản phẩm

Bây giờ điền thông tin từng sản phẩm vào các dòng trống vừa chèn:
- Dòng 14: sản phẩm thứ 1
- Dòng 15: sản phẩm thứ 2
- Dòng 16: sản phẩm thứ 3
- ... tiếp tục cho đến dòng 14+N-1

Với mỗi sản phẩm, điền vào các cột:
- Cột A: số thứ tự (1, 2, 3, ...)
- Cột B: ảnh sản phẩm (có thể để trống)
- Cột C: tên sản phẩm
- Cột D: đơn vị tính (Cái, Bộ, Chiếc, ...)
- Cột E: số lượng
- Cột F: đơn giá
- Cột G: thành tiền — dùng công thức Excel nhân số lượng với đơn giá (ví dụ dòng 14 thì công thức là =E14*F14)

### Bước 5 — Kẻ viền cho các dòng sản phẩm

Các dòng mới chèn vào sẽ không có viền (border). Bạn phải kẻ viền mỏng (thin border) ở cả 4 cạnh (trái, phải, trên, dưới) cho tất cả các ô từ cột A đến cột G của mỗi dòng sản phẩm vừa điền. Điều này đảm bảo bảng sản phẩm có viền đồng nhất, trông chuyên nghiệp và khớp với định dạng của dòng tiêu đề (dòng 13).

### Bước 6 — Cập nhật các công thức tổng

Sau khi chèn dòng, các dòng tổng hợp đã bị đẩy xuống. Bạn cần cập nhật lại các công thức cho đúng:

- Ô tổng thành tiền (cột F, nằm ở dòng 16+N): đổi công thức thành tổng cột G từ dòng sản phẩm đầu tiên đến dòng sản phẩm cuối cùng. Ví dụ với 3 sản phẩm: =SUM(G14:G16).
- Ô tổng tiền thanh toán (cột F, nằm ở dòng 19+N): đổi công thức thành lấy tổng thành tiền trừ chiết khấu trừ thuế, phải tham chiếu đúng dòng mới.

## Những điều tuyệt đối không được làm

1. Không bao giờ ghi dữ liệu sản phẩm vào các dòng có sẵn mà không chèn dòng mới trước. Template gốc chỉ có 2 dòng trống (14 và 15) cho sản phẩm. Nếu bạn cần điền 3 sản phẩm trở lên mà không chèn dòng mới, sản phẩm sẽ ghi đè lên dòng tổng.

2. Không bao giờ chỉ dùng lệnh chèn dòng mà quên xử lý ô gộp. Nếu bạn chèn dòng mà không gỡ và gộp lại ô ở vị trí mới, các ô gộp sẽ chồng lên vùng sản phẩm gây hiển thị sai.

3. Không chèn dòng từng cái một. Luôn chèn tất cả N dòng cùng một lúc để tránh tính sai vị trí.

4. Không tính toán thành tiền bằng Python rồi ghi kết quả cố định. Luôn dùng công thức Excel để file có thể tự cập nhật khi dữ liệu thay đổi.

5. Không quên kẻ viền cho các dòng sản phẩm mới. Dòng mới chèn vào luôn trống hoàn toàn, không có bất kỳ định dạng nào. Nếu không kẻ viền, bảng sản phẩm sẽ trông thiếu chuyên nghiệp với các dòng không có đường kẻ.

## Ví dụ minh họa

Giả sử người dùng yêu cầu điền 3 sản phẩm: Bàn gỗ (2 cái, 3.500.000đ), Ghế xoay (5 cái, 1.200.000đ), Kệ sách (1 bộ, 2.800.000đ).

Bạn sẽ thực hiện:

1. Gỡ tất cả ô gộp từ dòng 14 trở đi (bao gồm các ô gộp ở dòng 16-21 của khối tổng hợp và chữ ký).
2. Chèn 3 dòng mới liên tiếp tại dòng 14. Giờ dòng 14, 15, 16 là trống. Khối tổng hợp cũ (dòng 16-19) bây giờ nằm ở dòng 19-22. Phần chữ ký cũng dịch xuống tương ứng.
3. Gộp lại các ô theo vị trí mới. Ví dụ ô gộp cũ A16:C19 giờ thành A19:C22, ô gộp cũ D16:E16 giờ thành D19:E19, v.v.
4. Điền dữ liệu:
   - Dòng 14: STT=1, Tên=Bàn gỗ, ĐVT=Cái, SL=2, Đơn giá=3500000, Thành tiền=công thức =E14*F14
   - Dòng 15: STT=2, Tên=Ghế xoay, ĐVT=Cái, SL=5, Đơn giá=1200000, Thành tiền=công thức =E15*F15
   - Dòng 16: STT=3, Tên=Kệ sách, ĐVT=Bộ, SL=1, Đơn giá=2800000, Thành tiền=công thức =E16*F16
5. Kẻ viền mỏng (thin border) cả 4 cạnh cho tất cả ô A14:G16 (3 dòng × 7 cột = 21 ô).
6. Cập nhật công thức:
   - Dòng 19 (tổng thành tiền): =SUM(G14:G16)
   - Dòng 22 (tổng thanh toán): =F19-F20-F21

Kết quả: 3 sản phẩm nằm gọn ở dòng 14-16 với viền đầy đủ, khối tổng hợp nằm đúng ở dòng 19-22 với ô gộp và công thức chính xác, không có xung đột hay lỗi gì.
