"""Galo Metrics: base mestra = tabela histórica (1 linha por jogo) + fichas do Canto do Galo (detalhe).

uso: build2.py tabela.txt jogos_raw.json correcoes.json saida.json relatorio.txt
"""
import json, re, sys, unicodedata
from collections import Counter, defaultdict
from datetime import date

TAB, FICHAS, CORR, OUT, REP = sys.argv[1:6]
ACEITOS = sys.argv[6] if len(sys.argv) > 6 else None
MESES = {m: i + 1 for i, m in enumerate('jan fev mar abr mai jun jul ago set out nov dez'.split())}
rep = []


def key(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', s)).strip()


def split_uf(n):
    m = re.match(r'^(.*)-([A-Z]{2,3})$', n.strip())
    return (m.group(1).strip(), m.group(2)) if m else (n.strip(), None)


def familia(c):
    c = c or ''
    k = key(c)
    if k.startswith('mineiro') or 'torneio inicio mineiro' in k: return 'Campeonato Mineiro'
    if 'serie b' in k: return 'Brasileiro Série B'
    if k.startswith('brasileiro'): return 'Campeonato Brasileiro'
    if 'copa do brasil' in k: return 'Copa do Brasil'
    if 'libertadores' in k: return 'Libertadores'
    if 'sul americana' in k: return 'Sul-Americana'
    if k in ('conmebol', 'mercosul') or 'recopa' in k or 'supercopa' in k and 'brasil' not in k: return 'Outras Conmebol'
    if k.startswith('amistoso'): return 'Amistoso'
    return 'Torneios e outros'


# ---------------- 1. tabela histórica ----------------
def parse_scorers(s):
    """'Alonso, Hulk, Dudu (2) e Victor Luís (contra)' -> lista de gols do Galo + nota"""
    nota = None
    for m in re.findall(r'\(([^()]{12,})\)', s):
        if not re.match(r'^contra', m):
            nota = (nota + ' ' if nota else '') + m
    s = re.sub(r'\(([^()]{12,})\)', '', s).strip()
    gols = []
    if not s: return gols, nota
    for item in re.split(r',\s*|\s+e\s+', s):
        item = item.strip().strip('-').strip()
        if not item: continue
        m = re.match(r'^(.+?)\s*\((.+?)\)\s*$', item)
        nome, extra = (m.group(1).strip(), m.group(2).strip()) if m else (item, None)
        if extra and extra.startswith('contra'):
            n = int(extra.split('-')[1]) if '-' in extra else 1
            gols += [{'jogador': nome, 'minuto': None, 'tipo': 'contra', 'lado': 'galo'}] * n
        elif extra and extra.isdigit():
            gols += [{'jogador': nome, 'minuto': None, 'tipo': None, 'lado': 'galo'} for _ in range(int(extra))]
        else:
            gols.append({'jogador': nome, 'minuto': None, 'tipo': None, 'lado': 'galo'})
    return [dict(g) for g in gols], nota


tab = []
for ln in open(TAB, encoding='utf-8'):
    c = ln.rstrip('\n').split('\t')
    if len(c) < 10: continue
    aprox = False
    if re.match(r'\d{2}/\w{3}/\d{4}$', c[1]):
        d, mo, y = c[1].split('/')
    elif re.match(r'\w{3}/\d{4}$', c[1]):  # só mês/ano
        (mo, y), d, aprox = c[1].split('/'), '01', True
    else:
        continue
    mo = mo.lower()
    dt = f'{y}-{MESES[mo]:02d}-{d}'
    gp, gc = c[5].strip(), c[7].strip()
    res = (c[10].strip().upper() if len(c) > 10 else '') or None
    res = {'V': 'V', 'E': 'E', 'D': 'D'}.get(res)
    wo = 'WO' in (gp, gc)
    if res is None and gp.isdigit() and gc.isdigit():  # linha sem a coluna de resultado
        res = 'V' if int(gp) > int(gc) else ('E' if gp == gc else 'D')
    gols, nota = parse_scorers(c[9].strip() if len(c) > 9 else '')
    adv, uf = split_uf(c[8])
    j = {'n': c[0].strip(), 'data': dt, 'temporada': int(y), 'competicao': c[2].strip(), 'mando': c[3].strip() or None,
         'adversario': adv, 'adversario_uf': uf,
         'gp': int(gp) if gp.isdigit() else None, 'gc': int(gc) if gc.isdigit() else None,
         'resultado': res, 'wo': wo, 'gols': gols, 'nota': nota, 'fonte': 'tabela', 'data_aprox': aprox}
    if j['gp'] is not None:
        falta = j['gp'] - len(gols)
        if falta > 0:
            gols += [{'jogador': 'Não identificado', 'minuto': None, 'tipo': None, 'lado': 'galo'} for _ in range(falta)]
        elif falta < 0:
            rep.append(f"{dt} x {adv}: tabela lista {len(gols)} gols para placar {j['gp']}")
    tab.append(j)
print('tabela:', len(tab), 'jogos')

# ---------------- 2. fichas (com correções) ----------------
F = json.load(open(FICHAS, encoding='utf-8'))
DESDE = min(f['data'] for f in F if f['data'] > '1930' and f.get('escalacao_galo'))
C = json.load(open(CORR, encoding='utf-8'))
for fix in C.get('jogos', []):
    for f in F:
        if f['data'] == fix['data_original'] and key(f['adversario']) == key(fix['adversario']):
            f.update(fix.get('set', {})); f.setdefault('correcoes', []).append(fix['motivo'])
            tr = fix.get('trocar_nome', {})  # nome errado só neste jogo
            if tr:
                e = f.get('escalacao_galo') or {}
                e['titulares'] = [tr.get(x, x) for x in e.get('titulares', [])]
                for sb in e.get('substituicoes', []):
                    sb['entrou'] = tr.get(sb['entrou'], sb['entrou']); sb['saiu'] = tr.get(sb['saiu'], sb['saiu'])
                for g in f.get('gols', []): g['jogador'] = tr.get(g['jogador'], g['jogador'])
alias_players = {key(a): b for a, b in C.get('jogadores', {}).items()}
alias_coach = {key(a): b for a, b in C.get('tecnicos', {}).items()}
alias_comp = C.get('competicoes', {})

def pnorm(n):
    return alias_players.get(key(n), n)

for f in F:
    f['competicao'] = alias_comp.get(f.get('competicao'), f.get('competicao'))
    if f.get('tecnico_galo'): f['tecnico_galo'] = alias_coach.get(key(f['tecnico_galo']), f['tecnico_galo'])
    e = f.get('escalacao_galo')
    if e:
        e['titulares'] = [pnorm(x) for x in e['titulares']]
        for s in e['substituicoes']: s['entrou'] = pnorm(s['entrou']); s['saiu'] = pnorm(s['saiu'])
    for g in f['gols']:
        if g['lado'] == 'galo': g['jogador'] = pnorm(g['jogador'])

# grafia mais comum por chave (para unificar Éverson/Everson, Junior/Júnior...)
spell = defaultdict(Counter)
for f in F:
    e = f.get('escalacao_galo') or {'titulares': [], 'substituicoes': []}
    for n in e['titulares'] + [s['entrou'] for s in e['substituicoes']] + [g['jogador'] for g in f['gols'] if g['lado'] == 'galo']:
        spell[key(n)][n] += 1
disp = {k: c.most_common(1)[0][0] for k, c in spell.items()}
D = lambda n: disp.get(key(n), n)
for f in F:
    e = f.get('escalacao_galo')
    if e:
        _n = [D(x) for x in e['titulares']]
        e['titulares'] = list(dict.fromkeys(_n))
        if len(_n) != len(e['titulares']): e.pop('grupos', None)
        for s in e['substituicoes']: s['entrou'] = D(s['entrou']); s['saiu'] = D(s['saiu'])
    for g in f['gols']:
        if g['lado'] == 'galo': g['jogador'] = D(g['jogador'])

# ---------------- 3. casar ficha <-> tabela ----------------
by_date = defaultdict(list)
for j in tab: by_date[j['data']].append(j)
casadas, sobras = 0, []
adv_map, comp_map = {}, Counter()
def _parecido(a, b):
    ka, kb = key(a), key(b)
    if set(ka.split()) & set(kb.split()): return True
    sa, sb = ka.replace(' ', ''), kb.replace(' ', '')
    return len(sa) >= 5 and len(sb) >= 5 and (sa.startswith(sb[:6]) or sb.startswith(sa[:6]))
def _score(f, c):
    sc = 0
    if f.get('gp') is not None and (c['gp'], c['gc']) == (f['gp'], f['gc']): sc += 2
    if _parecido(c['adversario'], f['adversario']): sc += 3
    return sc
f_by_date = defaultdict(list)
for f in F: f_by_date[f['data']].append(f)
pares, fracos, soltas = [], [], []
for d, fs in f_by_date.items():
    cs = by_date.get(d, [])
    opts = sorted(((_score(f, c), i, k) for i, f in enumerate(fs) for k, c in enumerate(cs)), reverse=True)
    fu, cu = set(), set()
    for sc, i, k in opts:
        if sc == 0 or i in fu or k in cu: continue
        fu.add(i); cu.add(k); pares.append((fs[i], cs[k]))
    for i, f in enumerate(fs):
        if i in fu: continue
        livres = [c for k, c in enumerate(cs) if k not in cu]
        # sem placar nem adversário em comum: só vale se for a única ficha e a única linha livre do dia
        (fracos if len(fs) == 1 and len(livres) == 1 else soltas).append((f, livres[0] if len(fs) == 1 and len(livres) == 1 else None))
for f, c in pares: c['ficha'] = f
from datetime import date as _d, timedelta
def _perto(f):
    d0 = _d.fromisoformat(f['data'])
    for delta in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5):
        for c in by_date.get((d0 + timedelta(days=delta)).isoformat(), []):
            if 'ficha' not in c and (c['gp'], c['gc']) == (f.get('gp'), f.get('gc')) and _parecido(c['adversario'], f['adversario']):
                rep.append(f"{f['data']} x {c['adversario']}: data da ficha difere da tabela ({c['data']}); mantida a da tabela")
                return c
    return None
