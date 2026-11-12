# -*- coding: utf-8 -*-
CN = {'○': 0, '〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
      '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def to_int(s):
    if s.isdigit():
        return int(s)
    if '百' in s:
        a, b = s.split('百', 1)
        h = CN.get(a, 1) if a else 1
        rest = 0
        if b:
            if '十' in b:
                x, y = b.split('十', 1)
                rest = (CN.get(x, 1) if x else 1) * 10 + sum(CN.get(c, 0) for c in y)
            else:
                rest = sum(CN.get(c, 0) for c in b)
        return h * 100 + rest
    if '十' in s:
        x, y = s.split('十', 1)
        return (CN.get(x, 1) if x else 1) * 10 + sum(CN.get(c, 0) for c in y)
    if all(c in CN for c in s):
        v = 0
        for c in s:
            v = v * 10 + CN[c]
        return v
    return -1
