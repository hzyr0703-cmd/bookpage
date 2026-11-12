import io, re, sys, json

BASE = 'tmp/hlm/ch/ch-%d.md'

def load(n):
    return io.open(BASE % n, encoding='utf-8').read()

def body_paras(n):
    lines = load(n).split('\n')
    out = []
    for i, l in enumerate(lines):
        if i < 3:
            continue
        s = l.strip()
        if not s or s.startswith('[') or s.startswith('〔'):
            continue
        out.append((i, l))
    return out

def heads(chaps, width=46):
    for n in chaps:
        t = load(n).split('\n')
        print('=== %d | %s' % (n, t[0].lstrip('# ')))
        for i, l in body_paras(n):
            print('%d|%d|%s' % (i, len(l), l[:width] + ('…' if len(l) > width else '')))
        print()

def sent_split(t):
    raw = re.split('(?<=[。！？])', t)
    out = []
    for p in raw:
        if not p:
            continue
        if out and p[0] in '”』」':
            out[-1] += p
            continue
        out.append(p)
    return out

def full(chaps):
    for n in chaps:
        print('=== %d' % n)
        for i, l in body_paras(n):
            print('[P%d] len=%d' % (i, len(l)))
            print(l)
            if len(l) <= 400:
                for j, s in enumerate(sent_split(l)):
                    if len(s) <= 95:
                        print('   S%d(%d) %s' % (j, len(s), s))
            print()

def show(start, end):
    for n in range(start, end + 1):
        t = load(n).split('\n')
        print('=== %d | %s' % (n, t[0].lstrip('# ')))
        for i, l in body_paras(n):
            print('[P%d] len=%d %s' % (i, len(l), 'BAD>400' if len(l) > 400 else ''))
            if len(l) <= 400:
                print(l)
        print()

def pick(n, idxs):
    lines = load(n).split('\n')
    for i in idxs:
        l = lines[i]
        print('[%d] len=%d' % (i, len(l)))
        print(l)
        if len(l) <= 400:
            pos = 0
            for j, s in enumerate(sent_split(l)):
                a, b = pos, pos + len(s)
                pos = b
                print('  S%d @%d-%d len=%d %s' % (j, a, b, len(s), s))
        print()

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1]
    if cmd == 'heads':
        heads([int(x) for x in sys.argv[2:]])
    elif cmd == 'full':
        full([int(x) for x in sys.argv[2:]])
    elif cmd == 'lines':
        start, end = int(sys.argv[2]), int(sys.argv[3])
        show(start, end)
    elif cmd == 'pick':
        pick(int(sys.argv[2]), [int(x) for x in sys.argv[3:]])
