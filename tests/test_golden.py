#!/usr/bin/env python3
"""A8 金标准回归：五份样例 IR 的产物哈希锁死 + 12 个组件标记齐备。

A1 只证明"同一份 IR 两次构建相同"，但没锁住"改渲染器后产物是否被无意改动"。
本文件把 demo / all-components / demo-overview / demo-reader 四份 IR 的 sha256 钉死；
任何组件改动只要改变输出字节，这里立刻红。

用法：python tests/test_golden.py            # 判定并打印
      python tests/test_golden.py --update   # 有意改版后重钉哈希
退出码：0 全过；1 有偏差。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 哈希全部从 tests/golden.sha 读取；首次或有意改版后跑 --update 重钉
DEMO_SHA = None

# 每个组件在产物 HTML 里的独有标记；用来证明"12 个组件都真出现了"
MARKERS = {
    "s1": "chain-step", "s2": "matrix", "s3": "timeline", "s4": "fold",
    "s5": "ba-col", "s6": "selector", "s7": "quote",
    "p1": "prose", "d1": "dt-node", "t1": "story", "f1": "figures", "q1": "qcard",
}

SHA_FILE = os.path.join(HERE, "golden.sha")


def build(ir: str, out: str) -> bytes:
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("PYTHON"):
            del env[k]
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-I", os.path.join(ROOT, "bookpage.py"), "build", ir, out],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit("build 失败 [%s] rc=%d\n%s%s" % (ir, proc.returncode, proc.stdout, proc.stderr))
    with open(out, "rb") as f:
        return f.read()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pins() -> dict:
    pins = {}
    if DEMO_SHA:
        pins["demo"] = DEMO_SHA
    if os.path.exists(SHA_FILE):
        for line in open(SHA_FILE, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            pins[key.strip()] = value.strip()
    return pins


def main() -> int:
    update = "--update" in sys.argv
    pins = read_pins()
    tmp = tempfile.mkdtemp(prefix="bookpage-golden-")
    results = []
    products = (
        ("demo", "demo.json", ()),
        ("all", os.path.join("tests", "all-components.json"), ()),
        ("overview", "demo-overview.json", ("frameworks", "cm-row", "rule")),
        ("reader", "demo-reader.json", ("class=\"toc\"", "class=\"chap\"", "rFilter")),
        ("zhuangzi", "demo-reader-zhuangzi.json", ("class=\"tstep\"", "逍遥")),
        ("guide", "demo-guide-chensilu.json", ("class=\"gwrap\"", "class=\"mech\"", "自测")),
    )
    for key, ir, need in products:
        html = build(ir, os.path.join(tmp, key + ".html"))
        got = sha(html)
        want = pins.get(key)
        ok = (want is None) or (got == want)
        miss = [m for m in need if m.encode("utf-8") not in html]
        results.append((key, len(html), got, want, ok and not miss))
        print("%-8s %7d bytes  sha=%s  pinned=%s  %s%s" % (
            key, len(html), got[:16], (want or "(none)")[:16], "OK" if ok else "MISMATCH",
            "" if not miss else "  缺标记 " + ",".join(miss)))
    # 组件标记齐备（两份产物合并检查）
    joined = ""
    for key, _n, _g, _w, _o in results:
        joined += open(os.path.join(tmp, key + ".html"), encoding="utf-8").read()
    missing = [k for k, m in MARKERS.items() if m not in joined]
    print("组件标记：%d/%d 命中%s" % (len(MARKERS) - len(missing), len(MARKERS),
                                   "" if not missing else "，缺 " + ",".join(missing)))
    fails = [r[0] for r in results if not r[4]] + (["markers"] if missing else [])
    if update:
        with open(SHA_FILE, "w", encoding="utf-8") as f:
            f.write("# bookpage 金标准哈希；改版后用 python tests/test_golden.py --update 重钉\n")
            for key, _n, got, _w, _o in results:
                f.write("%s=%s\n" % (key, got))
        print("已更新 %s" % SHA_FILE)
        return 0
    if fails:
        print("FAIL：%s" % ",".join(fails))
        return 1
    print("A8 golden PASS（%d 组产物、%d/%d 组件标记）" % (len(results), len(MARKERS), len(MARKERS)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
