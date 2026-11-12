# -*- coding: utf-8 -*-
"""Build part-5.json from rec-81..100.json. All quote/text pulled verbatim from ch files."""
import io, os, re, json, glob
from common import load, sents, BASE

OUT = os.path.join(os.path.dirname(BASE), "part-5.json")


def window(paras, ref):
    p, s0, s1 = ref
    ss = sents(paras[p])
    assert 0 <= s0 < s1 <= len(ss), ("bad ref", p, s0, s1, len(ss))
    return "".join(ss[s0:s1])


def main():
    recs = []
    for path in sorted(glob.glob(os.path.join(BASE, "rec-*.json"))):
        recs.append(json.load(io.open(path, encoding="utf-8")))
    recs.sort(key=lambda r: r["n"])
    if "--partial" not in os.environ.get("BUILD5", ""):
        assert [r["n"] for r in recs] == list(range(81, 101)), [r["n"] for r in recs]

    cards = []
    for r in recs:
        n = r["n"]
        title, body, raw = load(n)
        q = window(body, r["quote"])
        texts = [window(body, t) for t in r["text"]]
        card = {
            "n": n,
            "title": title,
            "srcTitle": title,
            "role": r["role"],
            "gist": r["gist"],
            "points": r["points"],
            "quote": q,
            "quote_from": r["quote_from"],
            "text": texts,
        }
        assert len(title) <= 24, (n, "title", len(title))
        assert len(title) <= 40, (n, "srcTitle", len(title))
        assert len(r["role"]) <= 34, (n, "role", len(r["role"]), r["role"])
        assert 10 <= len(r["gist"]) <= 70, (n, "gist", len(r["gist"]))
        assert 2 <= len(r["points"]) <= 4, (n, "points")
        for p in r["points"]:
            assert len(p) <= 40, (n, "point", len(p), p)
        assert 5 <= len(q) <= 90, (n, "quote", len(q), q)
        assert q in raw, (n, "quote not substring", q)
        assert len(r["quote_from"]) <= 12, (n, "quote_from")
        assert 1 <= len(texts) <= 3, (n, "text count")
        for t in texts:
            assert 60 <= len(t) <= 400, (n, "text len", len(t), t[:30])
            assert t in raw, (n, "text not substring", t[:30])
        cards.append(card)

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cards, f, ensure_ascii=False, indent=1)
        f.write("\n")
    json.load(io.open(OUT, encoding="utf-8"))
    print("ok n=%d cards=%d bytes=%d" % (len(cards), len(cards), os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