resto = []
for f, c in fracos + soltas:
    t = _perto(f)
    if t is not None: t['ficha'] = f; pares.append((f, t))
    else: resto.append((f, c))
for f, c in resto:
    if c is not None and 'ficha' not in c: c['ficha'] = f; pares.append((f, c))
    else: sobras.append(f)
trocar_adv = []
for f, t in pares:
    if f.get('gp') is not None and t['gp'] is not None and (t['gp'], t['gc']) != (f['gp'], f['gc']):
        fg_ = [g for g in f['gols'] if g['lado'] == 'galo' and g['jogador'] != 'Não identificado']
        if not _parecido(t['adversario'], f['adversario']) and not t.get('wo'):  # casamento só pela data, jogo diferente: vale a ficha inteira
            trocar_adv.append((f, t, f"{t['adversario']} {t['gp']}x{t['gc']}"))
            t['gp'], t['gc'], t['resultado'] = f['gp'], f['gc'], f['resultado']
        elif len(fg_) == f['gp'] and not t.get('wo'):  # ficha traz os gols que fecham o placar: vale a ficha
            rep.append(f"{f['data']} x {t['adversario']}: placar da tabela {t['gp']}x{t['gc']} trocado pelo da ficha {f['gp']}x{f['gc']}")
            t['gp'], t['gc'], t['resultado'] = f['gp'], f['gc'], f['resultado']
        else:
            rep.append(f"{f['data']} x {t['adversario']}: placar do cabeçalho da ficha ({f["gp"]}x{f["gc"]}) não bate com os gols listados; mantida a tabela ({t["gp"]}x{t["gc"]})")
    casadas += 1
    if not any(x[1] is t for x in trocar_adv): adv_map[(key(f['adversario']), f['adversario_uf'])] = (t['adversario'], t['adversario_uf'])
    comp_map[(f.get('competicao'), t['competicao'])] += 1
