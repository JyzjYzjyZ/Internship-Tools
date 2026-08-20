---
name: pdf-to-html
description: >
  批量将 PDF 转成自包含 HTML（版面图片 + 可搜索文字层），
  输出到独立的 <源目录>_HTML 镜像目录，绝不覆盖原文件。
  适用: 产品册/海报/合同等整批 PDF 转网页版、发群里预览。
---

# PDF 批量转 HTML

## 适用场景

用户给出一个目录（含子目录）的 PDF，要全部转成 HTML，且**另存、不覆盖任何原文件**。
核心思路：**PyMuPDF 渲染页面为 JPEG → base64 内嵌进 HTML**，版面与 PDF 100% 一致，
另加 `get_text("text")` 文字层（`<details>` 折叠，Ctrl+F 可搜索）。

## 前置条件

- Python 3.10+，`pip install pymupdf`（别名 `fitz` 已弃用，用 `import pymupdf`）
- Windows 控制台中文可能乱码（GBK 代码页），属正常现象，文件内容不受影响

## 关键经验（每次都要遵守）

1. **文件路径用字面量**：脚本内 SRC/DST 写死绝对路径，脚本文件本身存 UTF-8
   （`# -*- coding: utf-8 -*-`），避免命令行传参时的编码坑。
2. **输出目录永远独立**：`<源目录>_HTML` 镜像子目录结构，`.html` 与 `.pdf` 同名。
   转换前先 `os.makedirs(..., exist_ok=True)`，天然不会覆盖原文件。
3. **自包含 = 可到处发**：图片 base64 内嵌，单 HTML 无外部依赖，双击浏览器即可看。
4. **先问用户意向再定参数**：这批 PDF 是干嘛用的？
   - 屏幕浏览（默认）→ ZOOM 1.6 / JPEG 85
   - 打印 → ZOOM 3.0+ / JPEG 90
   - 体积优先（发群/发邮件）→ ZOOM 1.3 / JPEG 75
   这些参数都是默认值、可调，不是写死。
5. **默认跟随 PDF 大小**：每页图片宽度 = 页宽 × ZOOM 像素（1:1 真实尺寸），
   不针对 A4 或任何规格写死容器宽度（旧版 `max-width:900px` 已移除）；
   MAXW（默认 1600px）只在超宽页兜底，视口更小则按视口缩放。
6. **文字层必须做 HTML 转义**：`&`→`&amp;`、`<`→`&lt;`、`>`→`&gt;`，否则 PDF 里的
   `<`（如 "≤3岁"）会破坏 DOM。
7. **渲染像素是唯一真相**：页面排版、颜色、字体都以渲染图片为准，别去解析内容流。
8. **大目录先探页数**：转换前先数总页数（`doc.page_count`），219 页约 30 秒；
   页数异常多时先跟用户确认。
9. **`import pymupdf`**：`import fitz` 会有 deprecation 警告，虽然能用但别用。

## 核心工作流

### 1. 确认源目录与规模

```python
import pymupdf, os
base = r'C:\Users\xxx\Desktop\产品册'
for root, _, files in os.walk(base):
    for f in sorted(files):
        if f.lower().endswith('.pdf'):
            d = pymupdf.open(os.path.join(root, f))
            print(d.page_count, f); d.close()
```

### 2. 转换（调用封装脚本）

```bash
python scripts/pdf2html.py "C:\Users\xxx\Desktop\产品册" "C:\Users\xxx\Desktop\产品册_HTML" 1.6 85 1600
```

参数：`源目录` `输出目录` `ZOOM` `JPEG质量` `MAXW`，后四个可省略
（默认 1.6 / 85 / 1600；MAXW=0 表示不设宽度上限）。
**转换前先问用户用途**（屏幕浏览 / 打印 / 体积优先），按上面的参数表取值。

### 3. 验证（必做）

- 输出目录存在且 `*.html` 数量 == 源 PDF 数量
- 抽查 1 个 HTML：读文件头确认 `<!DOCTYPE html>`、`charset=utf-8`、标题正确
- 确认输出目录与源目录是**两个不同路径**，源目录文件数没变

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/pdf2html.py` | 主流程: 遍历目录树 → 每页渲染 JPEG base64 → 生成自包含 HTML（含文字层、页码导航、打印隐藏文字层）。与下方"完整代码"内容一致 |

## 完整代码（scripts/pdf2html.py）

```python
# -*- coding: utf-8 -*-
"""PDF 批量转自包含 HTML（图片版式 + 可搜索文本层）。

用法:
    python pdf2html.py [源目录] [输出目录] [ZOOM] [JPEG质量] [MAXW]

默认:
    源目录    = 当前目录
    输出目录  = <源目录>_HTML（镜像子目录结构，绝不覆盖原文件）
    ZOOM      = 1.6（约 115 DPI；屏幕浏览 1.3~1.6，打印 3.0+）
    JPEG质量  = 85（体积优先 75，打印 90+）
    MAXW      = 1600（页面显示宽度上限 px，0 = 不设上限）

显示尺寸跟随 PDF：每页图片宽度 = 页宽 × ZOOM 像素（1:1 真实尺寸），
不针对 A4 或任何固定纸张规格写死；MAXW 只在超宽页兜底，
视口更小时按视口缩放。

依赖: pip install pymupdf
"""
import os, base64, sys, time
import pymupdf

