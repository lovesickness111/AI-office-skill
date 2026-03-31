---
name: youtube-script-creator
description: >
  Tạo kịch bản video YouTube hoàn chỉnh với thumbnail, tiêu đề, mô tả và bài viết LinkedIn.
  Sử dụng skill này khi người dùng muốn tạo script video YouTube, lên ý tưởng nội dung video,
  chuẩn bị tài liệu đăng video, hoặc tạo bài viết quảng bá video trên mạng xã hội.
  Kích hoạt khi người dùng nhắc đến: kịch bản video, script youtube, tạo video youtube,
  youtube content, đăng video, quảng bá video.
---

# YouTube Script Creator

Skill hướng dẫn tạo kịch bản video YouTube hoàn chỉnh. Khi người dùng cung cấp chủ đề video, 
hãy tạo đầy đủ **4 artifact** theo thứ tự dưới đây. Mỗi artifact phải được tạo ra riêng biệt
và trình bày rõ ràng cho người dùng.

> **LƯU Ý QUAN TRỌNG — Thư mục đầu ra:**  
> Trước khi tạo bất kỳ artifact nào, hãy tạo một **thư mục con** trong thư mục artifacts với tên
> dựa trên chủ đề video (viết thường, dùng dấu gạch nối, không dấu tiếng Việt).  
> Ví dụ: nếu chủ đề là "AI thay thế developer" → tạo thư mục `ai-thay-the-developer/`.  
> **Tất cả các artifact** (thumbnail, mô tả, bài LinkedIn) đều phải được lưu vào thư mục này.

## Quy trình làm việc

### Bước 1: Thu thập thông tin

Trước khi bắt đầu, hỏi người dùng những thông tin sau (nếu chưa rõ):

1. **Chủ đề video**: Nội dung chính video nói về gì?
2. **Đối tượng mục tiêu**: Video hướng đến ai? (developer, người đi làm, sinh viên, ...)
3. **Tone giọng**: Nghiêm túc, vui vẻ, hay pha trộn?
4. **Độ dài dự kiến**: Video ngắn (< 5 phút), trung bình (5-15 phút), hay dài (> 15 phút)?

Nếu người dùng đã cung cấp đủ thông tin trong prompt, bắt đầu tạo artifact ngay mà không cần hỏi thêm.

### Bước 2: Tạo 4 Artifact

Tạo lần lượt theo thứ tự sau. Giữa mỗi artifact, giải thích ngắn gọn lý do đằng sau các lựa chọn
sáng tạo để người dùng hiểu ý đồ.

---

## Artifact 1: Thumbnail YouTube

Dùng tool `generate_image` để tạo ảnh thumbnail. Lưu vào thư mục đầu ra đã tạo ở trên.

### Sử dụng ảnh tham chiếu model

Trước khi tạo thumbnail, hãy **chọn ngẫu nhiên 1 ảnh** từ thư mục `skills/youtube-script-creator/model-image-ref/`:
- Liệt kê các file trong thư mục `model-image-ref/`
- Random chọn 1 file ảnh
- Truyền đường dẫn tuyệt đối của ảnh đã chọn vào tham số `ImagePaths` của tool `generate_image`

Điều này giúp thumbnail có phong cách nhất quán dựa trên hình ảnh tham chiếu của model/người dẫn kênh.

### Yêu cầu bắt buộc về bố cục

- **BẮT BUỘC bố cục NGANG tỷ lệ 16:9** (landscape, width > height). Prompt PHẢI chỉ định rõ: `"wide horizontal 16:9 aspect ratio landscape orientation"` — KHÔNG được tạo ảnh dọc hoặc vuông.
- Kích thước lý tưởng: **1280×720 pixels** hoặc tương đương tỷ lệ 16:9
- Hình ảnh tập trung vào **chủ đề chính** của video
- Phải có **yếu tố gây tò mò** — một chi tiết bất ngờ, một biểu cảm mạnh, hoặc một hình ảnh tương phản khiến người xem muốn click vào
- Màu sắc nổi bật, tương phản cao, dễ nhìn ở kích thước nhỏ
- Nếu có text trên thumbnail, hãy giữ **ngắn gọn 2-4 từ**, font to và dễ đọc

### Prompt cho generate_image

Prompt **LUÔN LUÔN phải bắt đầu bằng**: `"Wide horizontal 16:9 landscape YouTube thumbnail, 1280x720, "`

