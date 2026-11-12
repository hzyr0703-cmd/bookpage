import io, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
IDX = json.load(io.open(os.path.join(ROOT, "ch", "index.json"), encoding="utf-8"))
TITLES = [c["title"] for c in IDX["chapters"]]


def body(n):
    p = os.path.join(ROOT, "ch", "ch-%02d.md" % n)
    s = io.open(p, encoding="utf-8-sig").read()
    return s.split("\n", 1)[1] if "\n" in s else ""


def chk(c):
    bad = []
    n = int(c.get("n") or 0)
    if not 1 <= n <= len(TITLES):
        return ["n 越界 %r" % c.get("n")]
    t = c.get("title") or ""
    if not 1 <= len(t) <= 24:
        bad.append("title %d 字" % len(t))
    if "srcTitle" in c and len(c["srcTitle"]) > 40:
        bad.append("srcTitle %d 字" % len(c["srcTitle"]))
    if "role" in c and len(c["role"]) > 34:
        bad.append("role %d 字" % len(c["role"]))
    g = c.get("gist") or ""
    if not 10 <= len(g) <= 70:
        bad.append("gist %d 字" % len(g))
    pts = c.get("points") or []
    if not 2 <= len(pts) <= 4:
        bad.append("points %d 条" % len(pts))
    for p in pts:
        if not 1 <= len(p) <= 40:
            bad.append("point %d 字" % len(p))
    q = c.get("quote") or ""
    if len(q) > 90:
        bad.append("quote %d 字" % len(q))
    if len(c.get("quote_from") or "") > 12:
        bad.append("quote_from %d 字" % len(c.get("quote_from")))
    tx = c.get("text") or []
    if not 1 <= len(tx) <= 4:
        bad.append("text %d 段" % len(tx))
    src = body(n)
    key = re.sub(r"[ \u3000]+", "", src)
    for i, p in enumerate(tx):
        if not 1 <= len(p) <= 400:
            bad.append("text[%d] %d 字" % (i, len(p)))
        if re.sub(r"[ \u3000]+", "", p) not in key:
            bad.append("text[%d] 不在原文" % i)
    if q and re.sub(r"[ \u3000]+", "", q) not in key:
        bad.append("quote 不在原文")
    return bad


tot = problems = 0
for k in range(1, 7):
    f = os.path.join(ROOT, "part-%d.json" % k)
    if not os.path.exists(f):
        print("part-%d 未出" % k)
        continue
    data = json.load(io.open(f, encoding="utf-8"))
    bad_ns = []
    for c in data:
        b = chk(c)
        tot += 1
        if b:
            problems += 1
            bad_ns.append("%s:%s" % (c.get("n"), ",".join(b)))
    ns = sorted(int(c["n"]) for c in data)
    gaps = [n for n in range(min(ns), max(ns) + 1) if n not in ns] if ns else []
    print("part-%d  %d 条  n=%s..%s  问题 %d  缺号 %s" % (
        k, len(data), ns[0] if ns else "?", ns[-1] if ns else "?", len(bad_ns), gaps[:8] or "无"))
    for s in bad_ns[:6]:
        print("    " + s)
print("合计 %d 条，问题 %d" % (tot, problems))
