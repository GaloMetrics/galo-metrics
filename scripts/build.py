"""Normaliza, aplica correções e gera a base final + relatório de qualidade."""
import json, re, sys, unicodedata, difflib
from collections import Counter, defaultdict

src, corr_path, out_path, report_path = sys.argv[1:5]
J = json.load(open(src, encoding='utf-8'))
C = json.load(open(corr_path, encoding='utf-8'))


def key(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', s)).strip()


report = []

# 1. correções manuais (fonte da verdade, editável)
for fix in C.get('jogos', []):
    for j in J:
        if j['data'] == fix['data_original'] and key(j['adversario']) == key(fix['adversario']):
            for k, v in fix['set'].items():
                j[k] = v
            j.setdefault('correcoes', []).append(fix['motivo'])
J.sort(key=lambda j: j['data'])
alias_players = {key(a): b for a, b in C.get('jogadores', {}).items()}
alias_coach = {key(a): b for a, b in C.get('tecnicos', {}).items()}
alias_comp = C.get('competicoes', {})

# 2. adversários: UF canônica = mais frequente para o nome
uf_count = defaultdict(Counter)
for j in J:
    uf_count[key(j['adversario'])][j['adversario_uf']] += 1
for j in J:
    best = uf_count[key(j['adversario'])].most_common(1)[0][0]
    if j['adversario_uf'] != best:
        report.append(f"{j['data']} {j['adversario']}: UF '{j['adversario_uf']}' trocada por '{best}'")
        j['adversario_uf'] = best
    # times homônimos: Atlético GO, América RJ etc. ficam separados pela UF
    j['adversario_id'] = key(j['adversario'] + ' ' + (j['adversario_uf'] or ''))
    j['competicao'] = alias_comp.get(j.get('competicao'), j.get('competicao'))

# 3. jogadores do Galo: chave sem acento + aliases manuais; nome exibido = grafia mais comum
def pkey(n):
    k = key(n)
    return key(alias_players.get(k, n))

spell = defaultdict(Counter)
for j in J:
    e = j.get('escalacao_galo')
    names = []
    if e:
        names += e['titulares'] + [s['entrou'] for s in e['substituicoes']]
    names += [g['jogador'] for g in j['gols'] if g['lado'] == 'galo']
    for n in names:
        spell[pkey(n)][alias_players.get(key(n), n)] += 1
display = {k: c.most_common(1)[0][0] for k, c in spell.items()}

# 4. sugestões de grafia parecida (para revisão, não aplica sozinho)
apps = Counter()
for j in J:
    e = j.get('escalacao_galo')
    if e:
        for n in set(pkey(x) for x in e['titulares'] + [s['entrou'] for s in e['substituicoes']]):
            apps[n] += 1
keys = list(apps)
for k in keys:
    if apps[k] > 2: continue
    for o in keys:
        if o == k or apps[o] <= apps[k]: continue
        if difflib.SequenceMatcher(None, k, o).ratio() >= 0.86:
            report.append(f"Grafia suspeita: '{display[k]}' ({apps[k]} jogo) parece '{display[o]}' ({apps[o]} jogos)")

# 5. datas: temporada da competição x ano; ordem do blog
for j in J:
    tc = j.get('temporada_comp')
    if tc and tc != j['data'][:4] and not j.get('correcoes'):
        report.append(f"{j['data']} {j['adversario']}: data em {j['data'][:4]} mas competição é /{tc}")

# 6. monta base final
jogadores = defaultdict(lambda: {'jogos': 0, 'titular': 0, 'gols': 0, 'gols_penalti': 0, 'primeiro': None, 'ultimo': None, 'por_comp': Counter(), 'gols_comp': Counter()})
tecnicos = defaultdict(lambda: {'jogos': 0, 'V': 0, 'E': 0, 'D': 0, 'primeiro': None, 'ultimo': None})
for j in J:
    j['temporada'] = int(j['data'][:4])
    e = j.get('escalacao_galo')
    if e:
        e['titulares'] = [display[pkey(n)] for n in e['titulares']]
        for s in e['substituicoes']:
            s['entrou'] = display[pkey(s['entrou'])]
            s['saiu'] = display.get(pkey(s['saiu']), s['saiu'])
        played = set(e['titulares']) | {s['entrou'] for s in e['substituicoes']}
        for n in played:
            p = jogadores[n]; p['jogos'] += 1; p['por_comp'][j['competicao']] += 1
            p['primeiro'] = p['primeiro'] or j['data']; p['ultimo'] = j['data']
        for n in set(e['titulares']):
            jogadores[n]['titular'] += 1
    for g in j['gols']:
        if g['lado'] == 'galo' and not (g['tipo'] and 'contra' in g['tipo']) and g['jogador'] != 'Não identificado':
            g['jogador'] = display.get(pkey(g['jogador']), g['jogador'])
            p = jogadores[g['jogador']]; p['gols'] += 1; p['gols_comp'][j['competicao']] += 1
            if g['tipo'] and 'penal' in g['tipo']: p['gols_penalti'] += 1
            p['primeiro'] = p['primeiro'] or j['data']; p['ultimo'] = p['ultimo'] if p['ultimo'] and p['ultimo'] > j['data'] else j['data']
    t = j.get('tecnico_galo')
    if t:
        t = alias_coach.get(key(t), t); j['tecnico_galo'] = t
        if j['resultado']:
            tc = tecnicos[t]; tc['jogos'] += 1; tc[j['resultado']] += 1
            tc['primeiro'] = tc['primeiro'] or j['data']; tc['ultimo'] = j['data']
    j.pop('gols_raw', None)

out = {
    'gerado_em': __import__('datetime').date.today().isoformat(),
    'fonte': 'O Canto do Galo (galopedia.blogspot.com)',
    'jogos': J,
    'jogadores': [{'nome': n, **{k: (dict(v) if isinstance(v, Counter) else v) for k, v in d.items()}} for n, d in jogadores.items()],
    'tecnicos': [{'nome': n, **d} for n, d in tecnicos.items()],
}
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
open(report_path, 'w', encoding='utf-8').write('\n'.join(report) + '\n')
print(len(J), 'jogos |', len(jogadores), 'jogadores |', len(tecnicos), 'técnicos |', len(report), 'alertas')
