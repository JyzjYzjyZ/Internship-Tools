# -*- coding: utf-8 -*-
"""PDF 批量转「可编辑 HTML」（PyMuPDF + Pillow）。

输出结构（与参考实现 convert.py 完全一致）：
  - 每页一个 <div class="page" style="width:…pt;height:…pt">（A4 用 pt 定尺寸）
  - 底层 <svg> 矢量路径（表格线/色块），可无缝放大
  - 中层内嵌 base64 图片（含 smask 透明度合并）
  - 文字层 <span contenteditable="true"> 可直接编辑，@font-face 内嵌原 PDF 字体
版面与 PDF 100% 同源（由 PDF 直接解析，非位图），浏览器里字可点开即改。

用法:
    python convert_pdf.py <输入.pdf> <输出.html>
    python convert_pdf.py <输入目录> <输出根目录>     # 批量，输出镜像 <目录名>_HTML

依赖: pip install pymupdf pillow
"""
import os
import re
import sys
import base64
import hashlib
import html as _html
from io import BytesIO

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf  # 老别名兜底
from PIL import Image

MIME = {'ttf': 'font/ttf', 'otf': 'font/otf', 'cff': 'font/otf',
        'woff': 'font/woff', 'woff2': 'font/woff2', 'pfb': 'font/otf'}


def strip_subset(name):
    """字体名去子集前缀，如 'ABCDEF+SimSun' -> 'SimSun'。"""
    if not name:
        return name
    if '+' in name:
        return name.split('+', 1)[1]
    return name


def int2color(c):
    return "#%02X%02X%02X" % ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def fcolor(c, op):
    """把 PDF 0..1 浮点色转 0..255 hex，带透明度。"""
    if not c:
        return None, 1.0
    r = max(0, min(255, round(c[0] * 255)))
    g = max(0, min(255, round(c[1] * 255)))
    b = max(0, min(255, round(c[2] * 255)))
    o = 1.0 if op is None else float(op)
    return "#%02X%02X%02X" % (r, g, b), o


def collect_fonts(doc):
    """收集全文所有字体，取最完整（字节最长）那版，供 @font-face 内嵌。"""
    fonts = {}
    for pno in range(len(doc)):
        for f in doc[pno].get_fonts():
            xref = f[0]
            basefont = f[3]
            base = strip_subset(basefont)
            try:
                info = doc.extract_font(xref)
            except Exception:
                continue
            if not info or len(info) < 4 or not info[3]:
                continue
            buf = info[3]
            cur = fonts.get(base)
            if cur is None or len(buf) > len(cur[1]):
                fonts[base] = (info[1], buf)
    return fonts