SRC = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DST = sys.argv[2] if len(sys.argv) > 2 else SRC.rstrip("\\/") + "_HTML"
ZOOM = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6
JPEG_Q = int(sys.argv[4]) if len(sys.argv) > 4 else 85
MAXW = int(sys.argv[5]) if len(sys.argv) > 5 else 1600


def page_html(page, idx):
    mat = pymupdf.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat)
    buf = pix.tobytes("jpeg", jpg_quality=JPEG_Q)
    b64 = base64.b64encode(buf).decode("ascii")
    wpx = pix.width
    text = page.get_text("text").strip()
    txt_block = ""
    if text:
        esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        txt_block = ("<details class='textlayer'><summary>本页文字（点击展开）</summary>"
                     "<pre>" + esc + "</pre></details>")
    return (f"<section class='page' id='p{idx+1}'>"
            f"<img src='data:image/jpeg;base64,{b64}' style='width:{wpx}px' alt='第{idx+1}页'>"
            f"{txt_block}</section>")


def convert(pdf_path, html_path):
    doc = pymupdf.open(pdf_path)
    title = os.path.splitext(os.path.basename(pdf_path))[0]
    maxw_css = f"min(100%, {MAXW}px)" if MAXW > 0 else "100%"
    pages = "\n".join(page_html(doc[i], i) for i in range(doc.page_count))
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ margin:0; background:#525659; font-family:"Microsoft YaHei",sans-serif; }}
header {{ background:#323639; color:#fff; padding:14px 20px; position:sticky; top:0; z-index:10;
        font-size:16px; display:flex; justify-content:space-between; align-items:center; }}
header a {{ color:#8ab4f8; text-decoration:none; font-size:13px; }}
.page {{ background:#fff; width:fit-content; max-width:100%; margin:18px auto; padding:18px;
        box-shadow:0 2px 10px rgba(0,0,0,.4); }}
.page img {{ max-width:{maxw_css}; height:auto; display:block; }}
.textlayer {{ margin-top:12px; font-size:12px; color:#444; border-top:1px dashed #ccc; padding-top:8px; }}
.textlayer pre {{ white-space:pre-wrap; word-break:break-all; font-family:inherit; margin:6px 0 0; }}
nav {{ background:#323639; padding:8px 20px; text-align:center; position:sticky; top:48px; z-index:9; }}
nav a {{ color:#fff; margin:0 4px; font-size:12px; text-decoration:none; }}
@media print {{ .textlayer,nav,header {{ display:none !important; }} }}
</style>
</head>
<body>
<header><span>{title}</span><a href="javascript:history.back()">返回</a></header>
<nav>{''.join(f"<a href='#p{i+1}'>{i+1}</a>" for i in range(doc.page_count))}</nav>
{pages}
</body>
</html>"""
    doc.close()
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    n = 0
    t0 = time.time()
    for root, dirs, files in os.walk(SRC):
        rel = os.path.relpath(root, SRC)
        out_dir = DST if rel == "." else os.path.join(DST, rel)
        os.makedirs(out_dir, exist_ok=True)
        for f in sorted(files):
            if not f.lower().endswith(".pdf"):
                continue
            src = os.path.join(root, f)
            dst = os.path.join(out_dir, os.path.splitext(f)[0] + ".html")
            convert(src, dst)
            n += 1
            print(f"[{n}] {os.path.relpath(dst, DST)}")
    print(f"DONE: {n} html files in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
```

## 常见坑速查

- 控制台中文乱码 → 正常，GBK 代码页显示问题，文件里是对的
- 图片糊 → ZOOM 调大（2.4 高清 / 3.5 打印）
- HTML 超大 → JPEG 质量降到 75，或 ZOOM 降到 1.3
- 页面显示偏大/偏小 → 调 ZOOM（显示尺寸 = 页宽×ZOOM，默认跟随 PDF 1:1）；MAXW 只兜底超宽页
- 页面文字搜不到 → 该页是扫描件（无文本层），`get_text` 为空属正常
- `import fitz` 报弃用警告 → 换成 `import pymupdf`