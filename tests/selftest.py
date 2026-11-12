#!/usr/bin/env python3
"""bookpage 自检：A1–A7 七条可复跑断言。

只用标准库，不依赖浏览器、不依赖 pip。
用法：python tests/selftest.py        全部通过时退出码 0
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "bookpage.py")
DEMO = os.path.join(ROOT, "demo.json")
ALL = os.path.join(HERE, "all-components.json")
BOOK = os.path.join(HERE, "sample-book.md")

RESULTS = []

try:  # Windows 控制台默认 GBK，先统一成 UTF-8，避免断言信息自己崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def run(args, isolate=False, env=None):
    base = dict(os.environ if env is None else env)
    base["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable] + (["-I"] if isolate else []) + [SCRIPT] + list(args)
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=base)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json_tmp(tmp, name, obj):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def check(code, title, fn):
    try:
        detail = fn()
        RESULTS.append((code, True, title, detail or ""))
    except AssertionError as exc:
        RESULTS.append((code, False, title, str(exc)))
    except Exception as exc:  # 夹具自身坏了也要如实报，不要静默跳过
        RESULTS.append((code, False, title, "%s: %s" % (type(exc).__name__, exc)))


# ---------------------------------------------------------------- A1 确定性
def a1():
    tmp = tempfile.mkdtemp(prefix="bookpage-a1-")
    out1 = os.path.join(tmp, "d1.html")
    out2 = os.path.join(tmp, "d2.html")
    p1 = run(["build", DEMO, out1])
    p2 = run(["build", DEMO, out2])
    assert p1.returncode == 0, "第一次 build 退出码 %d：%s" % (p1.returncode, p1.stdout + p1.stderr)
    assert p2.returncode == 0, "第二次 build 退出码 %d：%s" % (p2.returncode, p2.stdout + p2.stderr)
    h1, h2 = sha256(out1), sha256(out2)
    assert h1 == h2, "两次构建哈希不同\n  %s\n  %s" % (h1, h2)
    return h1[:16]


# ---------------------------------------------------------------- A2 未知签名
def a2():
    tmp = tempfile.mkdtemp(prefix="bookpage-a2-")
    ir = read_json(DEMO)
    ir["sections"][0]["signature"] = "fancy_grid"
    bad = write_json_tmp(tmp, "unknown-signature.json", ir)
    out = os.path.join(tmp, "x.html")
    p = run(["build", bad, out])
    text = p.stdout + p.stderr
    assert p.returncode == 1, "退出码应为 1，实际 %d" % p.returncode
    assert "E101" in text, "未报告 E101：%s" % text
    assert "sections[0].signature" in text, "未指出字段路径：%s" % text
    assert not os.path.exists(out), "lint 失败却写出了产物"
    return "E101 + sections[0].signature"


# ---------------------------------------------------------------- A3 缺必需键
def a3():
    tmp = tempfile.mkdtemp(prefix="bookpage-a3-")
    ir = read_json(DEMO)
    del ir["sections"][0]["data"]["steps"]
    bad = write_json_tmp(tmp, "missing-key.json", ir)
    out = os.path.join(tmp, "x.html")
    p = run(["build", bad, out])
    text = p.stdout + p.stderr
    assert p.returncode == 1, "退出码应为 1，实际 %d" % p.returncode
    assert "E102" in text, "未报告 E102：%s" % text
    assert "steps" in text, "未指出缺失键名：%s" % text
    return "E102 + steps"


# ---------------------------------------------------------------- A4 中文章节
def a4():
    p = run(["chapters", BOOK])
    assert p.returncode == 0, "chapters 退出码 %d：%s" % (p.returncode, p.stderr)
    m = re.search(r"chapters:\s*(\d+)", p.stdout)
    assert m, "输出里没有 chapters 计数：%s" % p.stdout
    n = int(m.group(1))
    assert n == 8, "期望 8 章，实际 %d" % n
    return "8/8"


# ---------------------------------------------------------------- A5 中文 token
def a5():
    text = open(BOOK, encoding="utf-8").read()
    legacy = int(len(text.split()) / 0.75)  # 上游 book-to-webpage 的算法
    p = run(["tokens", BOOK])
    assert p.returncode == 0, "tokens 退出码 %d：%s" % (p.returncode, p.stderr)
    m = re.search(r"tokens:\s*(\d+)", p.stdout)
    assert m, "输出里没有 tokens 计数：%s" % p.stdout
    est = int(m.group(1))
    chars = len(text)
    assert est >= 8 * legacy, "估算 %d 不足上游算法的 8 倍（上游 %d）" % (est, legacy)
    assert est >= 0.5 * chars, "估算 %d 低于字符数的 0.5 倍（%d 字）" % (est, chars)
    assert est <= 1.3 * chars, "估算 %d 超过字符数的 1.3 倍（%d 字）" % (est, chars)
    return "est=%d, 上游=%d, 字符=%d（约 %.0f 倍）" % (est, legacy, chars, est / max(1, legacy))


# ---------------------------------------------------------------- A6 输出自洽
def a6():
    tmp = tempfile.mkdtemp(prefix="bookpage-a6-")
    outs = []
    for name, src in (("demo", DEMO), ("all", ALL)):
        dst = os.path.join(tmp, name + ".html")
        p = run(["build", src, dst])
        assert p.returncode == 0, "%s build 退出码 %d：%s" % (name, p.returncode, p.stdout + p.stderr)
        outs.append((name, read_json(src), open(dst, encoding="utf-8").read()))
    for name, ir, html in outs:
        n = len(ir["sections"])
        assert "{{" not in html, "%s 残留占位符 {{" % name
        assert "<!-- degraded -->" not in html, "%s 意外降级" % name
        tabs = html.count('role="tab"')
        panels = html.count('role="tabpanel"')
        assert tabs == n, "%s tab 数 %d ≠ section 数 %d" % (name, tabs, n)
        assert panels == n, "%s panel 数 %d ≠ section 数 %d" % (name, panels, n)
        for sec in ir["sections"]:
            assert 'id="tab-%s"' % sec["id"] in html, "%s 缺 tab-%s" % (name, sec["id"])
            assert 'id="panel-%s"' % sec["id"] in html, "%s 缺 panel-%s" % (name, sec["id"])
            assert 'aria-controls="panel-%s"' % sec["id"] in html, "%s tab 未关联 panel" % name
        assert "http://" not in html and "https://" not in html, "%s 含外部引用，离线不可开" % name
    return "demo 7 节 / all 5 节，tab↔panel 对齐，无占位符与外部引用"


# ---------------------------------------------------------------- A7 零依赖
def a7():
    tmp = tempfile.mkdtemp(prefix="bookpage-a7-")
    dst = os.path.join(tmp, "clean.html")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    p = run(["build", DEMO, dst], isolate=True, env=env)
    assert p.returncode == 0, "干净环境退出码 %d：%s" % (p.returncode, p.stdout + p.stderr)
    assert os.path.exists(dst) and os.path.getsize(dst) > 4096, "产物缺失或过小"
    return "%d bytes，-I 且剥离 PYTHON* 变量" % os.path.getsize(dst)


def a9():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sys.executable, os.path.join(HERE, "test_extract.py")],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    assert p.returncode == 0, "A9 失败：%s" % (p.stdout + p.stderr).strip()[-200:]
    return "epub/docx/纯文本提取 + 章节计数 + pdf/mobi 缺依赖报错"



def a10():
    tmp = tempfile.mkdtemp(prefix="bookpage-a10-")
    ov = os.path.join(ROOT, "demo-overview.json")
    out1 = os.path.join(tmp, "o1.html")
    out2 = os.path.join(tmp, "o2.html")
    p0 = run(["lint", ov])
    assert p0.returncode == 0, "overview lint 退出码 %d：%s" % (p0.returncode, p0.stdout + p0.stderr)
    p1 = run(["build", ov, out1])
    p2 = run(["build", ov, out2])
    assert p1.returncode == 0 and p2.returncode == 0, "overview build 失败：%s" % (p1.stdout + p1.stderr)
    h1, h2 = sha256(out1), sha256(out2)
    assert h1 == h2, "overview 两次构建哈希不同"
    html = open(out1, encoding="utf-8").read()
    assert 'role="tab"' not in html and "panel-" not in html, "overview 不该出现 tab/panel"
    assert 'class="fw"' in html and 'class="cm-row"' in html and 'class="rule"' in html, "overview 缺区块标记"
    assert "{{" not in html and "http://" not in html, "overview 含占位符或外部引用"
    ir = read_json(ov)
    for key in ("frameworks", "chapterMap", "conceptMap", "decisionRules"):
        ir.pop(key, None)
    bad = write_json_tmp(tmp, "empty-overview.json", ir)
    p = run(["lint", bad])
    assert p.returncode == 1 and "E102" in (p.stdout + p.stderr), "空 overview 未报 E102"
    ir2 = read_json(ov)
    ir2["sections"] = []
    bad2 = write_json_tmp(tmp, "with-sections.json", ir2)
    p2b = run(["lint", bad2])
    assert p2b.returncode == 1 and "E100" in (p2b.stdout + p2b.stderr), "overview 带 sections 未报 E100"
    ir3 = read_json(ov)
    ir3["conceptMap"][0]["relation"] = "因果报应"
    bad3 = write_json_tmp(tmp, "bad-relation.json", ir3)
    p3 = run(["lint", bad3])
    assert p3.returncode == 1 and "relation" in (p3.stdout + p3.stderr), "非法 relation 未被拒"
    return "overview 4 区块，两次同哈希 %s，三条拒绝路径" % h1[:16]



def a11():
    tmp = tempfile.mkdtemp(prefix="bookpage-a11-")
    d = os.path.join(tmp, "chapters")
    p = run(["split", BOOK, "-o", d])
    assert p.returncode == 0, "split 退出码 %d：%s" % (p.returncode, p.stdout + p.stderr)
    idx = read_json(os.path.join(d, "index.json"))
    n = len(idx["chapters"])
    assert n == 8, "sample-book 应切出 8 章，实际 %d" % n
    files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
    assert len(files) == n, "ch-*.md 数 %d ≠ %d" % (len(files), n)
    for f in files:
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            assert fh.readline().startswith("# "), "%s 缺标题行" % f
    rd = os.path.join(ROOT, "demo-reader.json")
    p0 = run(["lint", rd])
    assert p0.returncode == 0, "reader lint 退出码 %d：%s" % (p0.returncode, p0.stdout + p0.stderr)
    o1, o2 = os.path.join(tmp, "r1.html"), os.path.join(tmp, "r2.html")
    for dst in (o1, o2):
        q = run(["build", rd, dst])
        assert q.returncode == 0, "reader build 失败：%s" % (q.stdout + q.stderr)
    h1, h2 = sha256(o1), sha256(o2)
    assert h1 == h2, "reader 两次构建哈希不同"
    html = open(o1, encoding="utf-8").read()
    assert 'role="tab"' not in html, "reader 不该出现 tab"
    assert 'class="toc"' in html and 'id="rFilter"' in html, "reader 缺目录或搜索框"
    ir = read_json(rd)
    assert html.count('class="chap"') == len(ir["chapters"]), "章节卡数量与 IR 不符"
    assert 'class="digest"' in html and html.count('class="dg"') == len(ir["digest"]), "缺全书摘要块或条数不符"
    ref_spans = html.count('<span class="ref">')
    ref_expect = sum(1 for t in ir["digest"] if isinstance(t, dict) and t.get("refs"))
    assert ref_spans == ref_expect, "digest 章号引用块 %d 个，期望 %d" % (ref_spans, ref_expect)
    ids = set(re.findall(r'id="ch-(\d+)"', html))
    dangling = [n for n in re.findall(r'href="#ch-(\d+)"', html) if n not in ids]
    assert not dangling, "章号引用指向不存在的章：%s" % dangling
    assert 'class="cc"' in html and html.count('class="cc"') == len(ir["concepts"]), "缺关键概念块或组数不符"
    assert "{{" not in html and "http://" not in html, "reader 含占位符或外部引用"
    plain = os.path.join(tmp, "no-heading.txt")
    with open(plain, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n\n".join("第 %d 段内容，没有章节标题，仅作为等分切分的填充文字。" % i for i in range(1, 320)))
    p3 = run(["split", plain, "-o", os.path.join(tmp, "eq")])
    assert p3.returncode == 0, "无标题书 split 失败：%s" % (p3.stdout + p3.stderr)
    eq = read_json(os.path.join(tmp, "eq", "index.json"))
    assert eq["method"] == "equal-split" and len(eq["chapters"]) >= 2, "无标题书未走等分切"
    return "split 8 章 / reader 两次同哈希 %s / 无 tab / 等分回退" % h1[:16]


def a12():
    """A12：论证主线（thread）与已读标记两块必须与 IR 对齐，且不破坏确定性。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a12-")
    rd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo-reader.json")
    ir = read_json(rd)
    assert ir.get("thread"), "demo-reader.json 缺 thread 块"
    o1 = os.path.join(tmp, "r1.html")
    o2 = os.path.join(tmp, "r2.html")
    run(["build", rd, o1])
    run(["build", rd, o2])
    assert sha256(o1) == sha256(o2), "thread 接入后两次构建哈希不同"
    html = open(o1, encoding="utf-8").read()
    assert 'class="thread"' in html, "缺论证主线区块"
    assert html.count('class="tstep"') == len(ir["thread"]), "主线环数与 IR 不符"
    assert html.count('class="mark"') == len(ir["chapters"]), "已读按钮数与章节数不符"
    assert 'id="rRead"' in html, "缺已读计数器"
    assert "localStorage" in html, "已读状态没有落到 localStorage（刷新即丢）"
    assert "=>" not in html.split("<script>")[-1], "内联 JS 出现箭头函数"
    ids = set(re.findall(r'id="ch-(\d+)"', html))
    dangling = [n for n in re.findall(r'class="tref".{0,400}?href="#ch-(\d+)"', html, re.S) if n not in ids]
    assert not dangling, "主线引用指向不存在的章：%s" % dangling
    return "主线 %d 环 / 已读按钮 %d 个 / 同哈希 %s" % (
        len(ir["thread"]), len(ir["chapters"]), sha256(o1)[:16])