for f, t, antes in trocar_adv:
    t['adversario'], t['adversario_uf'] = adv_map.get((key(f['adversario']), f['adversario_uf']), (f['adversario'], f['adversario_uf']))
    t['mando'] = 'C' if f['galo_mandante'] else 'F'
    rep.append(f"{f['data']}: tabela dizia {antes}, ficha do mesmo dia é x {t['adversario']} {t['gp']}x{t['gc']}; vale a ficha")
print('fichas casadas:', casadas, '| fichas sem linha na tabela:', len(sobras))

# competição da ficha -> nome da tabela (o mais frequente)
comp_tr = {}
for (fc, tc), n in comp_map.most_common():
    comp_tr.setdefault(fc, tc)

# jogos só nas fichas (2026 em diante, ou buracos da tabela)
for f in sobras:
    adv, uf = adv_map.get((key(f['adversario']), f['adversario_uf']), (f['adversario'], f['adversario_uf']))
    gm = f['galo_mandante']
    tab.append({'n': None, 'data': f['data'], 'temporada': int(f['data'][:4]), 'competicao': comp_tr.get(f.get('competicao'), f.get('competicao')),
                'mando': 'C' if gm else 'F', 'adversario': adv, 'adversario_uf': uf, 'gp': f['gp'], 'gc': f['gc'],
                'resultado': f['resultado'], 'wo': False, 'gols': [], 'nota': None, 'fonte': 'ficha', 'ficha': f})
    if f['data'] < '2026-01-01':
        rep.append(f"{f['data']} x {adv}: ficha sem linha correspondente na tabela (entrou só pela ficha)")
