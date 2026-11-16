# geo.py: limpa cidades, completa cidade pelo estádio, geocodifica e gera o mapa (SVG) do Galo
# uso: python3 geo.py data/galo.json /home/claude/geo
import json, sys, re, csv, math, unicodedata
from collections import Counter, defaultdict
import geonamescache

GJ, GEO = sys.argv[1], sys.argv[2]
G = json.load(open(GJ, encoding='utf-8'))
J = G['jogos']
def sem(s): return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode().lower().strip()

UF = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()
UFN = {'AC':'Acre','AL':'Alagoas','AP':'Amapá','AM':'Amazonas','BA':'Bahia','CE':'Ceará','DF':'Distrito Federal','ES':'Espírito Santo','GO':'Goiás','MA':'Maranhão','MT':'Mato Grosso','MS':'Mato Grosso do Sul','MG':'Minas Gerais','PA':'Pará','PB':'Paraíba','PR':'Paraná','PE':'Pernambuco','PI':'Piauí','RJ':'Rio de Janeiro','RN':'Rio Grande do Norte','RS':'Rio Grande do Sul','RO':'Rondônia','RR':'Roraima','SC':'Santa Catarina','SP':'São Paulo','SE':'Sergipe','TO':'Tocantins'}
# país (como escrito nas fichas) -> nome padrão, ISO2, ISO3
PAIS = {}
for nomes, pad, i2, i3 in [
  (['alemanha'], 'Alemanha', 'DE', 'DEU'), (['austria', 'áustria'], 'Áustria', 'AT', 'AUT'), (['belgica'], 'Bélgica', 'BE', 'BEL'),
  (['luxemburgo'], 'Luxemburgo', 'LU', 'LUX'), (['franca'], 'França', 'FR', 'FRA'), (['uruguai'], 'Uruguai', 'UY', 'URY'),
  (['paraguai'], 'Paraguai', 'PY', 'PRY'), (['mexico'], 'México', 'MX', 'MEX'), (['camaroes'], 'Camarões', 'CM', 'CMR'),
  (['romenia'], 'Romênia', 'RO', 'ROU'), (['italia'], 'Itália', 'IT', 'ITA'), (['espanha'], 'Espanha', 'ES', 'ESP'),
  (['indonesia'], 'Indonésia', 'ID', 'IDN'), (['bahreim', 'bahrein'], 'Bahrein', 'BH', 'BHR'), (['qatar', 'catar'], 'Catar', 'QA', 'QAT'),
  (['kuwait', 'kwait'], 'Kuwait', 'KW', 'KWT'), (['arabia saudita'], 'Arábia Saudita', 'SA', 'SAU'), (['portugal'], 'Portugal', 'PT', 'PRT'),
  (['chile'], 'Chile', 'CL', 'CHL'), (['argentina'], 'Argentina', 'AR', 'ARG'), (['holanda'], 'Holanda', 'NL', 'NLD'),
  (['colombia'], 'Colômbia', 'CO', 'COL'), (['argelia'], 'Argélia', 'DZ', 'DZA'), (['suica'], 'Suíça', 'CH', 'CHE'),
  (['dinamarca'], 'Dinamarca', 'DK', 'DNK'), (['ilhas faroe'], 'Ilhas Faroe', 'FO', 'FRO'), (['inglaterra'], 'Inglaterra', 'GB', 'GBR'),
  (['equador'], 'Equador', 'EC', 'ECU'), (['japao'], 'Japão', 'JP', 'JPN'), (['estados unidos', 'eua', 'estado unidos'], 'Estados Unidos', 'US', 'USA'),
  (['peru'], 'Peru', 'PE', 'PER'), (['venezuela'], 'Venezuela', 'VE', 'VEN'), (['hong kong'], 'Hong Kong', 'HK', 'CHN'),
  (['bolivia'], 'Bolívia', 'BO', 'BOL'), (['vietna', 'vietnan', 'vietnam'], 'Vietnã', 'VN', 'VNM'), (['marrocos'], 'Marrocos', 'MA', 'MAR'),
  (['china'], 'China', 'CN', 'CHN'), (['escocia'], 'Escócia', 'GB', 'GBR'), (['hungria'], 'Hungria', 'HU', 'HUN'), (['bulgaria'], 'Bulgária', 'BG', 'BGR'),
  (['iugoslavia'], 'Iugoslávia', 'RS', 'SRB'), (['suecia'], 'Suécia', 'SE', 'SWE'), (['polonia'], 'Polônia', 'PL', 'POL'),
  (['russia'], 'Rússia', 'RU', 'RUS'), (['ucrania'], 'Ucrânia', 'UA', 'UKR'), (['tchecoslovaquia'], 'Tchecoslováquia', 'CZ', 'CZE'), (['jamaica'], 'Jamaica', 'JM', 'JAM')]:
    for n in nomes: PAIS[sem(n)] = (pad, i2, i3)
