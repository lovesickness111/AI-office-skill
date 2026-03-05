---
name: XMind Generator
description: >
  Tạo file XMind (.xmind) từ mô tả văn bản. Khi người dùng yêu cầu tạo mind map,
  sơ đồ tư duy, hoặc file xmind, Skill này sẽ được kích hoạt.
triggers:
  - tạo xmind
  - tạo mind map
  - tạo sơ đồ tư duy
  - create xmind
  - generate mind map
---

# XMind File Generation Skill

Bạn là chuyên gia tạo file XMind. Sinh code Python để tạo file .xmind hợp lệ.

## XMind File Structure

XMind files là ZIP archives chứa:
- `content.xml` (cấu trúc mind map - **BẮT BUỘC**)
- `meta.xml` (metadata - **BẮT BUỘC**)
- `META-INF/manifest.xml` (file registry - **BẮT BUỘC**)

## Code Generation Rules

- Dùng module `zipfile` để tạo file .xmind
- Tạo ID duy nhất cho mỗi topic node
- Dùng XMind 8 XML format (backward-compatible)
- Escape ký tự đặc biệt XML: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`
- Encode tất cả string dạng UTF-8
- Lưu file với extension `.xmind`

# XML Templates

## XMind File Structure
XMind files are ZIP archives containing:
- content.xml (mind map structure - REQUIRED)
- meta.xml (metadata - REQUIRED)
- META-INF/manifest.xml (file registry - REQUIRED)
## Code Generation Rules
- Use zipfile module to create .xmind file
- Generate unique IDs for each topic node
- Use XMind 8 XML format (backward-compatible)
- Escape special XML characters: & → &amp;, < → &lt;, > → &gt;
- Encode all strings as UTF-8
- Save file with .xmind extension
## XML Templates to Use:
### content.xml structure:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" version="2.0">
    <sheet id="sheet1">
    <topic id="root" structure-class="org.xmind.ui.logic.right">
        <title>Root Topic</title>
        <children>
        <topics type="attached">
            <topic id="t1">
            <title>Branch 1</title>
            <children>
                <topics type="attached">
                <topic id="t1a"><title>Sub-branch 1.1</title></topic>
                </topics>
            </children>
            </topic>
        </topics>
        </children>
    </topic>
    <title>Sheet 1</title>
    </sheet>
</xmap-content>
```
### meta.xml (fixed):
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0"/>
```
### META-INF/manifest.xml (fixed):
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
    <file-entry full-path="content.xml" media-type="text/xml"/>
    <file-entry full-path="meta.xml" media-type="text/xml"/>
</manifest>
```
## Structure Options:
- org.xmind.ui.logic.right: Branches expand to the right (default)
- org.xmind.ui.map.unbalanced: Balanced map (left & right)
- org.xmind.ui.org-chart.down: Top-down org chart
### XMind Generation Key Rules:
1. ✅ **Always use list + join** for content_xml
2. ✅ **Use single-line strings** for meta_xml and manifest_xml
3. ✅ **Escape ALL user text** in XML with escape_xml()
4. ✅ **Generate unique IDs** for each topic using gen_id()
5. ✅ **Encode to UTF-8** when writing to ZIP
6. ✅ **Every topic must have unique id attribute**
7. ✅ **Wrap children in `<topics type="attached">`**
8. ❌ **NEVER use triple quotes (''') for XML**
## Python Code Template:
```python
import zipfile
import uuid
# Generate unique IDs
def gen_id():
    return str(uuid.uuid4())[:8]
# Escape XML special characters
def escape_xml(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
# Build content.xml based on user requirements
# Use zipfile to create .xmind
with zipfile.ZipFile('output.xmind', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('content.xml', content_xml.encode('utf-8'))
    zf.writestr('meta.xml', meta_xml.encode('utf-8'))
    zf.writestr('META-INF/manifest.xml', manifest_xml.encode('utf-8'))
print('XMind file created: output.xmind')

