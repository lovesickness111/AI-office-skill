# AI Office Skill

A comprehensive suite of AI agent skills designed to create, read, edit, analyze, and manipulate various office document formats. These skills empower AI agents to handle complex document workflows across popular file types while maintaining high professional standards.

## Covered Document Types

This repository contains dedicated skills for the following file formats:

### Word Documents (`docx`)
- **Capabilities:** Create new professional documents, read/analyze content (including tracked changes and XML), edit existing documents, generate tables of contents, and add headers/footers.
- **Key Tools:** `docx-js` (via Node.js), `pandoc`, LibreOffice (conversion).
- **Features:** Supports precise page sizing (US Letter/A4), professional typography, multi-column layouts, and direct XML tracked-change edits.

### Spreadsheets (`xlsx`)
- **Capabilities:** Read, edit, analyze, and create `.xlsx`, `.xlsm`, `.csv`, and `.tsv` files.
- **Key Tools:** `pandas` (for data analysis), `openpyxl` (for formatting/formulas), LibreOffice (for formula recalculation).
- **Features:** Strict adherence to financial modeling standards, color coding, dynamic formula generation (zero hardcoded calculations), and built-in scripts to verify zero formula errors (`#REF!`, `#DIV/0!`, etc.).

### PDF Documents (`pdf`)
- **Capabilities:** Read text/tables, merge/split PDFs, rotate pages, add watermarks, extract images, perform OCR on scanned PDFs, and create new PDFs.
- **Key Tools:** `pypdf`, `pdfplumber`, `reportlab`, `qpdf`, `pdftoppm`, `pytesseract`.
- **Features:** Robust layout preservation, table extraction, form filling, and protection/encryption.

### PowerPoint Presentations (`pptx`)
- **Capabilities:** Create pitch decks/presentations from scratch, edit existing slides, extract text, and apply templates.
- **Key Tools:** `markitdown` (text extraction), `pptxgenjs`, `thumbnail.py` (visual overview).
- **Features:** Enforces strict visual QA (checking for overlapping elements, text overflow, low contrast) and emphasizes modern design principles (bold colors, specific typography).

### Mind Maps (`xmind`)
- **Capabilities:** Generate `.xmind` files (XMind 8 compatible) locally from text descriptions.
- **Features:** Creates valid ZIP archives containing the required XML (`content.xml`, `meta.xml`, `manifest.xml`) to seamlessly build structural mind maps.

## Prerequisites

To fully utilize all the skills in this repository, the following dependencies are typically required:
- **Python 3.x**
- **Node.js** (for `docx` and `pptxgenjs` creation)
- **LibreOffice** (running in headless mode for document conversion and formula recalculation)
- **Poppler / poppler-utils** (for PDF/PPTX to image conversion)
- **Pandoc** (for DOCX text extraction with tracked changes)
- Various Python packages (`pandas`, `openpyxl`, `pypdf`, `pdfplumber`, `reportlab`, `markitdown`)

## Structure

- `/skills/` - Contains the individual skill directories (`docx`, `pdf`, `pptx`, `xlsx`, `xmind-creator`, etc.). Each directory contains its own `SKILL.md` detailing usage instructions, best practices, and dependencies.
- `/scripts/` - Auxiliary Python scripts to handle document unpacking/packing XML, automated QA, formula recalculation, and headless LibreOffice integrations.

---

# AI Office Skill (Tiếng Việt)

Một bộ công cụ (skills) toàn diện dành cho AI Agent, được thiết kế để tạo, đọc, chỉnh sửa, phân tích và thao tác với các định dạng tài liệu văn phòng khác nhau. Những kỹ năng này cho phép nền tảng AI xử lý các quy trình làm việc phức tạp đối với tài liệu trên nhiều loại tệp phổ biến trong khi vẫn duy trì các tiêu chuẩn chuyên nghiệp cao cấp.

## Các loại tài liệu được hỗ trợ

Kho lưu trữ này chứa các kỹ năng chuyên dụng cho các định dạng tệp sau:

