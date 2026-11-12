import sys, re
p = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 60
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 400
txt = open(p, encoding='utf-8').read().split('\n')
for i, s in enumerate(txt, 1):
    s = s.strip()
    if s and lo <= len(s) <= hi:
        print(i, len(s), "")