Ngoài ra cần bao gồm:
- Mô tả bố cục cụ thể (foreground, background)
- Phong cách hình ảnh (realistic, illustration, cinematic, ...)
- Yếu tố gây tò mò cụ thể
- Mô tả cách kết hợp hình ảnh tham chiếu của model vào bố cục (ví dụ: model đứng ở bên trái, biểu cảm bất ngờ, etc.)

**Ví dụ prompt tốt:**
> "Wide horizontal 16:9 landscape YouTube thumbnail, 1280x720, showing the person from the 
> reference image looking shocked at a screen displaying AI-generated code. Bold contrasting 
> colors, dramatic lighting. The screen shows impossibly clean code with a mysterious glowing 
> element. Cinematic style, high contrast, professional YouTube thumbnail composition."

---

## Artifact 2: Tiêu đề video YouTube

Viết tiêu đề video trực tiếp trong phản hồi (không cần tạo file riêng).

**Yêu cầu bắt buộc:**
- Dưới **100 ký tự** (bao gồm cả khoảng trắng)
- **KHÔNG trùng** text đã sử dụng trên thumbnail — tiêu đề và thumbnail phải bổ sung cho nhau, không lặp lại nội dung
- Khơi gợi **sự tò mò**, khiến người xem muốn tìm hiểu thêm
- Kích thích cảm xúc: có thể dùng câu hỏi, con số ấn tượng, hoặc mâu thuẫn bất ngờ

**Công thức tiêu đề hiệu quả:**
- **Câu hỏi kích thích**: "Tại sao [X] lại [kết quả bất ngờ]?"
- **Con số + giá trị**: "[Số] cách để [đạt kết quả] mà không ai nói cho bạn"
- **Mâu thuẫn**: "[Điều phổ biến] thực ra là [sự thật bất ngờ]"
- **Thách thức**: "Thử [hành động] trong [thời gian ngắn] — kết quả gây sốc"

**Ví dụ:**
- Thumbnail text: "AI CODE" → Tiêu đề: "Tôi để AI viết cả dự án trong 24h — và đây là điều xảy ra"
- Thumbnail text: "10X FASTER" → Tiêu đề: "Kỹ thuật debug mà senior developer giấu bạn suốt 5 năm"

Sau khi viết, đếm ký tự và xác nhận: `[XX/100 ký tự]`

---

## Artifact 3: Mô tả video YouTube

Viết nội dung mô tả video trực tiếp trong phản hồi.

**Yêu cầu bắt buộc:**
- Nội dung mô tả **tối đa 5000 ký tự** (không tính khối liên hệ)
- Mô tả phải **chi tiết và đầy đủ** — tận dụng tối đa không gian cho phép
- 2-3 dòng đầu tiên phải cuốn hút vì YouTube chỉ hiển thị phần này trước khi ấn "xem thêm"
- Bao gồm: tóm tắt nội dung, các điểm chính sẽ đề cập, timestamps dự kiến, hashtags liên quan
- **Dưới cùng LUÔN LUÔN có khối liên hệ** đúng format bên dưới:

```
---
📧 Email: vietcuong.uet@gmail.com
👤 Facebook: https://www.facebook.com/cuong.viet.965lovesicknes
```

**Cấu trúc mô tả nên theo:**
1. **Hook** (2-3 câu cuốn hút, hiển thị trước "xem thêm")
2. **Tóm tắt nội dung** (1-2 đoạn mô tả chi tiết video nói về gì)
3. **Những gì bạn sẽ học được** (danh sách bullet points các điểm chính)
4. **Timestamps** (dự kiến các mốc thời gian chính)
5. **Hashtags** (5-10 hashtags liên quan)
6. **Khối liên hệ**

**Ví dụ:**

```
Bạn có bao giờ tự hỏi AI có thể thay thế developer không? Trong video này, 
tôi thử để AI viết toàn bộ một dự án thực tế từ đầu đến cuối. 
Kết quả sẽ khiến bạn phải suy nghĩ lại về cách làm việc của mình.

Tôi đã sử dụng các công cụ AI mới nhất — từ code generation đến debugging — 
để xây dựng một ứng dụng web hoàn chỉnh. Video ghi lại toàn bộ quá trình: 
những lúc AI làm tốt đến bất ngờ, và những lúc nó thất bại thảm hại.

🔍 Những gì bạn sẽ tìm thấy trong video:
• AI có thể viết code production-ready không?
• Những loại task nào AI xử lý tốt nhất?
• Khi nào bạn KHÔNG nên dùng AI để code?
• So sánh thực tế: AI code vs human code
• Verdict cuối cùng: AI là đồng đội hay đối thủ?

⏱️ Timestamps:
0:00 - Giới thiệu thử nghiệm
2:30 - Setup dự án với AI
5:00 - AI viết feature đầu tiên
10:00 - Gặp bug — AI debug được không?
15:00 - Kết quả cuối cùng
18:00 - Verdict & kết luận

#AI #Programming #Developer #AICode #WebDevelopment

---
📧 Email: vietcuong.uet@gmail.com
👤 Facebook: https://www.facebook.com/cuong.viet.965lovesicknes
```