### Tài liệu Word (`docx`)
- **Khả năng:** Tạo tài liệu chuyên nghiệp mới, đọc/phân tích nội dung (bao gồm cả các thay đổi được theo dõi và XML), chỉnh sửa tài liệu hiện có, tạo mục lục và thêm tiêu đề đầu trang/chân trang.
- **Công cụ chính:** `docx-js` (qua Node.js), `pandoc`, LibreOffice (chuyển đổi).
- **Tính năng:** Hỗ trợ định cỡ trang chính xác (US Letter/A4), kiểu chữ chuyên nghiệp, bố cục nhiều cột và chỉnh sửa trực tiếp XML có theo dõi thay đổi (tracked changes).

### Bảng tính (`xlsx`)
- **Khả năng:** Đọc, chỉnh sửa, phân tích và tạo tệp `.xlsx`, `.xlsm`, `.csv` và `.tsv`.
- **Công cụ chính:** `pandas` (để phân tích dữ liệu), `openpyxl` (để định dạng/công thức), LibreOffice (để tính toán lại công thức).
- **Tính năng:** Tuân thủ nghiêm ngặt các tiêu chuẩn mô hình hóa tài chính, mã hóa màu sắc, tạo công thức động (không dùng các phép tính hardcode) và các tập lệnh tích hợp sẵn để xác minh không có lỗi công thức (như `#REF!`, `#DIV/0!`, v.v.).

### Tài liệu PDF (`pdf`)
- **Khả năng:** Đọc văn bản/bảng biểu, hợp nhất/tách PDF, xoay trang, thêm hình mờ (watermark), trích xuất hình ảnh, thực hiện OCR trên các tệp PDF được scan và tạo tệp PDF mới.
- **Công cụ chính:** `pypdf`, `pdfplumber`, `reportlab`, `qpdf`, `pdftoppm`, `pytesseract`.
- **Tính năng:** Bảo vệ bố cục mạnh mẽ, trích xuất bảng, điền biểu mẫu, cũng như bảo vệ/mã hóa tài liệu.

### Bản trình bày PowerPoint (`pptx`)
- **Khả năng:** Tạo bản thuyết trình từ đầu, chỉnh sửa các trang trình bày hiện có, trích xuất văn bản và áp dụng các mẫu (templates) có sẵn.
- **Công cụ chính:** `markitdown` (trích xuất văn bản), `pptxgenjs`, `thumbnail.py` (tổng quan hình ảnh).
- **Tính năng:** Áp dụng QA trực quan nghiêm ngặt (kiểm tra các phần tử chồng chéo, văn bản bị tràn, độ tương phản thấp) và nhấn mạnh các nguyên tắc thiết kế hiện đại (màu sắc đậm, kiểu chữ cụ thể).

### Bản đồ tư duy (`xmind`)
- **Khả năng:** Tạo tệp `.xmind` (tương thích XMind 8) cục bộ từ các mô tả bằng văn bản.
- **Tính năng:** Tạo một kho lưu trữ ZIP hợp lệ chứa XML cần thiết (`content.xml`, `meta.xml`, `manifest.xml`) để xây dựng liền mạch các biểu đồ bản đồ tư duy có cấu trúc.

## Điều kiện tiên quyết

Để sử dụng đầy đủ tất cả các tính năng trong kho lưu trữ này, bạn thường cần phải cài đặt các thành phần sau:
- **Python 3.x**
- **Node.js** (để quản lý tạo mới `docx` và `pptxgenjs`)
- **LibreOffice** (chạy ở chế độ không giao diện (headless) để chuyển đổi tài liệu và tính toán lại công thức)
- **Poppler / poppler-utils** (để chuyển đổi PDF/PPTX thành hình ảnh)
- **Pandoc** (để trích xuất văn bản DOCX đi kèm với nội dung theo dõi thay đổi)
- Các gói Python khác nhau (`pandas`, `openpyxl`, `pypdf`, `pdfplumber`, `reportlab`, `markitdown`)

## Cấu trúc thư mục

- `/skills/` - Chứa các thư mục theo từng kỹ năng (`docx`, `pdf`, `pptx`, `xlsx`, `xmind-creator`, v.v.). Mỗi thư mục có tệp `SKILL.md` riêng với hướng dẫn sử dụng, phương pháp thực hành tốt nhất và danh sách các thư viện phụ thuộc.
- `/scripts/` - Các kịch bản (scripts) Python phụ trợ để xử lý việc giải nén/nén XML, QA tự động, tính toán lại công thức và tích hợp với LibreOffice Headless.

