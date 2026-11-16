import json,os,re,unicodedata,collections,sys
ESC='/home/claude/esc'
d=json.load(open('/home/claude/galo/data/galo.json'))
def k(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\.(png|webp|jpg|jpeg|jfif|svg|avif)$','',s); s=re.sub(r'\.svg$','',s)
    s=re.sub(r'(logo|escudo|oficial|_\(\d+\))','',s)
    return re.sub(r'[^a-z]','',s)
files=[f for f in os.listdir(ESC) if not f.endswith(('.psd','.ini'))]
pref={'png':0,'webp':1,'svg':2,'jpg':3,'jpeg':3,'jfif':4,'avif':5}
byk=collections.defaultdict(list)
for f in files: byk[k(f)].append(f)
for v in byk.values(): v.sort(key=lambda f:(pref.get(f.rsplit('.',1)[-1].lower(),9),len(f)))
UFN={'MG':['mg','mineiro','minas'],'RJ':['rj','rio','carioca'],'SP':['sp','paulista'],'GO':['go','goiania','goias'],'PR':['pr','paranaense'],'RN':['rn'],'PB':['pb'],'BA':['ba'],'SC':['sc'],'RS':['rs'],'CE':['ce'],'PE':['pe'],'ES':['es'],'DF':['df'],'MT':['mt'],'MS':['ms'],'AM':['am'],'PA':['pa'],'AL':['al'],'SE':['se'],'PI':['pi'],'MA':['ma'],'AC':['ac'],'TO':['to'],'AP':['ap']}
cnt=collections.Counter(); teams={}
for j in d['jogos']:
    i=j['adversario_id']; cnt[i]+=1; teams[i]=(j['adversario'],j['adversario_uf'])  # nome mais recente
names=collections.defaultdict(list)
for i,(n,u) in teams.items(): names[k(n)].append(i)
MAN=json.load(open('/home/claude/galo/data/escudos_manual.json')) if os.path.exists('/home/claude/galo/data/escudos_manual.json') else {}
res={}
for i,(n,u) in teams.items():
    if i in MAN: res[i]=MAN[i]; continue
    nk=k(n); cands=[nk+s for s in UFN.get(u or '',[(u or '').lower()])]+[s+nk for s in UFN.get(u or '',[])]
    hit=next((byk[c][0] for c in cands if c in byk),None)
    if not hit and nk in byk:
        top=max(names[nk],key=lambda x:cnt[x])
        if top==i: hit=byk[nk][0]
    if hit: res[i]=hit
res={i:f for i,f in res.items() if f}
json.dump(res,open('/home/claude/galo/data/escudos_map.json','w'),ensure_ascii=False,indent=0)
mj=sum(cnt[i] for i in res); print('times',len(res),'/',len(teams),'jogos cobertos',mj,'/',sum(cnt.values()))
if len(sys.argv)>1:
    for i,c in cnt.most_common():
        if i not in res and c>=int(sys.argv[1]): print(c,i,'|',teams[i])
