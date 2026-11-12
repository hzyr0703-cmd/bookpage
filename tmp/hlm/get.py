import sys
f=sys.argv[1]; ls=sys.argv[2]
lines=[l.rstrip('\r') for l in open('ch/'+f,encoding='utf-8').read().split('\n')]
out=[]
for spec in ls.split(','):
    a,b=(spec.split('-')+[None])[:2]
    a=int(a); b=int(b) if b else a
    for i in range(a,b+1):
        t=lines[i-1].strip()
        if t: out.append('%d(%d)| %s'%(i,len(t),t))
open('sel.txt','w',encoding='utf-8').write('\n\n'.join(out))
