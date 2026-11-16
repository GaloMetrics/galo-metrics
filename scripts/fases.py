# fases.py: marca as finais do Campeonato Mineiro (lista de títulos e vices em data/finais_mineiro.json)
# uso: python3 fases.py data/galo.json data/finais_mineiro.json
import json, sys, re
from datetime import date
from collections import defaultdict
GJ, FM = sys.argv[1], sys.argv[2]
G = json.load(open(GJ, encoding='utf-8')); J = G['jogos']; L = json.load(open(FM, encoding='utf-8'))
def ed(j):
    m = re.search(r'Mineiro/(\d{4})', j.get('competicao_raw') or '')
    return int(m.group(1)) if m else j['temporada']
def eh_final(f):
    f = (f or '').lower()
    return bool(re.search(r'final|finais|decis', f)) and not re.search(r'semi|quarta|oitava|turno', f)
by = defaultdict(list)
for j in J:
    j.pop('final_mineiro', None)
    if j['grupo'] == 'Campeonato Mineiro' and j['resultado']: by[ed(j)].append(j)
out = []
for y in sorted(L['titulos'] + L['vices']):
    jogos = sorted(by.get(y, []), key=lambda j: j['data'])
    if not jogos: print('sem jogos do Mineiro', y); continue
    marc = [j for j in jogos if eh_final(j.get('fase'))]
    ult = marc[-1] if marc else jogos[-1]
    fim = date.fromisoformat(ult['data']); cauda = []
    for j in reversed(jogos[:jogos.index(ult) + 1]):
        if j['adversario_id'] != ult['adversario_id'] or (fim - date.fromisoformat(j['data'])).days > 30 or len(cauda) >= 4: break
        cauda.append(j)
    if len(marc) >= 2: cauda = []
    depois = []
    for j in jogos[jogos.index(ult) + 1:]:
        if j['adversario_id'] != ult['adversario_id'] or (date.fromisoformat(j['data']) - fim).days > 30: break
        depois.append(j)
    fin = sorted({j['id']: j for j in marc + cauda + [ult] + depois}.values(), key=lambda j: j['data'])
    tit = y in L['titulos']
    for j in fin: j['final_mineiro'] = y
    out.append({'ano': y, 'titulo': tit, 'adversario': ult['adversario'], 'adversario_id': ult['adversario_id'], 'ids': [j['id'] for j in fin]})
G['finais_mineiro'] = out
# Finais de outras competições (lista fixa em data/finais_outras.json)
import os
FO = os.path.join(os.path.dirname(FM), 'finais_outras.json')
B = {j['id']: j for j in J}
for j in J: j.pop('final_outra', None)
outras = []
if os.path.exists(FO):
    for x in json.load(open(FO, encoding='utf-8')):
        js = [B[i] for i in x['ids'] if i in B]
        if not x.get('sem_final'):
            for j in js: j['final_outra'] = f"{x['comp']} {x['ano']}"
        adv = js[-1] if js and not x.get('sem_final') else None
        outras.append({**x, 'ids': [j['id'] for j in js], 'adversario': adv['adversario'] if adv else '', 'adversario_id': adv['adversario_id'] if adv else ''})
G['finais_outras'] = outras
print('outras finais:', len(outras))
json.dump(G, open(GJ, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('finais do Mineiro marcadas:', len(out), 'edições,', sum(len(x['ids']) for x in out), 'jogos')
