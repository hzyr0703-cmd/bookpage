#!/usr/bin/env python3
"""bookpage 自检：A1–A7 七条可复跑断言。

只用标准库，不依赖浏览器、不依赖 pip。
用法：python tests/selftest.py        全部通过时退出码 0
"""

import hashlib
import json
import os
import re
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
    return "demo 7 节 / all 4 节，tab↔panel 对齐，无占位符与外部引用"


# ---------------------------------------------------------------- A7 零依赖
def a7():
    tmp = tempfile.mkdtemp(prefix="bookpage-a7-")
    dst = os.path.join(tmp, "clean.html")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    p = run(["build", DEMO, dst], isolate=True, env=env)
    assert p.returncode == 0, "干净环境退出码 %d：%s" % (p.returncode, p.stdout + p.stderr)
    assert os.path.exists(dst) and os.path.getsize(dst) > 4096, "产物缺失或过小"
    return "%d bytes，-I 且剥离 PYTHON* 变量" % os.path.getsize(dst)


def main():
    check("A1", "同输入两次构建字节一致", a1)
    check("A2", "未知 signature 被拒并指出路径", a2)
    check("A3", "缺必需键被拒并指出键名", a3)
    check("A4", "中文章节 8/8", a4)
    check("A5", "中文 token 估算不再低估 20 倍", a5)
    check("A6", "产物无占位符、tab↔panel 对齐、无外部引用", a6)
    check("A7", "干净环境零依赖直跑", a7)

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
