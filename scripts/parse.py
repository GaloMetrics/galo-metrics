"""Parser das fichas do Canto do Galo -> base JSON do Galo Metrics."""
import re, json, sys, unicodedata, glob, os
from collections import Counter, defaultdict

RAW = sys.argv[1]
OUT = sys.argv[2]

HEADER = re.compile(r'^(\d{2})/(\d{2})/(\d{4}) - (.+?)\s*$')
SCORE = re.compile(r'^(.+?)\s+(\d+)\s*x\s*(\d+)\s+(.+)$')
NOSCORE = re.compile(r'^(.+?)\s+x\s+(.+)$')
STOP = ('Postagens mais', 'Clique no Banner', 'Assinar:', 'Anos das', 'Mostrando postagens', 'Mais Criar blog')
FIELDS = ('Local:', 'Estádio:', 'Público:', 'Competição:', 'Árbitro:', 'Expuls', 'GOLS:', 'GOL:', 'OBS:')
FIELD_FIX = re.compile(r'^(Local|Estádio|Público|Competição|Árbitro|GOLS|GOL|OBS)\s+:')


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', s)).strip()


def split_team(t):
    t = t.strip()
    m = re.match(r'^(.*?)\s+([A-Z]{2,3})$', t)
    if m:
        return m.group(1).strip(), m.group(2)
    return t, None


def is_galo(name, uf):
    return norm(name) == 'atletico' and uf in ('MG', None)


def read_blocks(path):
    lines = open(path, encoding='utf-8').read().splitlines()
    blocks, cur = [], None
    for ln in lines:
        s = ln.strip()
        if HEADER.match(s) and re.search(r'\dx\d| x ', s):
            if cur: blocks.append(cur)
            cur = [s]; continue
        if cur is None: continue
        if any(s.startswith(p) for p in STOP) or re.match(r'^\d{2}/\d{2}/\d{4}, \d', s) or s.startswith('https://'):
            # rodapé do blog: só fecha se a ficha já tem OBS
            if any(l.startswith('OBS:') for l in cur):
                blocks.append(cur); cur = None
            continue
        if re.match(r'^\d{4} \(\d+\)$', s) or re.match(r'^[A-Z]{2} .+\(\d+\)$', s):
            continue  # índice lateral do blog
        if s: cur.append(s)
    if cur: blocks.append(cur)
    return blocks


def join_wrapped(lines):
    """Junta linhas quebradas (versão PDF da página) na linha de campo anterior."""
    out = []
    for l in lines:
        l = FIELD_FIX.sub(lambda m: m.group(1) + ':', l)
        starts_field = any(l.startswith(f) for f in FIELDS) or re.match(r'^[A-ZÀ-Ü0-9\-\.\' ]{2,}:', l)
        if out and not starts_field:
            out[-1] += ' ' + l
        else:
            out.append(l)
    return out


ULT_GRUPOS = ([], 0)
def parse_people(txt):
    """'A; B (C), D e E (F) (G) - Tec: X.' -> titulares, reservas, tecnico"""
    txt = txt.strip().rstrip('.').strip()
    tec = None
    m = re.search(r'[-–]\s*T[eé]c(?:nico)?:?\s*(?:[-–]\s*T[eé]c:\s*)?(.+)$', txt)
    if not m:  # "- Oswaldo de Oliveira." sem a palavra Tec, fora de parênteses
        m2 = re.search(r'\s[-–]\s+([A-ZÁÉÍÓÚÂÊÔ][^()\-–;]+?)\s*\.?\s*$', txt)
        if m2 and txt.rfind(')') < m2.start(): m = m2
    if m:
        tec = m.group(1).strip().rstrip('.')
        txt = txt[:m.start()].strip()
    if txt in ('', '?'):
        return [], [], tec
    txt = re.sub(r'\)\s+(?=[A-ZÀ-Ü])', '), ', txt)  # vírgula esquecida: "Pavón (X) Hulk"

    segs = txt.split(';')
    parts, gidx = [], []
    for gi, seg in enumerate(segs):
        for q in re.split(r',|:|\s+e\s+|(?<=[a-zà-ü][a-zà-ü])\.\s|(?<=\))\.\s|\s\.\s', seg):
            parts.append(q); gidx.append(gi)
    starters, subs, grp = [], [], []
    for p, gi in zip(parts, gidx):
        p = p.strip()
        if not p: continue
        inner = re.findall(r'\(([^()]+)\)', p)
        base = re.sub(r'\([^()]*\)', '', p).strip().strip('"').strip()
        if base:
            starters.append(base); grp.append(gi)
        prev = base
        for s in inner:
            s = re.sub(r'-G$', '', s).strip()
            if s and s != '?':
                subs.append({'entrou': s, 'saiu': prev})
                prev = s
    seen, st2, g2 = set(), [], []
    for a, b in zip(starters, grp):  # nome repetido na ficha
        if a not in seen: seen.add(a); st2.append(a); g2.append(b)
    global ULT_GRUPOS
    ULT_GRUPOS = (g2, len(segs))
    return st2, subs, tec


