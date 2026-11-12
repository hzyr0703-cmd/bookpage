# -*- coding: utf-8 -*-
import io, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
CH = os.path.join(os.path.dirname(BASE), "ch")
END = "。！？…"
CLOSE = "」』”’）)]"


def load(n):
    raw = io.open(os.path.join(CH, "ch-%d.md" % n), encoding="utf-8").read()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    title = lines[0].lstrip("#").strip()
    body = []
    for l in lines[1:]:
        s = l.strip()
        if not s:
            continue
        if re.match(r"^[\[〔]", s):
            break
        body.append(s)
    return title, body, raw


def sents(p):
    out, start = [], 0
    i = 0
    n = len(p)
    while i < n:
        if p[i] in END:
            j = i + 1
            while j < n and (p[j] in CLOSE or p[j] in END):
                j += 1
            out.append(p[start:j])
            start = j
            i = j
        else:
            i += 1
    if start < n:
        out.append(p[start:])
    return out
