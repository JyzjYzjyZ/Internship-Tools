import os
import re
import sys
from pathlib import Path

import fitz

def clean(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_code(filename):
    m = re.match(r"^([A-Za-z]+\d+)", filename)
    return m.group(1) if m else None

def pdf_to_md(path):
    doc = fitz.open(path)
    parts = []
    for i, page in enumerate(doc):
        parts.append(f"## 第 {i + 1} 页\n")
        parts.append(clean(page.get_text()))
        parts.append("\n")
    doc.close()
    return "\n".join(parts)

def main():
    if len(sys.argv) < 3:
        print("用法: python pdf2md_all.py <pdf目录> <输出目录>")
        sys.exit(1)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    pdfs = []
    for p in sorted(src.rglob("*.pdf"), key=lambda x: x.name):
        code = extract_code(p.name)
        pdfs.append((code, p))

    results, failed = [], []
    for code, path in pdfs:
        try:
            doc = fitz.open(path)
            pages = doc.page_count
            doc.close()
            text = pdf_to_md(path)
            if code is None:
                code = path.stem
            name = os.path.basename(path)
            (out / f"{code}.md").write_text(
                f"# {code} - {name}\n\n{text}\n", encoding="utf-8"
            )
            results.append((code, pages, len(text)))
        except Exception as e:
            failed.append((code, str(e)))

    print("OK:", len(results), "FAIL:", len(failed))
    for code, pages, size in results:
        print(code, pages, "pages", size, "bytes")
    for code, err in failed:
        print("FAIL", code, err)

if __name__ == "__main__":
    main()