def a13():
    """A13：verify 必须证明引文与原文片段真的来自书稿，且错误指到具体字段。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a13-")
    src = os.path.join(tmp, "book.txt")
    lines = [
        "第一章 起點",
        "　　阿甲出生在河邊的小鎮，家裡只有一間瓦房。他每天走三里路去學堂，路上會經過一座石橋。",
        "第二章 轉折",
        "　　那年夏天河漲水，石橋被沖斷，學堂停課半年。阿甲開始在橋邊幫人擺渡，一次能載四人。",
        "第三章 結局",
        "　　十年後他攢錢修了橋，橋上刻著他的名字。來往的人仍舊叫他擺渡的，沒人叫他修橋的。",
    ]
    with open(src, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n\n".join(lines) + "\n")
    ir = {
        "schema": "bookpage/1",
        "meta": {"book": "驗證樣本", "author": "測試", "mode": "reader", "theme": "paper"},
        "hero": {"eyebrow": "測試", "title": "三個章節", "lede": "用來證明 verify 真的在比對原文。",
                 "thesis": "引文必須落在書稿裡。"},
        "digest": [{"t": "一條足以讓 gate 通過的判斷句，長度剛好合規。", "refs": [1]}],
        "concepts": [{"name": "起點", "gist": "故事從一個小鎮的一間瓦房開始，主角叫阿甲。", "chapters": [1]},
                     {"name": "轉折", "gist": "河水沖斷石橋，學堂停課，主角改去擺渡。", "chapters": [2]}],
        "chapters": [
            {"n": 1, "title": "第一章 起點", "gist": "阿甲出生在河邊小鎮，每天走路去學堂。",
             "points": ["家裡只有一間瓦房", "上學要經過一座石橋"],
             "quote": "阿甲出生在河邊的小鎮，家裡只有一間瓦房。",
             "text": ["他每天走三里路去學堂，路上會經過一座石橋。"]},
            {"n": 2, "title": "第二章 轉折", "gist": "河水漲起來，石橋被沖斷，學堂停課半年。",
             "points": ["石橋被沖斷", "阿甲改去橋邊擺渡"],
             "quote": "那年夏天河漲水，石橋被沖斷，學堂停課半年。",
             "text": ["阿甲開始在橋邊幫人擺渡，一次能載四人。"]},
            {"n": 3, "title": "第三章 結局", "gist": "十年後阿甲修好了橋，橋上刻著他的名字。",
             "points": ["攢錢修了橋", "旁人仍舊叫他擺渡的"],
             "quote": "十年後他攢錢修了橋，橋上刻著他的名字。",
             "text": ["來往的人仍舊叫他擺渡的，沒人叫他修橋的。"]},
        ],
        "questions": [{"q": "這三段裡，哪一段最能說明「名字與稱呼」的錯位？",
                       "hint": "看第三章第二句。"},
                     {"q": "如果只能留一個細節，你留哪個？", "hint": "橋上刻著名字那句。"}],
    }
    good = write_json_tmp(tmp, "good.json", ir)
    p = run(["verify", good, "--source", src])
    assert p.returncode == 0, "正常 IR 未通过 verify：%s" % (p.stdout + p.stderr)
    assert "verify: OK" in p.stdout, "缺少 OK 汇报：%s" % p.stdout

    bad1 = json.loads(json.dumps(ir))
    bad1["chapters"][0]["quote"] = "阿甲出生在河邊的大城市，家裡有三間瓦房。"
    f1 = write_json_tmp(tmp, "bad-quote.json", bad1)
    p1 = run(["verify", f1, "--source", src])
    assert p1.returncode == 1 and "E301" in p1.stdout and "chapters[0].quote" in p1.stdout, \
        "改错的引文没被抓到：%s" % (p1.stdout + p1.stderr)

    bad2 = json.loads(json.dumps(ir))
    bad2["chapters"][1]["text"][0] = "阿甲開始在橋邊幫人做飯，一次能煮四人。"
    f2 = write_json_tmp(tmp, "bad-text.json", bad2)
    p2 = run(["verify", f2, "--source", src])
    assert p2.returncode == 1 and "E302" in p2.stdout and "chapters[1].text[0]" in p2.stdout, \
        "改错的原文片段没被抓到：%s" % (p2.stdout + p2.stderr)

    bad3 = json.loads(json.dumps(ir))
    bad3["chapters"][2]["title"] = "第三章 不存在的章"
    f3 = write_json_tmp(tmp, "bad-title.json", bad3)
    p3 = run(["verify", f3, "--source", src])
    assert p3.returncode == 1 and "E303" in p3.stdout, \
        "对不上的章节标题没被报出：%s" % (p3.stdout + p3.stderr)
    return "引文/片段/章题三类错误都能定位；9 章→3 章样本"


def a14():
    """A14：render 能判文本层；装了 pymupdf 就真渲染，没装就报缺依赖。"""
    try:
        import fitz  # noqa: F401
    except ImportError:
        p = run(["render", BOOK])
        text = p.stdout + p.stderr
        assert p.returncode == 2, "缺依赖时退出码应 2，实际 %d" % p.returncode
        assert "pymupdf" in text, "缺依赖时没提示装 pymupdf：%s" % text
        return "未装 pymupdf：只校验报错路径"
    tmp = tempfile.mkdtemp(prefix="bookpage-a14-")
    pdf = os.path.join(tmp, "sample.pdf")
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 100), "Sample page %d of the render test." % (i + 1))
    doc.save(pdf)
    doc.close()
    out = os.path.join(tmp, "pages")
    p = run(["render", pdf, "-o", out, "--pages", "1-2", "--dpi", "96"])
    text = p.stdout + p.stderr
    assert p.returncode == 0, "render 退出码 %d：%s" % (p.returncode, text)
    pngs = sorted(n for n in os.listdir(out) if n.endswith(".png"))
    assert pngs == ["p001.png", "p002.png"], "渲染页数不符：%s" % pngs
    assert "文本层：有" in p.stdout, "有文字层的 PDF 被误判：%s" % p.stdout
    return "3 页样本 → 只渲染 1-2 页，文本层判为「有」"


def a15():
    """A15：shelf 把同目录 IR 收成一页，链接可点、两次构建一致。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a15-")
    shutil.copy(DEMO, os.path.join(tmp, "demo.json"))
    out = os.path.join(tmp, "demo.html")
    build = run(["build", DEMO, out])
    assert build.returncode == 0, "构建书架样本页失败：%s" % (build.stdout + build.stderr)
    ov = os.path.join(ROOT, "demo-overview.json")
    shutil.copy(ov, os.path.join(tmp, "demo-overview.json"))
    idx1 = os.path.join(tmp, "i1.html")
    idx2 = os.path.join(tmp, "i2.html")
    p1 = run(["shelf", tmp, "-o", idx1])
    p2 = run(["shelf", tmp, "-o", idx2])
    assert p1.returncode == 0 and p2.returncode == 0, "shelf 失败：%s" % (p1.stdout + p1.stderr)
    assert sha256(idx1) == sha256(idx2), "shelf 两次输出不一致"
    html = open(idx1, encoding="utf-8").read()
    assert 'href="demo.html"' in html, "已构建的书没有指向成品的链接"
    assert "未构建" in html, "缺构建的书没有标注"
    assert "{{" not in html and "http://" not in html, "书架页含占位符或外部引用"
    assert html.count('class="card"') == 2, "书架卡数量不符：%d" % html.count('class="card"')
    return "2 本（1 已构建 / 1 未构建），两次同哈希"


