# -*- coding: utf-8 -*-
import io, sys
from load6 import load
a, b, w = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
out = []
for n in range(a, b + 1):
    t, ps, _ = load(n)
    out.append("===== CH %d | %s | paras=%d bodychars=%d" % (n, t, len(ps), sum(len(p) for p in ps)))
    for i, p in enumerate(ps):
        out.append("%2d|%4d|%s" % (i, len(p), p[:w]))
io.open(sys.argv[4], "w", encoding="utf-8").write("\n".join(out))
print("wrote", sys.argv[4])
