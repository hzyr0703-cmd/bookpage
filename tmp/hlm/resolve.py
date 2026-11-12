# -*- coding: utf-8 -*-
"""按「首行回目」定位章文件，不依赖文件名编号。
目录 tmp/hlm/ch/ 曾被重写，文件名与回目错位，故一律以首行 '# 第N回 ...' 为准。"""
import io, glob, os, re

CH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ch')

_CN = {'○': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9}


def cn2int(s):
    """把回目里的中文数字（一 / 一○ / 一一九 / 第一二○回）转 int"""
    s = s.replace('第', '').replace('回', '').strip()
    if s.isdigit():
        return int(s)
    if '百' in s:
        head, tail = s.split('百', 1)
        h = _CN.get(head, 1) if head else 1
        t = cn2int(tail) if tail else 0
        return h * 100 + t
    if '十' in s:
        head, tail = s.split('十', 1)
        h = _CN.get(head, 1) if head else 1
        t = _CN.get(tail, 0) if tail else 0
        return h * 10 + t
    val = 0
    for ch in s:
        if ch not in _CN:
            raise ValueError('无法解析回目数字: ' + s)
        val = val * 10 + _CN[ch]
    return val


def chapter_no(path):
    first = io.open(path, encoding='utf-8').readline()
    m = re.search(r'第([○零一二三四五六七八九十百0-9]+)回', first)
    return cn2int(m.group(1)) if m else None


def resolve(n):
    """返回该回对应的文件路径；同回多份时取最新修改的一份"""
    cands = []
    for p in glob.glob(os.path.join(CH_DIR, 'ch-*.md')):
        try:
            if chapter_no(p) == n:
                cands.append(p)
        except Exception:
            pass
    if not cands:
        raise SystemExit('找不到第%d回的文件' % n)
    return max(cands, key=os.path.getmtime)


def lines_of(n):
    return io.open(resolve(n), encoding='utf-8').read().split('\n')


def title_of(n):
    return lines_of(n)[0].lstrip('#').strip()


if __name__ == '__main__':
    import sys
    for a in sys.argv[1:]:
        n = int(a)
        p = resolve(n)
        print(n, os.path.basename(p), os.path.getsize(p), title_of(n))
