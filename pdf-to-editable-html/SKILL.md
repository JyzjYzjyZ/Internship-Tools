---
name: pdf-to-editable-html
description: >
  PDF 批量转「可编辑 HTML」（PyMuPDF + Pillow）。把 PDF 还原成文字可编辑、字体内嵌、
  矢量保留的自包含网页：每页 <div class="page"> + <svg> 矢量 + 内嵌图片 +
  <span contenteditable> 可编辑文字 + @font-face 内嵌原 PDF 字体。版面与 PDF 100% 一致，
  浏览器里点文字即可改。适用: 把产品 / 合同 / 画册等 PDF 转成可直接改文字的 HTML 再转回 PDF。
---

# PDF 转可编辑 HTML

## 适用场景

用户给出一个或多个 PDF（或含子目录的目录），要转成**可编辑 HTML**：文字能点开即改、
原 PDF 字体完整内嵌、表格线/色块以矢量保留、图片内嵌，版面与 PDF 100% 一致。
常用于：拿到 PDF 后要改数字/文字再重新出 PDF。

**与 `pdf-to-html` skill 的本质区别（别用错）**：
- `pdf-to-html`：每页渲染成一张 JPEG 位图 base64，**文字不可编辑**（仅附可搜索文本层），体积大。
- 本 skill（`pdf-to-editable-html`）：**矢量 + 可编辑文字**，字体内嵌，可直接改字。这是「可编辑 HTML」的正确形态。

## 前置条件

- Python 3.10+，`pip install pymupdf pillow`
- Windows 控制台中文可能乱码（GBK 代码页），属正常现象，文件内容不受影响

## 关键经验（每次都要遵守）

1. **输出永远独立**：单文件默认输出到源 PDF 同目录（同名 `.html`）；目录模式默认输出
   `<源目录>_HTML`，镜像子目录结构，**天然不覆盖原 PDF**。交付前跟用户确认落点。
2. **输出结构铁律**（保持与既定参考一致，用户已验收过）：
   - 每页 `<div class="page" style="width:<页宽>pt;height:<页高>pt">`（**pt 单位**，A4=595.3×841.9pt）
   - 底层 `<svg … style="position:absolute;…width:100%;height:100%">` 矢量路径
   - 图片 `<img src="data:…;base64,…">` + `position:absolute;…pt` 定位
   - 文字 `<span contenteditable="true" style="…pt…">`，**必须 contenteditable**
   - `<style>` 里 `@font-face{font-family:"<字体>";src:url(data:font/…;base64,…)}` 内嵌字体
   - body 背景 `#525659`，`.page` 白色卡片 + 阴影（与参考 HTML 完全一致）
3. **字体内嵌做去重**：同一字体在 PDF 里可能多次出现（子集不同），只取字节最长那版
   （`collect_fonts` 已处理），`strip_subset` 去掉 `ABC+` 前缀再作 font-family 名。
4. **图片透明**：PDF 图片带 `smask` 软掩模时用 Pillow 合并成 PNG 透明通道，否则透明区变黑。
5. **竖排文字**：`(y1-y0) > (x1-x0)*1.8` 判为竖排，逐字拆 span 按步进定位，避免串行。
6. **HTML 转义**：文字 `& < >` 用 `html.escape` 转义，防 `≤3岁` 这类内容破坏 DOM。
7. **渲染以 PDF 解析为唯一真相**：别去猜内容流，直接读 `get_drawings` / `get_image_info` /
   `get_text("dict")`。
8. **大目录先探规模**：转换前数一下 PDF 页数/文件数，异常多先跟用户确认。

## 核心工作流

### 1. 确认源与规模

```python
import pymupdf, os
src = r'C:\...\产品册.pdf'
d = pymupdf.open(src); print(d.page_count, '页'); d.close()
```

### 2. 转换（调用内置脚本）

```bash
# 单文件：输出同名 .html 到源所在目录
python scripts/convert_pdf.py "C:\...\C5-xxx.pdf"

# 单文件指定输出
python scripts/convert_pdf.py "C:\...\C5-xxx.pdf" "C:\...\C5-xxx.html"

# 批量：源目录下所有 PDF，镜像输出到 <源目录>_HTML
python scripts/convert_pdf.py "C:\...\职工文旅产品册\线上产品" "C:\...\输出根目录"
```

### 3. 验证（必做）

- 输出 HTML 存在；抽查头部确认 `<div class="page" style="width:…pt">`、
  `<svg`、`contenteditable="true"`、`@font-face` 都在；
- 页面数 == PDF 页数（数 `<div class="page"` 出现次数）；
- 确认输出路径与源 PDF 是两个不同位置，源文件没被动。

## 脚本

`scripts/convert_pdf.py` — 主流程：收集字体 -> 逐页（SVG 矢量层 + 图片层 + 可编辑文字层）
-> 拼自包含 HTML。命令形态见上。输出结构与参考实现完全一致。

## 常见坑速查

- `import pymupdf` 缺失/弃用 -> `pip install pymupdf`；脚本已带 `import fitz` 兜底。
- 文字在浏览器里不可编辑 -> 确认生成的是 `<span contenteditable="true">`（本 skill 形态），
  而不是 pdf-to-html 的位图覆盖层。
- 某页图片变黑块 -> 该图带 smask（透明），需 Pillow 合并；确认 `pip install pillow`。
- 字体没内嵌 -> 检查该页 `get_fonts()` 是否有真实字体数据（个别字体是内置标准字体无 TTF）。
- 中文乱码只出现在控制台 stdout，写入文件的是 UTF-8，没问题。