tab.sort(key=lambda j: (j['data'], j['n'] or ''))

# ---------------- 4. apelidos tabela -> nome da ficha ----------------
votos = defaultdict(Counter); voto_anos = defaultdict(list)
for j in tab:
    f = j.get('ficha')
    if not f or j['fonte'] != 'tabela': continue
    tg = Counter(g['jogador'] for g in j['gols'] if g['tipo'] != 'contra' and g['jogador'] != 'Não identificado')
    fg = Counter(g['jogador'] for g in f['gols'] if g['lado'] == 'galo' and 'contra' not in (g['tipo'] or '') and g['jogador'] != 'Não identificado')
    for tn, c in tg.items():
        if tn in fg: votos[tn][tn] += 1; continue
        tk = set(key(tn).split())
        cand = [fn for fn, fc in fg.items() if fc == c and (tk & set(key(fn).split()))]
        if len(cand) == 1: votos[tn][cand[0]] += 1; voto_anos[(tn, cand[0])].append(j['temporada'])
alias_tab, alias_range = {}, {}
for tn, c in votos.items():
    fn, n = c.most_common(1)[0]
    if fn != tn: alias_tab[tn] = fn
for tn, fn in alias_tab.items():
    anos = voto_anos[(tn, fn)]  # só os anos em que a ficha confirmou o apelido
    alias_range[tn] = (min(anos) - 6, max(anos) + 1)
rep.append(f"Apelidos da tabela ligados ao nome completo das fichas: {len(alias_tab)} (ex.: " +
           ', '.join(f'{a} = {b}' for a, b in list(alias_tab.items())[:6]) + ')')