def a16():
    """A16：outline 只交可验证的信号，且两次输出一致、不夹带全文。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a16-")
    o1 = os.path.join(tmp, "o1.md")
    o2 = os.path.join(tmp, "o2.md")
    p1 = run(["outline", BOOK, "-o", o1])
    p2 = run(["outline", BOOK, "-o", o2])
    assert p1.returncode == 0 and p2.returncode == 0, "outline 失败：%s" % (p1.stdout + p1.stderr)
    assert sha256(o1) == sha256(o2), "outline 两次输出不一致"
    md = open(o1, encoding="utf-8").read()
    src = open(BOOK, encoding="utf-8").read()
    assert md.count("## 第") == 8, "章节数与样书 8 章不符：%d" % md.count("## 第")
    assert "首句：" in md and "末句：" in md, "缺少首句/末句"
    assert "书内引号句" in md, "缺少引号句字段"
    assert "而不（" not in md and "子曰（" not in md, "虚词噪声又回到了输出里"
    assert len(md) < len(src) * 0.6, "候选文件没有比原文更短：%d vs %d" % (len(md), len(src))
    assert "{{" not in md and "\t" not in md, "候选文件含占位符或制表符"
    # 无引号的书也要能出结果，而不是报错
    p3 = run(["outline", os.path.join(HERE, "all-components.json")])
    assert p3.returncode in (0, 2), "非常规输入崩溃：rc=%d" % p3.returncode
    return "8 章候选，两次同哈希，长度 %d/%d" % (len(md), len(src))


def a17():
    """A17：draft 起草包只含原文片段，且两次一致、显著短于原文。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a17-")
    o1 = os.path.join(tmp, "d1.md")
    o2 = os.path.join(tmp, "d2.md")
    p1 = run(["draft", BOOK, "-o", o1])
    p2 = run(["draft", BOOK, "-o", o2])
    assert p1.returncode == 0 and p2.returncode == 0, "draft 失败：%s" % (p1.stdout + p1.stderr)
    assert sha256(o1) == sha256(o2), "draft 两次输出不一致"
    md = open(o1, encoding="utf-8").read()
    src = open(BOOK, encoding="utf-8").read()
    assert md.count("## 第") == 8, "章节数与样书 8 章不符：%d" % md.count("## 第")
    # 样书是 8 个短章，每章固定开销（标题/首末句/6 条抽样/6 条引号）占比高；
    # 真书上这个比值是 22%（庄子）～28%（阿Q），见 README。
    assert len(md) < len(src) * 0.85, "起草包没有比原文明显更短：%d vs %d" % (len(md), len(src))
    # 包里的每一句都必须能在原文里逐字找到（否则模型抄下来就会被 verify 判造假）
    norm = lambda t: re.sub(r"[ \u3000]+", " ", t).strip()
    src_norm = norm(src)
    checked = 0
    for line in md.split("\n"):
        line = line.strip()
        if line.startswith("· "):
            seg = norm(line[2:].rstrip("…"))
            assert seg and seg in src_norm, "包里的句子不是原文片段：%s" % seg
            checked += 1
    assert checked >= 20, "抽样句太少，包信息量不足：%d" % checked
    assert "{{" not in md, "起草包含占位符"
    return "8 章 / %d 句全部逐字命中原文 / 长度 %d/%d" % (checked, len(md), len(src))


