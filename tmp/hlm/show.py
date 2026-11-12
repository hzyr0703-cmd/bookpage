import io,sys,re
n=int(sys.argv[1])
raw=io.open('tmp/hlm/ch/ch-%d.md'%n,encoding='utf-8').read().split('\n')
print('TITLE:',raw[0].lstrip('#').strip())
ps=[]
for l in raw[1:]:
    s=l.strip()
    if not s: continue
    if re.match(r'^[\[〔]',s): break
    ps.append(s)
print('BODY_PARAS:',len(ps))
for i,p in enumerate(ps):
    print('[%d|%d] %s'%(i,len(p),p))