# ---------------- 5. jogo final ----------------
# clubes que mudaram de nome contam juntos no retrospecto (o jogo mantém o nome da época)
MESMO_CLUBE = {key('Palestra Itália MG'): key('Cruzeiro MG')}
jogos = []
for i, j in enumerate(tab, 1):
    f = j.get('ficha')
    for g in j['gols']:
        a = alias_tab.get(g['jogador'])
        if a and alias_range[g['jogador']][0] <= j['temporada'] <= alias_range[g['jogador']][1]:
            g['jogador'] = a
    gols = j['gols']
    if f:
        fg = [g for g in f['gols'] if g['lado'] == 'galo']
        if j['gp'] is not None and len(fg) == j['gp'] and all(g['lado'] in ('galo', 'adv') for g in f['gols']):
            gols = f['gols']  # ficha tem minuto e gols do adversário
        elif j['fonte'] == 'ficha':
            gols = f['gols']
    out = {'id': i, 'data': j['data'], 'temporada': j['temporada'], 'competicao': j['competicao'], 'grupo': familia(j['competicao']),
           'mando': j['mando'], 'adversario': j['adversario'], 'adversario_uf': j['adversario_uf'],
           'adversario_id': MESMO_CLUBE.get(key(j['adversario'] + ' ' + (j['adversario_uf'] or '')), key(j['adversario'] + ' ' + (j['adversario_uf'] or ''))),
           'gp': j['gp'], 'gc': j['gc'], 'resultado': j['resultado'], 'wo': j['wo'], 'nota': j['nota'], 'data_aprox': j.get('data_aprox', False),
           'gols': [{k: g.get(k) for k in ('jogador', 'minuto', 'tipo', 'lado')} for g in gols], 'tem_ficha': bool(f)}
    if f:
        for k in ('mandante', 'mandante_uf', 'visitante', 'visitante_uf', 'gols_mandante', 'gols_visitante', 'galo_mandante', 'cidade', 'estadio',
                  'publico', 'publico_tipo', 'renda', 'arbitro', 'expulsoes', 'obs', 'competicao_raw', 'fase',
                  'escalacao_galo', 'escalacao_adv', 'tecnico_galo', 'tecnico_adv', 'correcoes'):
            if f.get(k) is not None: out[k] = f[k]
    jogos.append(out)

epocas = {}
# ---------------- 5a. período conhecido dos artilheiros (números aceitos) ----------------
# gols com o mesmo nome fora do período do jogador conhecido viram outro jogador: "Reinaldo (1995–98)"
if ACEITOS:
    periodo = {}
    for a in json.load(open(ACEITOS, encoding='utf-8')):
        for r in a.get('ranking', []):
            if a['calculo']['tipo'] == 'gols_ranking' and not a['calculo'].get('adversario_id'):
                periodo[r['nome']] = (r['de'], r['ate'])
    fora = defaultdict(set)
    for j in jogos:
        for g in j['gols']:
            pr = periodo.get(g['jogador'])
            if pr and g['lado'] == 'galo' and not (pr[0] <= j['temporada'] <= pr[1]): fora[g['jogador']].add(j['temporada'])
    for n, anos in fora.items():
        anos = sorted(anos); grupos = [[anos[0]]]
        for x in anos[1:]: (grupos[-1].append(x) if x - grupos[-1][-1] <= 3 else grupos.append([x]))
        nomes = {x: (f"{n} ({g[0]})" if g[0] == g[-1] else f"{n} ({g[0]}–{str(g[-1])[2:]})") for g in grupos for x in g}
        for j in jogos:
            if j['temporada'] in nomes:
                for g in j['gols']:
                    if g['jogador'] == n and g['lado'] == 'galo': g['jogador'] = nomes[j['temporada']]
        epocas[n] = [(periodo[n][0], periodo[n][1], n)] + [(g[0], g[-1], nomes[g[0]]) for g in grupos]
        rep.append(f"{n}: gols fora do período {periodo[n][0]}-{periodo[n][1]} separados como " + ', '.join(sorted(set(nomes.values()))))

# ---------------- 5b. homônimos de épocas diferentes ----------------
# mesmo nome com intervalo de mais de 8 anos sem gols = jogadores diferentes (ex.: Guilherme dos anos 1910 x 2010)
datas = defaultdict(list)
for j in jogos:
    for g in j['gols']:
        if g['lado'] == 'galo' and g['jogador'] != 'Não identificado' and 'contra' not in (g['tipo'] or ''):
            datas[g['jogador']].append(j['temporada'])
