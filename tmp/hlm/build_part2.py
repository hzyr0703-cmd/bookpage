# -*- coding: utf-8 -*-
"""Build part-2.json from spec2.json; fills title/text/quote by index from chapter files.

spec2.json: [{"n":21,"role":..,"gist":..,"points":[..],"text_idx":[i,j],"quote_idx":i,"quote_from":..}, ...]
All text is pulled verbatim from tmp/hlm/ch/ch-NN.md so substrings always verify.
"""
import io, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
CH = os.path.join(BASE, "ch")
SPECS = os.path.join(BASE, "specs")
OUT = os.path.join(BASE, "part-2.json")


def paras(n):
    raw = io.open(os.path.join(CH, "ch-%d.md" % n), encoding="utf-8").read()
    lines = raw.split("\n")
    title = lines[0].lstrip("#").strip()
    ps = [l.strip() for l in lines[1:] if l.strip()]
    return title, ps


def cut_at(p, marker):
    i = p.find(marker)
    if i < 0:
        return ""
    return p[:i + len(marker)]


def trim_quote(p):
    """Take whole paragraph if <=90 chars, else cut at last sentence end within 90."""
    if len(p) <= 90:
        return p
    cut = -1
    for m in re.finditer("。|！|？|\u201d。|\u201d！|\u201d？", p):
        if m.end() <= 90:
            cut = m.end()
    if cut > 0:
        return p[:cut]
    return ""


def main():
    spec = []
    for fn in sorted(os.listdir(SPECS), key=lambda x: int(re.sub(r"\D", "", x))):
        if fn.endswith(".json"):
            spec.extend(json.load(io.open(os.path.join(SPECS, fn), encoding="utf-8")))
    cards = []
    for s in spec:
        n = s["n"]
        title, ps = paras(n)
        texts = [ps[i] for i in s["text_idx"]]
        qp = ps[s["quote_idx"]]
        if s.get("quote_start"):
            i = qp.find(s["quote_start"])
            qp = qp[i:] if i >= 0 else ""
        q = cut_at(qp, s["quote_end"]) if s.get("quote_end") else trim_quote(qp)
        full = title
        short = full[:24]
        card = {
            "n": n,
            "title": short,
            "srcTitle": full,
            "role": s["role"],
            "gist": s["gist"],
            "points": s["points"],
            "quote": q,
            "quote_from": s["quote_from"],
            "text": texts,
        }
        # validate
        assert len(short) <= 24, (n, "title too long", len(short))
        assert len(full) <= 40, (n, "srcTitle", len(full))
        assert len(s["role"]) <= 34, (n, "role", len(s["role"]))
        assert 10 <= len(s["gist"]) <= 70, (n, "gist", len(s["gist"]))
        assert 2 <= len(s["points"]) <= 4, (n, "points")
        for p in s["points"]:
            assert len(p) <= 40, (n, "point", len(p), p)
        assert q and len(q) <= 90, (n, "quote", len(q))
        assert len(s["quote_from"]) <= 12, (n, "quote_from")
        assert 1 <= len(texts) <= 3, (n, "text count")
        raw = io.open(os.path.join(CH, "ch-%d.md" % n), encoding="utf-8").read()
        for t in texts:
            assert 60 <= len(t) <= 400, (n, "text len", len(t))
            assert t in raw, (n, "text not substring")
        assert q in raw, (n, "quote not substring")
        cards.append(card)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cards, f, ensure_ascii=False, indent=1)
        f.write("\n")
    json.load(io.open(OUT, encoding="utf-8"))
    print("ok cards=%d bytes=%d" % (len(cards), os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