# cidade estrangeira (como escrita) -> nome no geonames, ou coordenadas fixas
ALIAS = {'munich': 'Munich', 'hamburgo': 'Hamburg', 'viena': 'Vienna', 'bruxelas': 'Brussels', 'brunswick': 'Braunschweig',
  'cidade de luxemburgo': 'Luxembourg', 'montevideu': 'Montevideo', 'assuncao': 'Asunción', 'yauonde': 'Yaoundé', 'bucareste': 'Bucharest',
  'roma': 'Rome', 'la coruna': 'A Coruña', 'djakarta': 'Jakarta', 'ujung-pandang': 'Makassar', 'mahama': 'Manama', 'jeddah': 'Jeddah',
  'napoli': 'Naples', 'argel': 'Algiers', 'salzburg': 'Salzburg', 'madri': 'Madrid', 'liege': 'Liège', 'berna': 'Bern', 'padova': 'Padova',
  'amsterdam': 'Amsterdam', 'berlim': 'Berlin', 'reggio calabria': 'Reggio Calabria', 'turim': 'Turin', 'lerida': 'Lleida', 'fusuoka': 'Fukuoka',
  'cali': 'Cali', 'rosario': 'Rosario', 'kowloon': 'Kowloon', 'ho chi minh': 'Ho Chi Minh City', 'calama': 'Calama', 'marrakesh': 'Marrakesh',
  'tayiuan': 'Taiyuan', 'santa fe': 'Santa Fe', 'cusco': 'Cusco', 'timisiora': 'Timişoara', 'guayaquil': 'Guayaquil', 'kuwait': 'Kuwait City',
  'doha': 'Doha', 'saarbrucken': 'Saarbrücken', 'bogota': 'Bogotá', 'cadiz': 'Cádiz', 'malaga': 'Málaga', 'leon': 'León de los Aldama',
  'quito': 'Quito', 'lima': 'Lima', 'la paz': 'La Paz', 'medellin': 'Medellín', 'ibague': 'Ibagué', 'logrono': 'Logroño', 'sangolqui': 'Sangolquí',
  'santiago': 'Santiago', 'buenos aires': 'Buenos Aires', 'san francisco del rincon': 'San Francisco del Rincón'}
FIXO = {'taguatinga': (-15.83, -48.06), 'gama': (-16.02, -48.06), 'sobradinho': (-15.65, -47.79), 'planaltina': (-15.62, -47.65), 'sangolqui': (-0.33, -78.45), 'kumba': (4.64, 9.45), 'vittel': (48.2, 5.94), 'cingoli': (43.37, 13.22), 'vildsberg': (55.7, 12.4), 'heion': (50.1, 8.2),
  'la calera': (-32.79, -71.2), 'la linea': (36.16, -5.35), 'torshavn': (62.01, -6.77), 'patterson': (40.92, -74.17), 'bridgeport': (41.18, -73.19),
  'boca raton': (26.36, -80.08), 'fort lauderdale': (26.12, -80.14), 'saint petersburg': (27.77, -82.64), 'orlando': (28.54, -81.38), 'miami': (25.77, -80.19),
  'godoy cruz': (-32.93, -68.84), 'avellaneda': (-34.66, -58.37), 'lanus': (-34.7, -58.39), 'maldonado': (-34.9, -54.95), 'ciudad del este': (-25.51, -54.61),
  'puerto ordaz': (8.29, -62.72), 'barinas': (8.62, -70.21), 'valencia|ve': (10.16, -68.0), 'chimbote': (-9.07, -78.59), 'arequipa': (-16.4, -71.54),
  'iquique': (-20.21, -70.15), 'cochabamba': (-17.39, -66.16), 'santa cruz de la sierra': (-17.78, -63.18), 'mendoza': (-32.89, -68.83),
  'barranquilla': (10.96, -74.8), 'bucaramanga': (7.12, -73.12), 'caracas': (10.49, -66.88), 'guadalajara': (20.67, -103.35), 'tijuana': (32.51, -117.04),
  'sapporo': (43.06, 141.35), 'aomori': (40.82, 140.74), 'nantong': (32.0, 120.86), 'nanning': (22.82, 108.32), 'douala': (4.05, 9.7),
  'bandung': (-6.91, 107.61), 'surabaya': (-7.25, 112.75), 'craiova': (44.32, 23.8), 'enschede': (52.22, 6.9), 'cesena': (44.14, 12.24),
  'wiesbaden': (50.08, 8.24), 'dortmund': (51.51, 7.47), 'trieste': (45.65, 13.78), 'rimini': (44.06, 12.57), 'modena': (44.65, 10.93),
  'rotterdam': (51.92, 4.48), 'sanremo': (43.82, 7.78), 'palermo': (38.12, 13.36), 'pamplona': (42.81, -1.64), 'albacete': (38.99, -1.86),
  'vigo': (42.24, -8.72), 'porto': (41.15, -8.61), 'lille': (50.63, 3.06), 'paris': (48.86, 2.35), 'bilbao': (43.26, -2.93), 'manchester': (53.48, -2.24),
  'bremen': (53.08, 8.8), 'gelsenkirchen': (51.51, 7.1)}
