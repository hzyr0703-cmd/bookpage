#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A9：书源提取回归（docx / epub / 纯文本 / 缺依赖时的报错）。

全部夹具在运行时生成，不落二进制文件；只用标准库（zipfile 造 docx 与 epub）。
"""

import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(ROOT, "bookpage.py")
TMP = os.path.join(HERE, ".tmp-extract")
PY = sys.executable

CSS = "body{}"


def run(args):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("PYTHON"):
            env.pop(k)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([PY, "-I", CLI] + args, capture_output=True, env=env, cwd=ROOT)
    out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
    return proc.returncode, out


def make_epub(path, chapters):
    """最小合法 epub：mimetype + container.xml + OPF(spine) + 每章一个 xhtml。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?><container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles></container>')
        items, refs = [], []
        for i, (title, body) in enumerate(chapters, 1):
            name = "ch%d.xhtml" % i
            zf.writestr("OEBPS/" + name,
                        '<?xml version="1.0" encoding="utf-8"?><html><head><title>%s</title>'
                        '</head><body><h2>%s</h2><p>%s</p></body></html>' % (title, title, body))
            items.append('<item id="c%d" href="%s" media-type="application/xhtml+xml"/>' % (i, name))
            refs.append('<itemref idref="c%d"/>' % i)
        zf.writestr("OEBPS/content.opf",
                    '<?xml version="1.0" encoding="utf-8"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
                    '<manifest>%s</manifest><spine>%s</spine></package>'
                    % ("".join(items), "".join(refs)))


def make_docx(path, paragraphs):
    """最小 docx：只要 word/document.xml 就能被本实现读出来。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "".join('<w:p><w:r><w:t>%s</w:t></w:r></w:p>' % p for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document '
           'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>%s</w:body></w:document>' % body)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml",
                    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="xml" ContentType="application/xml"/></Types>')
        zf.writestr("word/document.xml", doc)


def main():
    os.makedirs(TMP, exist_ok=True)
    fails = []

    epub = os.path.join(TMP, "book.epub")
    make_epub(epub, [("第一章 起", "甲" * 40), ("第二章 承", "乙" * 40), ("第三章 转", "丙" * 40)])
    rc, out = run(["extract", epub, "-o", os.path.join(TMP, "epub.txt")])
    if rc != 0:
        fails.append("epub 提取退出码 %d：%s" % (rc, out.strip()[:120]))
    else:
        txt = open(os.path.join(TMP, "epub.txt"), encoding="utf-8").read()
        for mark in ("第一章 起", "第二章 承", "第三章 转", "甲" * 20):
            if mark not in txt:
                fails.append("epub 文本缺 %r" % mark[:20])
        if "<" in txt or "body" in txt:
            fails.append("epub 文本疑似残留 HTML 标签")
        rc2, out2 = run(["chapters", os.path.join(TMP, "epub.txt")])
        if "chapters: 3" not in out2:
            fails.append("epub 章节数不对：%s" % out2.strip()[:80])

    docx = os.path.join(TMP, "book.docx")
    make_docx(docx, ["第一章 总则", "正文段落甲。", "第二章 分则", "正文段落乙。"])
    rc, out = run(["extract", docx, "-o", os.path.join(TMP, "docx.txt")])
    if rc != 0:
        fails.append("docx 提取退出码 %d：%s" % (rc, out.strip()[:120]))
    else:
        txt = open(os.path.join(TMP, "docx.txt"), encoding="utf-8").read()
        if "正文段落甲。" not in txt or "第二章 分则" not in txt:
            fails.append("docx 文本缺失段落")
        if "<w:t>" in txt:
            fails.append("docx 文本残留 XML 标签")

    plain = os.path.join(HERE, "sample-book.md")
    rc, out = run(["extract", plain, "-o", os.path.join(TMP, "md.txt")])
    if rc != 0:
        fails.append("纯文本提取失败：%s" % out.strip()[:100])
    else:
        rc2, out2 = run(["chapters", os.path.join(TMP, "md.txt")])
        if "chapters: 8" not in out2:
            fails.append("纯文本章节数不是 8：%s" % out2.strip()[:80])

    pdf = os.path.join(TMP, "fake.pdf")
    open(pdf, "wb").write(b"%PDF-1.4\n%%EOF\n")
    rc, out = run(["extract", pdf, "-o", os.path.join(TMP, "pdf.txt")])
    if rc != 2 or "pypdf" not in out:
        fails.append("pdf 缺依赖时应 rc=2 且提示 pypdf，实际 rc=%d：%s" % (rc, out.strip()[:100]))

    mobi = os.path.join(TMP, "fake.mobi")
    open(mobi, "wb").write(b"BOOKMOBI")
    rc, out = run(["extract", mobi, "-o", os.path.join(TMP, "mobi.txt")])
    if rc != 2 or "calibre" not in out:
        fails.append("mobi 应 rc=2 且提示 calibre，实际 rc=%d" % rc)

    if fails:
        for f in fails:
            print("FAIL:", f)
        print("A9 FAIL（%d 项）" % len(fails))
        return 1
    print("A9 PASS：epub/docx/纯文本提取 + 章节计数 + pdf/mobi 缺依赖报错")
    return 0


if __name__ == "__main__":
    sys.exit(main())