Sau khi viết, đếm ký tự (không tính khối liên hệ) và xác nhận: `[XX/5000 ký tự]`

---

## Artifact 4: Bài viết chia sẻ LinkedIn

Viết một bài viết phù hợp để đăng trên LinkedIn, quảng bá cho video.

**Yêu cầu bắt buộc:**
- Nội dung được rút ra từ **nội dung chính của video**, không chỉ quảng cáo video
- Phong cách **chuyên nghiệp, hướng công việc** — phù hợp với LinkedIn audience
- **Hạn chế tối đa icon/emoji** — không dùng emoji ở đầu mỗi dòng, tối đa 1-2 emoji trong toàn bài nếu thực sự cần thiết
- Cung cấp **giá trị độc lập** — người đọc LinkedIn phải thấy hữu ích ngay cả khi không xem video
- Cuối bài mới đề cập đến video như một nguồn tham khảo thêm
- Độ dài phù hợp: 150-300 từ

**Cấu trúc bài viết LinkedIn hiệu quả:**
1. **Hook** (1-2 câu): Mở đầu bằng insight hoặc quan sát gây chú ý từ góc nhìn chuyên môn
2. **Nội dung chính** (3-5 đoạn ngắn): Chia sẻ bài học, phân tích, hoặc kinh nghiệm thực tế rút ra từ chủ đề video
3. **Kết nối video** (1-2 câu): Giới thiệu video như nguồn tham khảo chi tiết hơn, kèm link
4. **CTA nhẹ nhàng**: Một câu hỏi mở hoặc lời mời thảo luận

**Ví dụ hook tốt:**
- "Tuần vừa rồi tôi thử một thí nghiệm: để AI viết 100% code cho một dự án thực tế. Kết quả không như bạn nghĩ."
- "Sau 3 năm làm việc với AI tools, tôi nhận ra rằng vấn đề không phải AI có thay thế được developer hay không."

**Tránh:**
- Bài viết kiểu "Xem video mới nhất của tôi!!!" — đây không phải quảng cáo
- Mỗi dòng một emoji — LinkedIn audience thấy phản cảm
- Giọng văn quá casual hoặc quá hàn lâm

---

## Checklist trước khi gửi cho người dùng

Trước khi trình bày kết quả cuối cùng, tự kiểm tra:

- [ ] Đã tạo thư mục đầu ra riêng cho video này
- [ ] Thumbnail đã được tạo bằng `generate_image` với ảnh tham chiếu từ `model-image-ref/`
- [ ] Thumbnail đúng bố cục **ngang 16:9** (landscape, KHÔNG phải dọc hoặc vuông)
- [ ] Thumbnail có yếu tố gây tò mò
- [ ] Tiêu đề < 100 ký tự, đã đếm và xác nhận
- [ ] Tiêu đề KHÔNG lặp lại text trên thumbnail
- [ ] Mô tả ≤ 5000 ký tự (không tính khối liên hệ), nội dung chi tiết và đầy đủ
- [ ] Mô tả có khối liên hệ email + Facebook ở cuối
- [ ] Bài LinkedIn có giá trị độc lập, phong cách chuyên nghiệp
- [ ] Bài LinkedIn hạn chế emoji, không dùng emoji đầu mỗi dòng

## Trình bày kết quả

Trình bày mỗi artifact với tiêu đề rõ ràng, ví dụ:

```
## 🎨 Thumbnail
[Ảnh thumbnail đã tạo]

## 📝 Tiêu đề video [XX/100 ký tự]
[Tiêu đề]

## 📋 Mô tả video [XX/5000 ký tự]
[Nội dung mô tả]

## 💼 Bài viết LinkedIn
[Nội dung bài viết]
```

Sau khi trình bày, hỏi người dùng:
> "Bạn muốn điều chỉnh artifact nào không? Tôi có thể sửa từng phần riêng lẻ."
