# -*- coding: utf-8 -*-
"""Build part-6.json from spec6/*.json + p6/ch-N.md (canonical 101-120 text)."""
import io, json, os, re, sys

SRC = 'p6'
SPEC = 'spec6'
OUT = 'part-6.json'
MARK = re.compile(r'^(\[\d+\]|〔[一二三四五六七八九十百]+〕|注\s|校注)')


def load(n):
    p = os.path.join(SRC, 'ch-%d.md' % n)
    text = io.open(p, encoding='utf-8').read()
    lines = text.split('\n')
    title = lines[0].lstrip('#').strip()
    ps = []
    for l in lines[1:]:
        s = l.strip()
        if not s:
            continue
        if MARK.match(s):
            break
        if re.match(r'^第[○〇零一二三四五六七八九十百]+回', s):
            continue
        ps.append(s)
    return title, ps, text


def sents(p):
    out, buf = [], ''
    for i, ch in enumerate(p):
        buf += ch
        if ch in '。！？':
            nxt = p[i + 1:i + 2]
            if nxt in ('”', '」', '』'):
                buf += nxt
                continue
            out.append(buf)
            buf = ''
    if buf:
        out.append(buf)
    return out


def pick(item, ps):
    """item -> exact substring of the chapter body."""
    if isinstance(item, int):
        return ps[item]
    p = ps[item['p']]
    if 'sen' in item:
        a, b = item['sen']
        return ''.join(sents(p)[a:b + 1])
    if 'cut' in item:
        a, b = item['cut']
        return p[a:b]
    if 'a' in item or 'b' in item:
        a, b = item.get('a', 0), item.get('b', len(p))
        return p[a:b]
    return p


def clean_title(t):
    t = re.sub(r'\[\d+\]', '', t)
    t = re.sub(r'〔[一二三四五六七八九十百]+〕', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def main():
    only = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    cards = []
    for f in sorted(os.listdir(SPEC)):
        if not f.endswith('.json'):
            continue
        spec = json.load(io.open(os.path.join(SPEC, f), encoding='utf-8'))
        n = spec['n']
        if only and n not in only:
            continue
        title, ps, raw = load(n)
        errors = []
        t = clean_title(title)
        if len(t) > 24:
            errors.append('title>24 (%d)' % len(t))
        role, gist = spec['role'], spec['gist']
        if len(role) > 34:
            errors.append('role>34 (%d)' % len(role))
        if not (10 <= len(gist) <= 70):
            errors.append('gist len %d' % len(gist))
        if role == gist:
            errors.append('role==gist')
        if not (2 <= len(spec['points']) <= 4):
            errors.append('points count %d' % len(spec['points']))
        for i, pt in enumerate(spec['points']):
            if len(pt) > 40:
                errors.append('point[%d]>40 (%d)' % (i, len(pt)))
        q = pick(spec['quote'], ps)
        if not (1 <= len(q) <= 90):
            errors.append('quote len %d' % len(q))
        if q not in raw:
            errors.append('quote NOT substring')
        if len(spec['quote_from']) > 12:
            errors.append('quote_from>12')
        texts = []
        for i, it in enumerate(spec['text']):
            s = pick(it, ps)
            if not (60 <= len(s) <= 400):
                errors.append('text[%d] len %d' % (i, len(s)))
            if '〔' in s or '[' in s:
                errors.append('text[%d] has footnote mark' % i)
            if s not in raw:
                errors.append('text[%d] NOT substring' % i)
            texts.append(s)
        if '〔' in q or '[' in q:
            errors.append('quote has footnote mark')
        if errors:
            print('FAIL %d: %s' % (n, '; '.join(errors)))
            for e in errors:
                print('   ', e)
        cards.append({'n': n, 'title': t, 'role': role, 'gist': gist,
                      'points': spec['points'], 'quote': q,
                      'quote_from': spec['quote_from'], 'text': texts})
        if errors:
            print('  q=%r\n  t0=%r' % (q, texts[0] if texts else ''))
    cards.sort(key=lambda c: c['n'])
    if not only:
        data = json.dumps(cards, ensure_ascii=False, indent=1) + '\n'
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(data)
        back = json.load(io.open(OUT, encoding='utf-8'))
        print('ok cards=%d bytes=%d' % (len(back), os.path.getsize(OUT)))


main()
