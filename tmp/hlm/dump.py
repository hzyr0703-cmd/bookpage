import re, sys

BASE = "tmp/hlm/ch/ch-%02d.md"

def load(n):
    p = BASE % n
    lines = open(p, encoding="utf-8").read().split("\n")
    idx = next(j for j, l in enumerate(lines)
               if re.match(r"^\[\d+\]", l.strip()) or re.match(r"^〔[一二三四五六七八九十]+〕", l.strip()))
    return lines[:idx]

def main():
    mode = sys.argv[1]
    if mode == "skim":
        for n in range(int(sys.argv[2]), int(sys.argv[3]) + 1):
            print(f"===== CH {n} =====")
            for j, l in enumerate(load(n)):
                s = l.strip()
                if not s:
                    continue
                print(f"{j+1}|{len(s)}|{s[:45]}")
    elif mode == "full":
        n = int(sys.argv[2])
        for j in map(int, sys.argv[3:]):
            l = load(n)[j - 1].strip()
            print(f"--- {n}:{j} len={len(l)} ---")
            print(l)

main()
