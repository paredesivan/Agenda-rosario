from pathlib import Path
import json
r=Path(__file__).resolve().parent
p=r/'fuentes_ampliadas.py';s=p.read_text()
if "if fuente['adaptador'] == 'aec_teatro':" not in s:
 anchor='def ficha(contenido, url, fuente):\n'
 if s.count(anchor)!=1:raise SystemExit('No se encontró un punto único de integración AEC')
 s=s.replace(anchor,anchor+"    if fuente['adaptador'] == 'aec_teatro':\n        from fuente_aec import ficha_aec\n        return ficha_aec(contenido, url, fuente)\n")
anchor='        coincidencias = [p for p in salida if misma_funcion(e, p)]'
if anchor in s:s=s.replace(anchor,"        from fuente_aec import misma_sala_aec\n        coincidencias = [p for p in salida if misma_funcion(e, p) or misma_sala_aec(e, p)]")
p.write_text(s)
p=r/'fuentes_ampliadas.json';d=json.loads(p.read_text());url='https://www.aecrosario.org.ar/cultura/teatro/'
if not any(f.get('listado')==url for f in d['fuentes']):
 d['fuentes'].append({'nombre':'Empleados de Comercio Rosario — Teatro AEC','listado':url,'adaptador':'aec_teatro','tipo':'oficial','habilitada':True,'patron_ficha':'^/[^/]+/?$','selector':'h3.pre-post-title a[href]','cache_horas':2,'motivo':'HTML y robots públicos verificados 18/10/2026. Sala abierta a todo público. Gratuidad para afiliados no se extiende a público general; no cursos ni eventos fijos.'})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=r/'.github/workflows/actualizar.yml';s=p.read_text()
for nombre in ['fuente_aec.py','instalar_fuente_aec.py']:
 if '      - '+nombre+'\n' not in s:s=s.replace('      - fuentes_ampliadas.py\n','      - fuentes_ampliadas.py\n      - '+nombre+'\n')
p.write_text(s)