renome = {}
MESMO_JOGADOR = set(C.get('mesmo_jogador', []))
for n, anos in datas.items():
    anos = sorted(set(anos)); grupos = [[anos[0]]]
    for a in anos[1:]:
        (grupos[-1].append(a) if a - grupos[-1][-1] <= 8 else grupos.append([a]))
    if len(grupos) > 1 and n not in MESMO_JOGADOR:
        cont = Counter(datas[n]); maior = max(grupos, key=lambda gr: sum(cont[a] for a in gr))
        nomes_gr = []
        for gr in grupos:
            nm = n if gr is maior else (f"{n} ({gr[0]})" if gr[0] == gr[-1] else f"{n} ({gr[0]}–{str(gr[-1])[2:]})")
            nomes_gr.append((gr[0], gr[-1], nm))
            if gr is maior: continue  # a época com mais gols fica com o nome puro
            for a in gr: renome[(n, a)] = nm
        if n not in epocas: epocas[n] = nomes_gr
        rep.append(f"Homônimos separados por época: {n} -> " + ', '.join(f'{g[0]}-{g[-1]}' for g in grupos))
for j in jogos:
    for g in j['gols']:
        if (g['jogador'], j['temporada']) in renome and g['lado'] == 'galo':
            g['jogador'] = renome[(g['jogador'], j['temporada'])]
    e = j.get('escalacao_galo')
    if e:
        def ep(x, a=j['temporada']):  # escalação: época mais próxima do ano do jogo
            if x not in epocas: return x
            return min(epocas[x], key=lambda t: 0 if t[0] <= a <= t[1] else min(abs(a - t[0]), abs(a - t[1])))[2]
        e['titulares'] = [ep(x) for x in e['titulares']]
        for sb in e['substituicoes']:
            sb['entrou'] = ep(sb['entrou']); sb['saiu'] = ep(sb['saiu'])

# ---------------- 5b2. homônimos sem gol, separados à mão por período (correcoes.json > jogadores_por_data) ----------------
for r in C.get('jogadores_por_data', []):
    for j in jogos:
        if not (r['de'] <= j['data'] <= r['ate']): continue
        for g in j['gols']:
            if g['lado'] == 'galo' and g['jogador'] == r['nome']: g['jogador'] = r['novo']
        e = j.get('escalacao_galo')
        if e:
            e['titulares'] = [r['novo'] if x == r['nome'] else x for x in e['titulares']]
            for sb in e['substituicoes']:
                if sb.get('entrou') == r['nome']: sb['entrou'] = r['novo']
                if sb.get('saiu') == r['nome']: sb['saiu'] = r['novo']

# ---------------- 5c. nomes de estádio padronizados ----------------
EST = C.get('estadios', {})
for j in jogos:
    e = j.get('estadio')
    if e:
        e = re.sub(r'[\s:;,.]+$', '', re.sub(r'\.\s*Renda:.*$', '', e)).strip()
        j['estadio'] = EST.get(e, EST.get(e + ':', e))

# ---------------- 5d. RSSSF: cidade dos jogos sem ficha (1909-2006) e maiores públicos ----------------
import os
def _sem_acento(x): return ''.join(ch for ch in unicodedata.normalize('NFD', x) if unicodedata.category(ch) != 'Mn').upper()
CID = {}
for j in jogos:
    c = j.get('cidade')
    if c and ',' in c: CID.setdefault(_sem_acento(c.replace(', ', '/')), c)
def _cidade(loc):
    k = _sem_acento(loc)
    if k in CID: return CID[k]
    if '/' in loc:
        a, b = loc.rsplit('/', 1)
        a = ' '.join(w.capitalize() if w not in ('DE','DA','DO','DOS','DAS') else w.lower() for w in a.split())
        b = b if len(b) == 2 else b.capitalize()
        return f'{a}, {b}'
    return loc.title()
BYD = {}
for j in jogos: BYD.setdefault(j['data'], []).append(j)
def _acha(data, gp, gc):
    c = BYD.get(data, [])
    m = [j for j in c if j.get('gp') == gp and j.get('gc') == gc]
    return m[0] if len(m) == 1 else (c[0] if len(c) == 1 and not m else None)
