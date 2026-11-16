"""Monta site/index.html: template + app.js + base JSON embutida (abre sem servidor)."""
import sys
import json, os
tpl, app, data, out = sys.argv[1:5]
aceitos = sys.argv[5] if len(sys.argv) > 5 else None
s = open(tpl, encoding='utf-8').read()
_ex = os.path.join(os.path.dirname(app), 'extra.js')
src = open(app, encoding='utf-8').read() + ('\n' + open(_ex, encoding='utf-8').read() if os.path.exists(_ex) else '')
s = s.replace('<script>/*APP*/</script>', '<script>\n' + src + '\n</script>')
db = json.load(open(data, encoding='utf-8'))
if aceitos: db['aceitos'] = json.load(open(aceitos, encoding='utf-8'))
import os
if os.path.exists('data/proximo.json'): db['proximo'] = json.load(open('data/proximo.json', encoding='utf-8'))
if os.path.exists('data/escudos_web.json'): db['escudos'] = json.load(open('data/escudos_web.json', encoding='utf-8'))
d = json.dumps(db, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
s = s.replace('<script type="application/json" id="db">{}</script>', '<script type="application/json" id="db">' + d + '</script>')
open(out, 'w', encoding='utf-8').write(s)
