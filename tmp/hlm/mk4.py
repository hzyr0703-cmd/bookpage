import io, json, sys, importlib

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'tmp/hlm')


import resolve  # 按「首行回目」定位文件，tmp/hlm/ch 的文件名可能错位


def load(n):
    return io.open(resolve.resolve(n), encoding='utf-8').read()


def title_of(n):
    return load(n).split('\n')[0].lstrip('#').strip()


def build():
    import rec4
    importlib.reload(rec4)
    recs = []
    errs = []
    for r in rec4.REC:
        n = r['n']
        text = load(n)
        lines = text.split('\n')
        rec = {'n': n}
        rec['title'] = title_of(n)
        rec['role'] = r['role']
        rec['gist'] = r['gist']
        rec['points'] = r['points']
        rec['quote'] = r['quote']
        rec['quote_from'] = r['quote_from']
        paras = [lines[i] for i in r['text']]
        rec['text'] = paras
        # checks
        if '"' in rec['quote'] or '\\' in rec['quote']:
            pass
        if rec['quote'] not in text:
            errs.append('%d quote not found: %s' % (n, rec['quote'][:40]))
        if len(rec['quote']) > 90:
            errs.append('%d quote len %d' % (n, len(rec['quote'])))
        if not (10 <= len(rec['gist']) <= 70):
            errs.append('%d gist len %d' % (n, len(rec['gist'])))
        if len(rec['role']) > 34:
            errs.append('%d role len %d' % (n, len(rec['role'])))
        if len(rec['title']) > 24:
            errs.append('%d title len %d: %s' % (n, len(rec['title']), rec['title']))
        if not (2 <= len(rec['points']) <= 4):
            errs.append('%d points count %d' % (n, len(rec['points'])))
        for p in rec['points']:
            if len(p) > 40:
                errs.append('%d point len %d: %s' % (n, len(p), p))
        if not (1 <= len(paras) <= 3):
            errs.append('%d paras count %d' % (n, len(paras)))
        for i, p in zip(r['text'], paras):
            if p not in text:
                errs.append('%d line %d not substring' % (n, i))
            if not (60 <= len(p) <= 400):
                errs.append('%d line %d len %d' % (n, i, len(p)))
        if len(rec['quote_from']) > 12:
            errs.append('%d quote_from len %d' % (n, len(rec['quote_from'])))
        recs.append(rec)
    order = [61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80]
    recs.sort(key=lambda x: order.index(x['n']))
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
