# -*- coding: utf-8 -*-
import io, sys
from load6 import load
n = int(sys.argv[1]); idx = [int(x) for x in sys.argv[2:-1]]
out = sys.argv[-1]
t, ps, _ = load(n)
buf = ["== CH %d %s" % (n, t)]
for i in idx:
    buf.append("--- p%d len=%d ---" % (i, len(ps[i])))
    buf.append(ps[i])
io.open(out, "a", encoding="utf-8").write("\n".join(buf) + "\n")
print("appended", out, len(buf))