def build_svg(page, w, h):
    """把页面的矢量绘图（表格线、色块、图标）转成 SVG path。"""
    draws = page.get_drawings()
    parts = []
    for d in draws:
        fill, fo = fcolor(d.get('fill'), d.get('fill_opacity'))
        stroke, so = fcolor(d.get('color'), d.get('stroke_opacity'))
        segs = []
        for it in d.get('items', []):
            t = it[0]
            if t == 're':  # rectangle
                r = it[1]
                segs.append('M %g %g H %g V %g H %g Z' % (r.x0, r.y0, r.x1, r.y1, r.x0))
            elif t == 'l':  # line
                p1, p2 = it[1], it[2]
                segs.append('M %g %g L %g %g' % (p1.x, p1.y, p2.x, p2.y))
            elif t == 'c':  # cubic bezier
                p1, p2, p3 = it[1], it[2], it[3]
                segs.append('C %g %g %g %g %g %g' % (p1.x, p1.y, p2.x, p2.y, p3.x, p3.y))
            elif t == 'qu':  # quad -> two lines (approximation kept as polyline)
                pts = it[1]
                if len(pts) == 4:
                    segs.append('M %g %g L %g %g L %g %g L %g %g Z' % (
                        pts[0].x, pts[0].y, pts[1].x, pts[1].y, pts[2].x, pts[2].y, pts[3].x, pts[3].y))
            elif t == 'o':  # ellipse -> two arcs
                r = it[1]
                cx = (r.x0 + r.x1) / 2.0
                cy = (r.y0 + r.y1) / 2.0
                rx = abs(r.x1 - r.x0) / 2.0
                ry = abs(r.y1 - r.y0) / 2.0
                if rx > 0 and ry > 0:
                    segs.append('M %g %g a %g %g 0 1 1 %g 0 a %g %g 0 1 1 %g 0 Z' % (
                        cx - rx, cy, rx, ry, 2 * rx, rx, ry, -2 * rx))
        path = ' '.join(segs)
        if not path:
            continue
        cap = {0: 'butt', 1: 'round', 2: 'square'}.get(d.get('lineCap'), 'butt')
        join = {0: 'miter', 1: 'round', 2: 'bevel'}.get(d.get('lineJoin'), 'miter')
        attrs = []
        if stroke:
            attrs.append('stroke="%s"' % stroke)
            attrs.append('stroke-width="%g"' % (d.get('width') or 1))
            if so < 1:
                attrs.append('stroke-opacity="%g"' % so)
            attrs.append('stroke-linecap="%s"' % cap)
            attrs.append('stroke-linejoin="%s"' % join)
            dash = d.get('dashes')
            if dash:
                m = re.match(r'\[([^\]]*)\]\s*([\d.]*)', dash)
                if m:
                    arr = [x for x in m.group(1).split() if x]
                    if arr:
                        attrs.append('stroke-dasharray="%s"' % ' '.join(arr))
        else:
            attrs.append('stroke="none"')
        if fill:
            attrs.append('fill="%s"' % fill)
            if fo < 1:
                attrs.append('fill-opacity="%g"' % fo)
        else:
            attrs.append('fill="none"')
        parts.append('<path d="%s" %s/>' % (path, ' '.join(attrs)))
    if not parts:
        return ''
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%g" height="%g" '
            'viewBox="0 0 %g %g" '
            'style="position:absolute;left:0;top:0;width:100%%;height:100%%">%s</svg>'
            % (w, h, w, h, ''.join(parts)))


def build_imgs(page, doc, cache):
    """内嵌页面图片；有 smask 软掩模时合并为 PNG 透明通道。"""
    infos = page.get_image_info(xrefs=True)
    out = []
    for info in infos:
        xref = info['xref']
        bbox = info['bbox']
        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
        if xref not in cache:
            try:
                d = doc.extract_image(xref)
            except Exception:
                continue
            data = d['image']
            ext = d['ext']
            smask = d.get('smask')
            if isinstance(smask, int):
                try:
                    md = doc.extract_image(smask)
                    if md and md.get('image'):
                        smask = md['image']
                except Exception:
                    smask = None
            if smask:
                try:
                    im = Image.open(BytesIO(data)).convert('RGBA')
                    mask = Image.open(BytesIO(smask)).convert('L')
                    if mask.size != im.size:
                        mask = mask.resize(im.size)
                    im.putalpha(mask)
                    buf = BytesIO()
                    im.save(buf, 'PNG')
                    data = buf.getvalue()
                    ext = 'png'
                except Exception:
                    pass
            cache[xref] = 'data:image/%s;base64,%s' % (ext, base64.b64encode(data).decode())
        wdt = abs(x1 - x0)
        hgt = abs(y1 - y0)
        out.append('<img src="%s" alt="" style="position:absolute;left:%gpt;top:%gpt;'
                   'width:%gpt;height:%gpt;"/>' % (cache[xref], x0, y0, wdt, hgt))
    return ''.join(out)


