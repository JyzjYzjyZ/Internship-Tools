# -*- coding: utf-8 -*-
"""PDF 批量转自包含 HTML（图片版式 + 可搜索文本层）。

用法:
    python pdf2html.py [源目录] [输出目录] [ZOOM] [JPEG质量]

默认:
    源目录    = 当前目录
    输出目录  = <源目录>_HTML（镜像子目录结构，绝不覆盖原文件）
    ZOOM      = 1.6（约 115 DPI，1.0=72DPI）
    JPEG质量  = 85

依赖: pip install pymupdf
"""
import os, io, base64, sys, time
import pymupdf

SRC = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DST = sys.argv[2] if len(sys.argv) > 2 else SRC.rstrip("\\/") + "_HTML"
ZOOM = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6
JPEG_Q = int(sys.argv[4]) if len(sys.argv) > 4 else 85


def page_html(page, idx):
    mat = pymupdf.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat)
    buf = pix.tobytes("jpeg", jpg_quality=JPEG_Q)
    b64 = base64.b64encode(buf).decode("ascii")
    text = page.get_text("text").strip()
    txt_block = ""
    if text:
        esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        txt_block = ("<details class='textlayer'><summary>本页文字（点击展开）</summary>"
                     "<pre>" + esc + "</pre></details>")
    return (f"<section class='page' id='p{idx+1}'>"
            f"<img src='data:image/jpeg;base64,{b64}' alt='第{idx+1}页'>"
            f"{txt_block}</section>")


def convert(pdf_path, html_path):
    doc = pymupdf.open(pdf_path)
    title = os.path.splitext(os.path.basename(pdf_path))[0]
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
.page {{ background:#fff; max-width:900px; margin:18px auto; padding:18px;
        box-shadow:0 2px 10px rgba(0,0,0,.4); }}
.page img {{ width:100%; height:auto; display:block; }}
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