gc = geonamescache.GeonamesCache()

def limpa(c):
    if not c: return None
    c = re.split(r'\.\s*Est[áa]dio', c)[0]
    c = c.replace(' - ', ', ').replace(';', '').strip().rstrip(',.').strip()
    c = re.sub(r'\s+', ' ', c).replace(' ,', ',')
    if c.lower() in ('não identificado', 'nao identificado') or re.search(r'\d{4}', c): return None
    if c == 'Belo Horizonte': c = 'Belo Horizonte, MG'
    FIX = {'Rio de Janeiro, MG': 'Rio de Janeiro, RJ', 'Joinvile, SC': 'Joinville, SC', 'Belo Horizontino, MG': 'Belo Horizonte, MG', 'São Paulo, MG': 'São Paulo, SP',
      'Pium-hi, MG': 'Piumhi, MG', 'Recife, MG': 'Recife, PE', 'Belo Horizonte, RJ': 'Belo Horizonte, MG', 'Belo Horiznte, MG': 'Belo Horizonte, MG',
      'Santa Bárbara do Oeste, SP': "Santa Bárbara d'Oeste, SP", 'Cachoeiro do Itapemirim, ES': 'Cachoeiro de Itapemirim, ES', 'Florianópolis, MG': 'Florianópolis, SC',
      'Teófilo Ottoni, MG': 'Teófilo Otoni, MG', 'Capecó, SC': 'Chapecó, SC', 'Belo Jorizonte, MG': 'Belo Horizonte, MG', 'Horizonte, MG': 'Belo Horizonte, MG',
      'Curitiba, MG': 'Curitiba, PR', 'Belo Hozizonte, MG': 'Belo Horizonte, MG', 'Venda Nova, MG': 'Belo Horizonte, MG'}
    c = re.sub(r'\s+', ' ', c.replace(' - ', ', ')).strip().rstrip(',.').strip()
    c = FIX.get(c, c)
    p = [x.strip() for x in c.split(',')]
    if len(p) >= 2 and p[-1].upper() in UF: return f'{p[0]}, {p[-1].upper()}'
    if len(p) >= 2 and sem(p[-1]) in PAIS:
        nome = {'cali': 'Cali', 'kwait': 'Kuwait'}.get(sem(p[0]), p[0])
        return f'{nome}, {PAIS[sem(p[-1])][0]}'
    return c

# 0) estádio com público/renda colados ("Mineirão. Pagantes: 22.712 pagantes - Renda: ...")
lim_est = 0
for j in J:
    e = j.get('estadio')
    if not e: continue
    m = re.match(r'^(.*?)\.\s*(P[uùú]b?l?i?co|Pagantes|P[uú]bico|Renda|P[uú]blico e Renda)\b(.*)$', e)
    if m:
        j['estadio'] = m.group(1).strip()
        n = re.search(r'([\d.]{3,})\s*(pagantes|presentes)', m.group(3))
        if n and j.get('publico') is None:
            j['publico'] = int(n.group(1).replace('.', '')); j['publico_tipo'] = n.group(2)
        lim_est += 1
print('estádios limpos:', lim_est)
# 1) limpa e completa pela maioria do estádio
for j in J: j['cidade'] = limpa(j.get('cidade'))
por_est = defaultdict(Counter)
for j in J:
    if j.get('cidade') and j.get('estadio'): por_est[j['estadio']][j['cidade']] += 1
comp = 0
for j in J:
    if not j.get('cidade') and j.get('estadio') in por_est:
        j['cidade'] = por_est[j['estadio']].most_common(1)[0][0]; j['cidade_inferida'] = True; comp += 1

# 2) coordenadas
mun = {}
cod_uf = {r[next(iter(r))]: r['uf'] for r in csv.DictReader(open(f'{GEO}/estados.csv', encoding='utf-8-sig'))}
for r in csv.DictReader(open(f'{GEO}/municipios.csv', encoding='utf-8')):
    mun[(sem(r['nome']), cod_uf[r['codigo_uf']])] = (float(r['latitude']), float(r['longitude']))