rs = 'data/rsssf/todos_jogos_1909_2006.txt'
n_cid = 0
if os.path.exists(rs):
    for l in open(rs, encoding='utf-8', errors='replace'):
        m = re.match(r'(\d\d)/(\d\d)/(\d{4}) (.{21}) CAM\s+(\d+)x(\d+) ', l)
        if not m: continue
        d, mo, y, loc, a, b = m.groups(); loc = loc.strip()
        if loc in ('?', ''): continue
        j = _acha(f'{y}-{mo}-{d}', int(a), int(b))
        if j and not j.get('tem_ficha') and not j.get('cidade'):
            j['cidade'] = _cidade(loc); j['cidade_fonte'] = 'RSSSF'; n_cid += 1
EST_RS = {'MINEIRAO': 'Mineirão', 'MARACANA': 'Maracanã', 'MARACANÃ': 'Maracanã', 'MORUMBI': 'Morumbi', 'SERRA DOURADA': 'Serra Dourada'}
rp = 'data/rsssf/maiores_publicos.txt'
n_pub = 0
if os.path.exists(rp):
    for l in open(rp, encoding='utf-8', errors='replace'):
        m = re.match(r'\d{3}\s+(\d\d)/(\d\d)/(\d{4})\s+([\d.]+)\s+ATL-MG (\d+)x(\d+) .*?\s{2,}\S.*?\s{2,}(\S.*?)\s*$', l)
        if not m: continue
        d, mo, y, pub, a, b, est = m.groups()
        j = _acha(f'{y}-{mo}-{d}', int(a), int(b))
        if not j: continue
        if j.get('publico') is None:
            j['publico'] = int(pub.replace('.', '')); j['publico_tipo'] = j.get('publico_tipo') or 'presentes'; n_pub += 1
        if not j.get('estadio'): j['estadio'] = EST_RS.get(est.strip().upper(), est.strip().title())
print('RSSSF: cidade em', n_cid, 'jogos; público em', n_pub, 'jogos', file=sys.stderr)

# ---------------- 5e. pênaltis defendidos pelo goleiro do Galo ----------------
def _base(n): return re.sub(r'\s*\(\d{4}(?:[–-]\d{2,4})?\)$', '', n or '')
PD = json.load(open('data/penaltis_disputas.json', encoding='utf-8'))['disputas'] if os.path.exists('data/penaltis_disputas.json') else []
PDD = {x['data']: x for x in PD}
PNJ = {}
for y in (json.load(open('data/penaltis_disputas.json', encoding='utf-8')).get('no_jogo', []) if os.path.exists('data/penaltis_disputas.json') else []): PNJ.setdefault(y['data'], []).append(y)
for j in jogos:
    e = j.get('escalacao_galo') or {'titulares': [], 'substituicoes': []}
    gal = list(e['titulares']) + [s['entrou'] for s in e['substituicoes']]
    canon = lambda nm: next((g for g in gal if _base(g) == nm or g == nm), None)
    defs = []
    o = j.get('obs') or ''
    for s in re.split(r'(?<=[.)])\s+(?=[A-ZÁÉÍÓÚ])', o):
        if re.search(r'decis[aã]o por p|Nos penaltys|disputa de penal|ganhou nos penal', s, re.I): continue
        for m in re.finditer(r"([A-ZÁÉÍÓÚ][\wÀ-ÿ']+(?: [A-ZÁÉÍÓÚ][\wÀ-ÿ']+)?)(?: \((?:A|At)\)|, goleiro atleticano,)? defendeu (?:penalty|outro)(?:.*?(?:cobrado|batido) por ([^(,.]+?)(?: \(\w+\))?(?: aos|[,.]|$))?", s):
            g = canon(m.group(1))
            if g: defs.append({'goleiro': g, 'tipo': 'jogo', 'cobrador': (m.group(2) or '').strip() or None})
    for y in PNJ.get(j['data'], []):
        g = canon(y['goleiro']) or y['goleiro']
        if not any(d['tipo'] == 'jogo' and d['goleiro'] == g and (d['cobrador'] or '') == y.get('cobrador', '') for d in defs):
            defs.append({'goleiro': g, 'tipo': 'jogo', 'cobrador': y.get('cobrador')})
    x = PDD.get(j['data'])
    if x:
        g = canon(x['goleiro']) or x['goleiro']
        cob = x.get('cobradores') or []
        for i in range(x['n']): defs.append({'goleiro': g, 'tipo': 'disputa', 'cobrador': cob[i] if i < len(cob) else None})
    if defs: j['pen_defendidos'] = defs

