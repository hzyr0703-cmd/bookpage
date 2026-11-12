# -*- coding: utf-8 -*-
import io, os, re
BASE = os.path.dirname(os.path.abspath(__file__))
FOOT = re.compile(r'^(\[\d+\]|〔[一二三四五六七八九十百]+〕|注\s|校注)')
HEAD = re.compile(r'^第[一二三四五六七八九十○百]+回')

def load(n):
    raw = io.open(os.path.join(BASE, "ch", "ch-%d.md" % n), encoding="utf-8").read()
    lines = raw.split("\n")
    title = lines[0].lstrip("#").strip()
    ps = []
    for l in lines[1:]:
        s = l.strip()
        if not s:
            continue
        if FOOT.match(s):
            break
        if HEAD.match(s):
            continue
        ps.append(s)
    return title, ps, raw

def sents(p):
    return [t for t in re.finditer(r'[^。！？]*[。！？]?', p).group(0)] if False else [m.group(0) for m in re.finditer(r'[^。！？]*[。！？]?', p) if m.group(0)]
