#!/usr/bin/env python3
"""bookpage 像素基线：用本机 Edge 无头渲染三张页，按宽度各拍一张，比对 PNG 哈希。

这是唯一检查「渲染出来长什么样」的测试 —— 其余 A1–A18 都是文本层断言，
断言全绿但页面排版崩掉时，只有这里会报警。

- 找不到 Edge 就跳过（exit 0，打印 SKIP），不当失败。
- 只在本机同版本浏览器之间比较；换机器 / 换浏览器版本需要 --update 重钉。
- 截图尺寸固定（1280×1400 与 900×1400），高度固定避免长页面整页缩放差异。

用法：python tests/visual.py            比对基线
      python tests/visual.py --update   重钉基线
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "bookpage.py")
BASELINE = os.path.join(HERE, "visual", "baselines.json")
PAGES = [
    ("theme-demo", os.path.join(ROOT, "demo.json")),
    ("reader-demo", os.path.join(ROOT, "demo-reader.json")),
    ("theme-chensilu", os.path.join(ROOT, "demo-theme-chensilu.json")),
]
VIEWPORTS = [(1280, 1400), (900, 1400)]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_edge():
    """返回 Edge 可执行文件路径，找不到返回 None。"""
    env = os.environ.get("BOOKPAGE_EDGE")
    if env and os.path.exists(env):
        return env
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    which = shutil.which("msedge") or shutil.which("chromium") or shutil.which("google-chrome")
    for c in cands:
        if os.path.exists(c):
            return c
    return which


def build(ir, out):
    r = subprocess.run([sys.executable, SCRIPT, "build", ir, out],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode != 0:
        raise SystemExit("构建失败 %s：%s" % (ir, r.stderr.strip() or r.stdout.strip()))


def shoot(edge, html, png, w, h):
    r = subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--screenshot=" + png, "--window-size=%d,%d" % (w, h),
                        "file:///" + html.replace("\\", "/")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(png) or os.path.getsize(png) == 0:
        raise SystemExit("截图失败：%s" % (r.stderr.strip()[:400]))


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    update = "--update" in sys.argv
    edge = find_edge()
    if not edge:
        print("SKIP 本机找不到 Edge / Chromium，像素基线跳过")
        return 0

    tmp = tempfile.mkdtemp(prefix="bp-visual-")
    got = {}
    try:
        for name, ir in PAGES:
            html = os.path.join(tmp, name + ".html")
            build(ir, html)
            for w, h in VIEWPORTS:
                key = "%s-%dx%d" % (name, w, h)
                png = os.path.join(tmp, key + ".png")
                shoot(edge, html, png, w, h)
                got[key] = md5(png)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if update:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, indent=2, sort_keys=True)
            f.write("\n")
        print("基线已重钉：%d 张" % len(got))
        return 0

    if not os.path.exists(BASELINE):
        print("FAIL 没有基线文件，先跑 python tests/visual.py --update")
        return 1

    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

    bad = []
    for key in sorted(got):
        if key not in base:
            bad.append("%s 无基线" % key)
        elif base[key] != got[key]:
            bad.append("%s 像素变了（基线 %s / 现在 %s）" % (key, base[key][:8], got[key][:8]))
    if bad:
        print("FAIL 像素基线不一致：")
        for b in bad:
            print("  - " + b)
        return 1
    print("PASS 像素基线一致（%d 张，浏览器 %s）" % (len(got), os.path.basename(edge)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
