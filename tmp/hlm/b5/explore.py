# -*- coding: utf-8 -*-
import sys, io, os
from common import load, sents, BASE

n = int(sys.argv[1])
title, body, raw = load(n)
out = []
out.append("TITLE[%d]: %s" % (len(title), title))
out.append("PARAS=%d CHARS=%d" % (len(body), len(raw)))
for i, p in enumerate(body):
    ss = sents(p)
    out.append("P%d len=%d sents=%d" % (i, len(p), len(ss)))
    for j, s in enumerate(ss):
        out.append("  %d.%d[%d] %s" % (i, j, len(s), s))
path = os.path.join(BASE, "view-%d.txt" % n)
io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print("written", path, os.path.getsize(path))