def build_text(page, fonts):
    """文字层：每个 span 可编辑（contenteditable），用 @font-face 字体名定位。"""
    data = page.get_text('dict')
    out = []
    for b in data['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                x0, y0, x1, y1 = s['bbox']
                txt = s['text']
                if not txt:
                    continue
                fam = strip_subset(s['font'])
                if fam not in fonts:
                    fam = s['font']
                sz = s['size']
                color = int2color(s['color'])
                lh = (y1 - y0) or sz
                vertical = False
                if len(txt) > 1 and (y1 - y0) > (x1 - x0) * 1.8:
                    vertical = True
                if vertical:  # 竖排文字：逐字定位
                    step = (y1 - y0) / len(txt)
                    for i, ch in enumerate(txt):
                        st = ('position:absolute;left:%gpt;top:%gpt;font-size:%gpt;color:%s;'
                              'font-family:"%s";line-height:1;white-space:pre;font-weight:400;') % (
                            x0, y0 + i * step, sz, color, fam)
                        out.append('<span contenteditable="true" style="%s">%s</span>' % (st, _html.escape(ch)))
                else:  # 横排文字：按换行分段
                    for i, seg in enumerate(txt.split('\n')):
                        st = ('position:absolute;left:%gpt;top:%gpt;font-size:%gpt;color:%s;'
                              'font-family:"%s";line-height:%gpt;white-space:pre;font-weight:400;') % (
                            x0, y0 + i * (lh if lh else sz), sz, color, fam, lh)
                        out.append('<span contenteditable="true" style="%s">%s</span>' % (st, _html.escape(seg)))
    return '\n'.join(out)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#525659; padding:32px 0; }
.page {
  position:relative;
  margin:16px auto;
  background:#fff;
  overflow:hidden;
  box-shadow:0 2px 12px rgba(0,0,0,.35);
}
.page span[contenteditable] { outline:none; }
.page span[contenteditable]:focus { background:rgba(66,133,244,.12); outline:1px dashed #4285f4; }
__FONTS__
</style>
</head>
<body>
__BODY__
</body>
</html>
"""


def convert_pdf(path, outpath):
    """单文件：PDF -> 可编辑 HTML。"""
    doc = pymupdf.open(path)
    try:
        fonts = collect_fonts(doc)
        fontcss = []
        for base, (ext, buf) in fonts.items():
            mime = MIME.get(ext, 'font/ttf')
            b64 = base64.b64encode(buf).decode()
            fontcss.append('@font-face{font-family:"%s";src:url(data:%s;base64,%s);font-display:block;}'
                           % (base, mime, b64))
        fontcss = '\n'.join(fontcss)
        imgcache = {}
        pages = []
        for p in doc:
            w = p.rect.width
            h = p.rect.height
            svg = build_svg(p, w, h)
            imgs = build_imgs(p, doc, imgcache)
            text = build_text(p, fonts)
            layers = []
            if svg:
                layers.append(svg)
            if imgs:
                layers.append('<div style="position:absolute;left:0;top:0;width:%gpt;height:%gpt">%s</div>'
                              % (w, h, imgs))
            layers.append('<div style="position:absolute;left:0;top:0;width:%gpt;height:%gpt">%s</div>'
                          % (w, h, text))
            page = '<div class="page" style="width:%gpt;height:%gpt">%s</div>' % (w, h, ''.join(layers))
            pages.append(page)
        body = '\n'.join(pages)
        html = (HTML_TEMPLATE
                .replace('__TITLE__', _html.escape(os.path.basename(outpath)))
                .replace('__FONTS__', fontcss)
                .replace('__BODY__', body))
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write(html)
    finally:
        doc.close()


def main():
    args = [a for a in sys.argv[1:] if a]
    if len(args) < 1:
        print(__doc__)
        sys.exit(0)
    src = args[0]
    dst = args[1] if len(args) > 1 else None
    if os.path.isfile(src):
        files = [src]
        single_out = None
        if dst and dst.lower().endswith('.html'):
            single_out = dst           # dst 是完整输出文件路径
            root = os.path.dirname(os.path.abspath(dst))
        else:
            root = dst or os.path.dirname(os.path.abspath(src))  # dst（或默认）是目录
    elif os.path.isdir(src):
        files = []
        for dp, _dn, fn in os.walk(src):
            for f in sorted(fn):
                if f.lower().endswith('.pdf'):
                    files.append(os.path.join(dp, f))
        root = dst or src.rstrip('\\/') + '_HTML'
    else:
        print('NOT FOUND:', src)
        sys.exit(1)

    ok, fail = [], []
    for f in files:
        if os.path.isfile(src) and single_out:
            out = single_out
        elif os.path.isfile(src):
            out = os.path.join(root, os.path.splitext(os.path.basename(f))[0] + '.html')
        else:
            rel = os.path.relpath(f, src)
            out = os.path.join(root, os.path.splitext(rel)[0] + '.html')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        try:
            convert_pdf(f, out)
            ok.append(out)
            print('OK   %s' % out)
        except Exception as e:
            fail.append((out, str(e)))
            print('FAIL %s : %s' % (out, e))
    print('\n===== done: %d ok, %d fail =====' % (len(ok), len(fail)))
    for out, e in fail:
        print('FAILED:', out, '->', e)


if __name__ == '__main__':
    main()