def parse_goals(txt):
    """'Hulk (51' e 58' - penalty), Reinier (29')' -> lista de gols"""
    txt = txt.strip().rstrip('.').strip()
    goals = []
    # quebra em scorers respeitando parênteses
    depth, buf, items = 0, '', []
    i = 0
    while i < len(txt):
        c = txt[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if depth == 0 and (c == ',' or txt[i:i+3] == ' e '):
            items.append(buf); buf = ''
            i += 3 if txt[i:i+3] == ' e ' else 1
            continue
        buf += c; i += 1
    items.append(buf)
    for it in items:
        it = it.strip()
        if not it or it == '?': continue
        m = re.match(r'^(.+?)\s*\((.+)\)\s*$', it)
        if not m:
            goals.append({'jogador': it, 'minuto': None, 'tipo': None}); continue
        name, inner = m.group(1).strip(), m.group(2)
        # Aníbal Machado "Pingo" (2) -> quantidade de gols (fichas antigas)
        if re.fullmatch(r'\d+', inner.strip()) and int(inner) <= 13:
            for _ in range(int(inner)):
                goals.append({'jogador': name, 'minuto': None, 'tipo': None})
            continue
        for g in re.split(r'\s+e\s+|,', inner):
            g = g.strip()
            mm = re.match(r'^(\d+)\s*[\'"’´`]?\s*(?:[-–—]\s*(.+))?$', g)
            mt = re.match(r'^(\d)\s*º?\s*t(?:empo)?\s*(?:[-–—]\s*(.+))?$', g, re.I)
            if mt:
                goals.append({'jogador': name, 'minuto': None, 'tipo': (mt.group(2) or '').strip().lower() or None, 'tempo': int(mt.group(1))})
            elif mm:
                tipo = (mm.group(2) or '').strip().lower() or None
                goals.append({'jogador': name, 'minuto': int(mm.group(1)), 'tipo': tipo})
            else:
                goals.append({'jogador': name, 'minuto': None, 'tipo': g or None})
    return goals


def parse_block(b, src):
    head = HEADER.match(b[0])
    d, mo, y, rest = head.groups()
    if re.search(r'Atl[ée]tico[- ]B\b|Sub-?\d\d', rest + ' ' + ' '.join(b[:8])):
        return None  # time B / sub-23: fora da contagem do time principal
    m = SCORE.match(rest)
    if m:
        h, hg, ag, a = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    else:
        m = NOSCORE.match(rest)
        h, a = m.group(1), m.group(2); hg = ag = None
    hn, huf = split_team(h); an, auf = split_team(a)
    galo_home = is_galo(hn, huf)
    if not galo_home and not is_galo(an, auf):
        galo_home = None
    j = {'data': f'{y}-{mo}-{d}', 'mandante': hn, 'mandante_uf': huf, 'visitante': an, 'visitante_uf': auf,
         'gols_mandante': hg, 'gols_visitante': ag, 'fonte': os.path.basename(src)}
    lines = join_wrapped(b[1:])
    team_lines = {}
    for l in lines:
        if l.startswith('Local:'): j['cidade'] = l[6:].strip().rstrip('.')
        elif l.startswith('Estádio:'): j['estadio'] = l[8:].strip().rstrip('.')
        elif l.startswith('Público:'):
            pm = re.search(r'([\d\.]+)\s+(pagantes|presentes)', l)
            j['publico'] = int(pm.group(1).replace('.', '')) if pm else None
            j['publico_tipo'] = pm.group(2) if pm else None
            rm = re.search(r'Renda:\s*(R\$\s*[\d\.,]+)', l)
            j['renda'] = rm.group(1).rstrip('.') if rm else None
        elif l.startswith('Competição:'):
            c = l[11:].strip().rstrip('.')
            cm = re.match(r'^(.*?)(?:/(\d{4}))?\s*(?:\((.+)\))?$', c)
            j['competicao'] = cm.group(1).strip(); j['temporada_comp'] = cm.group(2); j['fase'] = cm.group(3)
            j['competicao_raw'] = c
        elif l.startswith('Árbitro:'): j['arbitro'] = l[8:].strip().rstrip('.')
        elif l.startswith('Expuls'): j['expulsoes'] = l.split(':', 1)[1].strip().rstrip('.')
        elif l.startswith('GOLS:') or l.startswith('GOL:'): j['gols_raw'] = l.split(':', 1)[1].strip()
        elif l.startswith('OBS:'): j['obs'] = l[4:].strip() or None
        else:
            tm = re.match(r'^([^:]{2,40}):\s*(.*)$', l)
            if tm: team_lines[tm.group(1).strip()] = tm.group(2)
    # escalações
    galo_key = next((k for k in team_lines if norm(k) == 'atletico'), None)
    other_keys = [k for k in team_lines if k != galo_key and k == k.upper()]
    j['escalacao_galo'] = None; j['escalacao_adv'] = None
    if galo_key:
        s, sb, t = parse_people(team_lines[galo_key])
        j['escalacao_galo'] = {'titulares': s, 'substituicoes': sb, 'grupos': ULT_GRUPOS[0], 'ngrupos': ULT_GRUPOS[1]}; j['tecnico_galo'] = t
    if other_keys:
        s, sb, t = parse_people(team_lines[other_keys[0]])
        j['escalacao_adv'] = {'titulares': s, 'substituicoes': sb}; j['tecnico_adv'] = t
    j['galo_mandante'] = galo_home
    return j


def main():
    jogos, seen = [], set()
    for f in sorted(glob.glob(os.path.join(RAW, '*.txt'))):
        for b in read_blocks(f):
            try:
                j = parse_block(b, f)
            except Exception as e:
                print('ERRO', f, b[0], e); continue
            if j is None: continue
            key = (j['data'], norm(j['mandante']), norm(j['visitante']))
            if key in seen: continue
            seen.add(key); jogos.append(j)
    jogos.sort(key=lambda j: j['data'])
    # gols + atribuição de lado
    for i, j in enumerate(jogos):
        j['id'] = i + 1
        galo_players = set()
        if j['escalacao_galo']:
            galo_players = {norm(p) for p in j['escalacao_galo']['titulares']} | {norm(s['entrou']) for s in j['escalacao_galo']['substituicoes']}
        adv_players = set()
        if j['escalacao_adv']:
            adv_players = {norm(p) for p in j['escalacao_adv']['titulares']} | {norm(s['entrou']) for s in j['escalacao_adv']['substituicoes']}
        gols = []
        raw = j.get('gols_raw')
        if raw:
            if ';' in raw:  # formato antigo: "mandante ; visitante"
                hpart, apart = raw.split(';', 1)
                for side, part in (('mandante', hpart), ('visitante', apart)):
                    for g in parse_goals(part):
                        g['lado'] = 'galo' if (side == 'mandante') == bool(j['galo_mandante']) else 'adv'
                        gols.append(g)
            else:
                for g in parse_goals(raw):
                    n = norm(g['jogador']); contra = g['tipo'] and 'contra' in g['tipo']
                    if n in galo_players: side = 'adv' if contra else 'galo'
                    elif n in adv_players: side = 'galo' if contra else 'adv'
                    else: side = '?'
                    g['lado'] = side; gols.append(g)
        # fichas sem escalação: gols sem lado conhecido e contagem bate com o placar do Galo
        unk = [g for g in gols if g['lado'] == '?']
        if unk and j.get('gols_mandante') is not None and j['galo_mandante'] is not None:
            gp = j['gols_mandante'] if j['galo_mandante'] else j['gols_visitante']
            if len(unk) == gp - sum(1 for g in gols if g['lado'] == 'galo'):
                for g in unk: g['lado'] = 'galo'
        # completa gols sem autor identificado
        if j.get('gols_mandante') is not None and j['galo_mandante'] is not None:
            gp, gc = (j['gols_mandante'], j['gols_visitante']) if j['galo_mandante'] else (j['gols_visitante'], j['gols_mandante'])
            for side, tot in (('galo', gp), ('adv', gc)):
                falta = tot - sum(1 for g in gols if g['lado'] == side)
                for _ in range(max(0, falta)):
                    gols.append({'jogador': 'Não identificado', 'minuto': None, 'tipo': None, 'lado': side})
        j['gols'] = gols
        gm, gv = j['gols_mandante'], j['gols_visitante']
        if gm is None or j['galo_mandante'] is None:
            j['gp'] = j['gc'] = j['resultado'] = None
        else:
            j['gp'], j['gc'] = (gm, gv) if j['galo_mandante'] else (gv, gm)
            j['resultado'] = 'V' if j['gp'] > j['gc'] else ('E' if j['gp'] == j['gc'] else 'D')
        j['adversario'] = j['visitante'] if j['galo_mandante'] else j['mandante']
        j['adversario_uf'] = j['visitante_uf'] if j['galo_mandante'] else j['mandante_uf']
    json.dump(jogos, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(jogos), 'jogos')


main()
