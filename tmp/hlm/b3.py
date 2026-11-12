# -*- coding: utf-8 -*-
"""Build tmp/hlm/part-3.json from specs.SPECS, verbatim checks."""
import io, json, sys, re
sys.path.insert(0, 'tmp/hlm')
import specs

OUT = 'tmp/hlm/part-3.json'


def main():
    recs, errs = [], []
    for s in specs.SPECS:
        n = s['n']
        raw = io.open('tmp/hlm/ch/' + s['file'], encoding='utf-8').read()
        body = raw.split('\n')
        src = body[0].lstrip('#').strip()
        title = src[:24].strip()
        q = s['quote']
        paras = []
        for i in s['text_lines']:
            p = body[i - 1].strip()
            paras.append(p)
            if p not in raw:
                errs.append('%d line %d not substring' % (n, i))
            if not (60 <= len(p) <= 400):
                errs.append('%d line %d len %d' % (n, i, len(p)))
        if q not in raw:
            errs.append('%d quote not substring' % n)
        if len(q) > 90:
            errs.append('%d quote len %d' % (n, len(q)))
        if len(src) > 40:
            errs.append('%d srcTitle len %d' % (n, len(src)))
        if len(s['role']) > 34:
            errs.append('%d role len %d' % (n, len(s['role'])))
        if not (10 <= len(s['gist']) <= 70):
            errs.append('%d gist len %d' % (n, len(s['gist'])))
        if not (2 <= len(s['points']) <= 4):
            errs.append('%d points count %d' % (n, len(s['points'])))
        for p in s['points']:
            if len(p) > 40:
                errs.append('%d point len %d' % (n, len(p)))
        if len(s['quote_from']) > 12:
            errs.append('%d quote_from len %d' % (n, len(s['quote_from'])))
        rec = {'n': n, 'title': title, 'srcTitle': src, 'role': s['role'], 'gist': s['gist'],
               'points': s['points'], 'quote': q, 'quote_from': s['quote_from'],
               'text': paras}
        recs.append(rec)
    if errs:
        for e in errs:
            print('ERR', e)
        sys.exit(1)
    recs.sort(key=lambda r: r['n'])
    out = json.dumps(recs, ensure_ascii=False, indent=1)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(out)
    json.load(io.open(OUT, encoding='utf-8'))
    print('OK cards=%d bytes=%d' % (len(recs), len(out.encode('utf-8'))))


if __name__ == '__main__':
    main()
