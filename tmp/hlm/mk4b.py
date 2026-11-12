# -*- coding: utf-8 -*-
"""校验并生成 tmp/hlm/part-4.json。
n = 章文件序号：text/quote 必须逐字落在 tmp/hlm/ch/ch-N.md 里。
"""
import io, json, re, sys, importlib

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'tmp/hlm')

MARK = re.compile(r'\[[0-9]+\]|〔[^〕]*〕')


def raw(n):
    return io.open('tmp/hlm/ch/ch-%d.md' % n, encoding='utf-8').read()


def clean_title(n):
    first = raw(n).split('\n')[0]
    t = first.lstrip('#').strip()
    t = MARK.sub('', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def build():
    import rec4
    importlib.reload(rec4)
    recs, errs = [], []
    for r in rec4.REC:
        n = r['n']
        rawtext = raw(n)
        lines = rawtext.split('\n')
        full = clean_title(n)
        rec = {
            'n': n,
            'title': full[:24],
            'srcTitle': full,
            'role': r['role'],
            'gist': r['gist'],
            'points': r['points'],
            'quote': r['quote'],
            'quote_from': r['quote_from'],
            'text': [lines[i] for i in r['text']],
        }
        if rec['quote'] not in rawtext:
            errs.append('%d quote not found: %s' % (n, rec['quote'][:40]))
        if len(rec['quote']) > 90:
            errs.append('%d quote len %d' % (n, len(rec['quote'])))
        if not (10 <= len(rec['gist']) <= 70):
            errs.append('%d gist len %d' % (n, len(rec['gist'])))
        if len(rec['role']) > 34:
            errs.append('%d role len %d' % (n, len(rec['role'])))
        if len(rec['title']) > 24:
            errs.append('%d title len %d' % (n, len(rec['title'])))
        if len(rec['srcTitle']) > 40:
            errs.append('%d srcTitle len %d' % (n, len(rec['srcTitle'])))
        if not (2 <= len(rec['points']) <= 4):
            errs.append('%d points count %d' % (n, len(rec['points'])))
        for p in rec['points']:
            if len(p) > 40:
                errs.append('%d point len %d: %s' % (n, len(p), p))
        if not (1 <= len(rec['text']) <= 3):
            errs.append('%d text count %d' % (n, len(rec['text'])))
        for i, p in zip(r['text'], rec['text']):
            if p not in rawtext:
                errs.append('%d line %d not substring' % (n, i))
            if not (60 <= len(p) <= 400):
                errs.append('%d line %d len %d' % (n, i, len(p)))
        if len(rec['quote_from']) > 12:
            errs.append('%d quote_from len %d' % (n, len(rec['quote_from'])))
        recs.append(rec)

    recs.sort(key=lambda x: x['n'])
    want = list(range(61, 81))
    got = [x['n'] for x in recs]
    if got != want:
        errs.append('n 覆盖不全: %s' % got)
    if errs:
        for e in errs:
            print('ERR', e)
        return None
    out = json.dumps(recs, ensure_ascii=False, indent=1)
    io.open('tmp/hlm/part-4.json', 'w', encoding='utf-8', newline='\n').write(out)
    data = json.load(io.open('tmp/hlm/part-4.json', encoding='utf-8'))
    print('OK cards=%d bytes=%d' % (len(data), len(out.encode('utf-8'))))
    return True


if __name__ == '__main__':
    build()