def a18():
    """A18：目录空条目被丢弃、版权页不并入首章；要点字面量与证据片段必须对得上原文。"""
    tmp = tempfile.mkdtemp(prefix="bookpage-a18-")
    src = os.path.join(tmp, "book.txt")
    body = ("版权信息\n书名：测试之书\n作者：某人\nISBN 123-456\n\n"
            "第一卷\n第二卷\n第三卷\n\n"
            "第一卷\n阿尔法说，先看清再行动，这是第一条。\n\n"
            "第二卷\n贝塔记录了三次失败与两次修正，共 5 年。\n\n"
            "第三卷\n伽马认为，凡是能解释的都值得留下。\n")
    open(src, "w", encoding="utf-8", newline="\n").write(body)
    sp = run(["split", src, "-o", os.path.join(tmp, "chs")])
    assert sp.returncode == 0, "split 失败：%s" % (sp.stdout + sp.stderr)
    idx = json.load(open(os.path.join(tmp, "chs", "index.json"), encoding="utf-8"))
    assert len(idx["chapters"]) == 3, "目录空条目没被丢弃（应为 3 卷）：%d" % len(idx["chapters"])

    ir = {"schema": "bookpage/1",
          "meta": {"book": "测试之书", "author": "某人", "mode": "reader", "theme": "paper",
                   "topic": "三卷", "sources": ["夹具"]},
          "hero": {"eyebrow": "测试", "title": "三卷的结构", "lede": "这是一份用来核对验证器的夹具页面，三段正文各成一卷，卷一讲看清再行动，卷二讲失败与修正，卷三讲解释的价值与边界。", "thesis": "验证器只认原文里真有的字。"},
          "digest": [{"t": "卷一给的是行动前的自检", "refs": [1]},
                     {"t": "卷二给的是失败的账本", "refs": [2]}],
          "concepts": [{"name": "先看清", "gist": "行动之前先判断局面", "chapters": [1]},
                       {"name": "修正", "gist": "失败要记账再改", "chapters": [2]}],
          "chapters": [
            {"n": 1, "title": "第一卷", "srcTitle": "第一卷", "role": "立规矩：先看清再动手",
             "gist": "阿尔法把行动前的判断写成第一条规矩", "points": ["先看清再行动", "第一条规矩要能自检"],
             "ev": ["阿尔法说，先看清再行动，这是第一条。"],
             "quote": "阿尔法说，先看清再行动，这是第一条。", "quote_from": "第一卷",
             "text": ["阿尔法说，先看清再行动，这是第一条。"]},
            {"n": 2, "title": "第二卷", "srcTitle": "第二卷", "role": "记账：把失败写下来",
             "gist": "贝塔记了三次失败与两次修正，历时 5 年", "points": ["三次失败", "两次修正"],
             "ev": ["贝塔记录了三次失败与两次修正，共 5 年。"],
             "quote": "贝塔记录了三次失败与两次修正，共 5 年。", "quote_from": "第二卷",
             "text": ["贝塔记录了三次失败与两次修正，共 5 年。"]},
            {"n": 3, "title": "第三卷", "srcTitle": "第三卷", "role": "收束：给解释划边界",
             "gist": "伽马说能解释的才值得留下", "points": ["能解释的值得留下"],
             "ev": ["伽马认为，凡是能解释的都值得留下。"],
             "quote": "伽马认为，凡是能解释的都值得留下。", "quote_from": "第三卷",
             "text": ["伽马认为，凡是能解释的都值得留下。"]},
          ],
          "questions": [{"q": "三卷的顺序能不能换？", "hint": "看卷一与卷三的因果关系。"},
                        {"q": "你最先想改哪条规矩？", "hint": "回到卷一的第一句。"}]}
    good = write_json_tmp(tmp, "good.json", ir)
    pv = run(["verify", good, "--source", src])
    assert pv.returncode == 0 and "E30" not in pv.stdout, "正常 IR 误报：%s" % (pv.stdout + pv.stderr)

    bad = json.loads(json.dumps(ir))
    bad["chapters"][1]["points"][1] = "到 1874 年一共修正了四次"
    f = write_json_tmp(tmp, "bad-num.json", bad)
    pn = run(["verify", f, "--source", src])
    assert pn.returncode == 1 and "E304" in pn.stdout, "要点里编的数字没被抓到：%s" % (pn.stdout + pn.stderr)

    bad2 = json.loads(json.dumps(ir))
    bad2["chapters"][2]["ev"][0] = "伽马说，解释不了的就该丢掉。"
    f2 = write_json_tmp(tmp, "bad-ev.json", bad2)
    pe = run(["verify", f2, "--source", src])
    assert pe.returncode == 1 and "E305" in pe.stdout, "编造的证据片段没被抓到：%s" % (pe.stdout + pe.stderr)
    return "3 卷（目录条目已丢）/ E304 抓编数字 / E305 抓编证据"