# ---------------- 6. jogadores e técnicos ----------------
P = defaultdict(lambda: {'jogos': 0, 'titular': 0, 'gols': 0, 'gols_penalti': 0, 'primeiro': None, 'ultimo': None, 'por_comp': Counter(), 'gols_comp': Counter()})
POS = defaultdict(lambda: defaultdict(int))
def touch(p, d):
    p['primeiro'] = min(filter(None, [p['primeiro'], d])); p['ultimo'] = max(filter(None, [p['ultimo'], d]))
T = defaultdict(lambda: {'jogos': 0, 'V': 0, 'E': 0, 'D': 0, 'primeiro': None, 'ultimo': None})
for j in jogos:
    e = j.get('escalacao_galo') if j['data'] >= DESDE else None  # jogos/titular só no período com escalações contínuas
    if e:
        for n in set(e['titulares']) | {s['entrou'] for s in e['substituicoes']}:
            p = P[n]; p['jogos'] += 1; p['por_comp'][j['grupo']] += 1; touch(p, j['data'])
        for n in set(e['titulares']): P[n]['titular'] += 1
        gr, ng = e.get('grupos'), e.get('ngrupos', 0)
        if gr and len(gr) == len(e['titulares']) and ng >= 4:
            for n, gi in zip(e['titulares'], gr):
                pos = 'Goleiro' if gi == 0 else 'Defensor' if gi == 1 else 'Atacante' if gi == ng - 1 else 'Meia'
                POS[n][pos] += 1
    for g in j['gols']:
        if g['lado'] == 'galo' and g['tipo'] != 'contra' and 'contra' not in (g['tipo'] or '') and g['jogador'] != 'Não identificado':
            p = P[g['jogador']]; p['gols'] += 1; p['gols_comp'][j['grupo']] += 1; touch(p, j['data'])
            if g['tipo'] and 'penal' in g['tipo']: p['gols_penalti'] += 1
    t = j.get('tecnico_galo')
    if t and j['resultado']:
        x = T[t]; x['jogos'] += 1; x[j['resultado']] += 1; touch(x, j['data'])

com_ficha = [j['data'] for j in jogos if j['tem_ficha'] and j.get('escalacao_galo') and j['escalacao_galo']['titulares']]
meta = {'gerado_em': date.today().isoformat(), 'total': len(jogos), 'primeiro': jogos[0]['data'], 'ultimo': jogos[-1]['data'],
        'fichas': sum(j['tem_ficha'] for j in jogos), 'escalacoes_desde': DESDE,
        'fontes': ['Tabela histórica de jogos do Galo Metrics', 'Fichas técnicas: O Canto do Galo (galopedia.blogspot.com)']}
for n, c in POS.items():
    if n in P and sum(c.values()) >= 2:
        P[n]['posicao'] = max(c.items(), key=lambda kv: kv[1])[0]
for j in jogos:
    e = j.get('escalacao_galo')
    if e: e.pop('grupos', None); e.pop('ngrupos', None)
json.dump({'meta': meta, 'jogos': jogos,
           'jogadores': [{'nome': n, **{k: dict(v) if isinstance(v, Counter) else v for k, v in d.items()}} for n, d in P.items()],
           'tecnicos': [{'nome': n, **d} for n, d in T.items()]},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
open(REP, 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
print(meta)
