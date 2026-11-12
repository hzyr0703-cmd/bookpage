import io, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
IDX = json.load(io.open(os.path.join(ROOT, "ch", "index.json"), encoding="utf-8"))
TITLES = [c["title"] for c in IDX["chapters"]]
N = len(TITLES)


def key(t):
    return re.sub(r"[ \u3000]+", " ", t).strip()


cards, by_n = [], {}
for k in range(1, 7):
    path = os.path.join(ROOT, "part-%d.json" % k)
    if not os.path.exists(path):
        print("缺 part-%d.json" % k)
        continue
    for c in json.load(io.open(path, encoding="utf-8")):
        n = int(c.get("n") or 0)
        if n in by_n:
            raise SystemExit("章号重复：n=%d 出现在 part-%d 与更早的批次" % (n, k))
        by_n[n] = c
        cards.append(c)

missing = [n for n in range(1, N + 1) if n not in by_n]
extra = [n for n in by_n if n < 1 or n > N]
if missing:
    raise SystemExit("缺 %d 条卡：%s …" % (len(missing), missing[:12]))
if extra:
    raise SystemExit("越界章号：%s" % extra[:12])

merged = []
for n in range(1, N + 1):
    c = by_n[n]
    c["n"] = n
    c.setdefault("srcTitle", TITLES[n - 1])
    merged.append(c)

base = json.load(io.open(os.path.join(ROOT, "base.json"), encoding="utf-8"))
groups = 6
size = (N + groups - 1) // groups
parts = []
for g in range(groups):
    start, end = g * size + 1, min(N, (g + 1) * size)
    if start > end:
        break
    tpl = base["parts"][g]
    parts.append({"title": tpl["title"], "gist": tpl["gist"],
                  "chapters": list(range(start, end + 1))})
base["parts"] = parts
base["chapters"] = merged

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "hongloumeng.json")
io.open(out, "w", encoding="utf-8", newline="\n").write(
    json.dumps(base, ensure_ascii=False, indent=1) + "\n")
print("merged: %d 卡 / %d 章 -> %s（%d 字节）；分卷 %d 组（每组 ≤%d 章）" % (
    len(merged), N, out, os.path.getsize(out), len(parts), size))