APEL_BR = {('ipatinga', 'MG'): None, ('sao joao del rei', 'MG'): ('sao joao del rei', 'MG'), ('sao joao del-rei', 'MG'): ('sao joao del rei', 'MG')}
cid = {}; falta = Counter()
for j in J:
    c = j.get('cidade')
    if not c or c in cid: continue
    nome, reg = [x.strip() for x in c.rsplit(',', 1)]
    if reg in UF:
        k = (sem(nome).replace('-', ' '), reg)
        ll = mun.get(k) or mun.get((sem(nome), reg))
        if not ll:
            cand = [v for (n, u), v in mun.items() if u == reg and (n.startswith(k[0]) or k[0].startswith(n))]
            ll = cand[0] if len(cand) == 1 else None
        ll = ll or FIXO.get(sem(nome))
        if ll: cid[c] = {'lat': ll[0], 'lon': ll[1], 'uf': reg, 'pais': 'Brasil', 'iso3': 'BRA', 'estado': UFN[reg]}
        else: falta[c] += 1
    else:
        pad = next((v for v in PAIS.values() if v[0] == reg), None)
        if not pad: falta[c] += 1; continue
        s = sem(nome); ll = FIXO.get(s) or FIXO.get(f'{s}|{pad[1].lower()}')
        if not ll:
            r = [x for x in gc.search_cities(ALIAS.get(s, nome)) if x['countrycode'] == pad[1]]
            r.sort(key=lambda x: -x['population'])
            if r: ll = (r[0]['latitude'], r[0]['longitude'])
        if ll: cid[c] = {'lat': round(ll[0], 3), 'lon': round(ll[1], 3), 'uf': None, 'pais': pad[0], 'iso3': pad[2], 'estado': None}
        else: falta[c] += 1
print('cidades com coordenada:', len(cid), '| sem:', sum(falta.values()), 'jogos ->', falta.most_common(25), '| completadas pelo estádio:', comp)

# 3) mapas (SVG paths pré-projetados)
def rdp(pts, eps):
    if len(pts) < 3: return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-9
    i, dm = 0, -1
    for k in range(1, len(pts) - 1):
        d = abs(dy * pts[k][0] - dx * pts[k][1] + x2 * y1 - y2 * x1) / L
        if d > dm: i, dm = k, d
    if dm > eps: return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]
def paths(geom, proj, eps):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    out = []
    for poly in polys:
        ring = [proj(x, y) for x, y in poly[0]]
        h = len(ring) // 2
        ring = rdp(ring[:h + 1], eps)[:-1] + rdp(ring[h:], eps)
        if len(ring) < 4: continue
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        if max(xs) - min(xs) < eps * 2 and max(ys) - min(ys) < eps * 2: continue
        out.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in ring) + 'Z')
    return ''.join(out)
# Brasil: equiretangular com cos(-15°), recorte -74..-34 / 6..-34
kx = math.cos(math.radians(15)); W = 600
bx0, bx1, by0, by1 = -74.2, -34.6, 5.4, -33.9
sc = W / ((bx1 - bx0) * kx)
pbr = lambda lon, lat: ((lon - bx0) * kx * sc, (by0 - lat) * sc)
H = (by0 - by1) * sc
br = json.load(open(f'{GEO}/br.geojson', encoding='utf-8'))
mapa_br = {}
for f in br['features']:
    uf = f['properties'].get('sigla') or f['properties'].get('UF') or f['properties'].get('abbreviation')
    if not uf:
        nm = sem(f['properties'].get('name', ''))
        uf = next((k for k, v in UFN.items() if sem(v) == nm), None)
    mapa_br[uf] = paths(f['geometry'], pbr, 0.6)
# Mundo: equiretangular simples, 1000 x 500, sem Antártida
pw = lambda lon, lat: ((lon + 180) / 360 * 1000, (90 - lat) / 180 * 500)
wo = json.load(open(f'{GEO}/world.geojson', encoding='utf-8'))
mapa_w = {}
for f in wo['features']:
    if f['id'] == 'ATA': continue
    mapa_w[f['id']] = paths(f['geometry'], pw, 0.7)
for c, v in cid.items():
    if v['pais'] == 'Brasil': v['bx'], v['by'] = [round(t, 1) for t in pbr(v['lon'], v['lat'])]
    v['wx'], v['wy'] = [round(t, 1) for t in pw(v['lon'], v['lat'])]
G['geo'] = {'cidades': cid, 'br': {'w': W, 'h': round(H), 'uf': mapa_br, 'nomes': UFN}, 'mundo': {'w': 1000, 'h': 500, 'p': mapa_w}}
json.dump(G, open(GJ, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('br paths', sum(len(v) for v in mapa_br.values()), 'mundo', sum(len(v) for v in mapa_w.values()), 'estados', len(mapa_br), [k for k in mapa_br if not k])