def a19():
    """A19：像素基线 —— 三张页 × 两种宽度，渲染出来的样子不能变。"""
    r = subprocess.run([sys.executable, os.path.join(HERE, "visual.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, "像素基线不一致：%s" % out.strip()[:600]
    if "SKIP" in out:
        return "跳过（本机无 Edge）：%s" % out.strip().splitlines()[-1]
    return out.strip().splitlines()[-1]


def main():

    check("A1", "同输入两次构建字节一致", a1)
    check("A2", "未知 signature 被拒并指出路径", a2)
    check("A3", "缺必需键被拒并指出键名", a3)
    check("A4", "中文章节 8/8", a4)
    check("A5", "中文 token 估算不再低估 20 倍", a5)
    check("A6", "产物无占位符、tab↔panel 对齐、无外部引用", a6)
    check("A7", "干净环境零依赖直跑", a7)
    check("A9", "书源提取：docx/epub/纯文本 + 缺依赖报错", a9)
    check("A10", "overview 模式：4 区块渲染 + 拒绝路径", a10)
    check("A11", "reader 模式 + split 拆章", a11)
    check("A12", "论证主线 + 已读标记", a12)
    check("A13", "verify：引文/片段/章题必须对上书稿", a13)
    check("A14", "render：文本层判定 + 分页渲染", a14)
    check("A15", "shelf：同目录 IR 收成一页", a15)
    check("A16", "outline：只交可验证信号，两次一致", a16)
    check("A17", "draft：起草包只含原文片段，两次一致", a17)
    check("A18", "split 去目录空章；verify 抓编造数字与证据", a18)
    check("A19", "像素基线：三页 × 两宽度渲染不变", a19)

    bar = "-" * 56
    sys.stdout.write(bar + "\n")
    for code, ok, title, detail in RESULTS:
        sys.stdout.write("%s %s  %s\n" % ("PASS" if ok else "FAIL", code, title))
        if detail:
            sys.stdout.write("         %s\n" % detail)
    sys.stdout.write(bar + "\n")
    passed = sum(1 for r in RESULTS if r[1])
    sys.stdout.write("%d/%d PASS\n" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
