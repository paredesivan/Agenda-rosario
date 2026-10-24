"""Genera HTML factual y URLs por función; no consulta ni copia páginas externas."""
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo

SITIO = 'https://salidasrosario.com.ar'
INICIO = '<!-- AGENDA ESTATICA INICIO -->'
FIN = '<!-- AGENDA ESTATICA FIN -->'


def escapar(valor):
    return html.escape(str(valor or ''), quote=True)


def ruta_evento(e):
    from actualizar_eventos import normalizar
    identidad = [e['fecha'], e['hora'], normalizar(e['nombre']).strip(), normalizar(e['lugar']).strip()]
    digest = hashlib.sha256(json.dumps(identidad, ensure_ascii=False).encode()).hexdigest()[:20]
    return f'fichas/{digest}.html'


def estructurado(e, url):
    # No inventar medianoche, disponibilidad, estado confirmado ni precios.
    if e.get('horario_pendiente') or e.get('revision_pendiente') or not re.fullmatch(r'\d{2}:\d{2}', e['hora']):
        return None
    valor = {'@context': 'https://schema.org', '@type': 'Event', 'name': e['nombre'], 'url': url,
             'startDate': f"{e['fecha']}T{e['hora']}:00-03:00",
             'location': {'@type': 'Place', 'name': e['lugar']}}
    if e.get('direccion'):
        valor['location']['address'] = {'@type': 'PostalAddress', 'streetAddress': e['direccion'],
                                       'addressLocality': 'Rosario', 'addressRegion': 'Santa Fe', 'addressCountry': 'AR'}
    return valor


def documento(titulo, contenido, canonical, schema=None):
    datos = ''
    if schema:
        seguro = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        datos = '<script type="application/ld+json">'+seguro+'</script>'
    return ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escapar(titulo)} · Salidas Rosario</title>'
            f'<link rel="canonical" href="{escapar(canonical)}">'
            '<link rel="stylesheet" href="/estilos.css">'+datos+'</head><body>'
            '<header><a href="/">Salidas Rosario</a></header><main>'+contenido+'</main>'
            '<footer>Las actividades pueden cambiar. Consultá siempre la fuente.</footer></body></html>\n')


def enlace(e):
    return f'<a href="/{ruta_evento(e)}">{escapar(e["nombre"])}</a>'


def ficha(e):
    contenido = (f'<article><h1>{escapar(e["nombre"])}</h1>'
                 f'<p><time datetime="{escapar(e["fecha"])}">{escapar(e["fecha"])}</time> · {escapar(e["hora"])}</p>'
                 f'<p>{escapar(e["lugar"])}</p><p>{escapar(e.get("direccion"))}</p>')
    if e.get('revision_pendiente'):
        contenido += '<p>Información conservada de una consulta anterior; pendiente de nueva verificación.</p>'
    precio = e.get('precio')
    etiqueta = e.get('precio_etiqueta') or ('Gratis' if precio == 0 else f'${precio:g}' if precio is not None else 'Consultar precio en la fuente')
    contenido += f'<p>{escapar(etiqueta)}</p>'
    url = e.get('evento_url')
    if url:
        contenido += f'<p><a href="{escapar(url)}" rel="noopener noreferrer">Consultar fuente: {escapar(e.get("origen") or "publicación original")}</a></p>'
    destino = e.get('direccion') or e['lugar']
    mapa = 'https://www.google.com/maps/search/?api=1&query='+quote(destino+', Rosario, Santa Fe, Argentina')
    contenido += f'<p><a href="{escapar(mapa)}">Ver mapa</a></p></article><p><a href="/fichas/">Ver todas las actividades</a></p>'
    return documento(e['nombre'], contenido, SITIO+'/'+ruta_evento(e), estructurado(e, SITIO+'/'+ruta_evento(e)))


def generar(root, hoy=None):
    from actualizacion_segura import validar
    from actualizar_eventos import sin_repetidos
    root = Path(root)
    datos = validar(json.loads((root/'eventos.json').read_text(encoding='utf-8')))
    from fuentes_adicionales import acr_vigente
    momento = datetime.fromisoformat(hoy+'T00:00:00-03:00') if hoy else datetime.now(ZoneInfo('America/Argentina/Cordoba'))
    hoy = hoy or momento.date().isoformat()
    eventos = sorted(sin_repetidos([e for e in datos['eventos'] if e['fecha'] >= hoy and
                                  (e.get('origen') != 'Agenda Cultural Rosario' or acr_vigente(e, momento))]),
                     key=lambda e:(e['fecha'], e['hora'], e['nombre'], e['lugar']))
    salidas = {ruta_evento(e): ficha(e) for e in eventos}
    lista = '<ul>'+''.join(f'<li>{escapar(e["fecha"])} · {escapar(e["hora"])} · {enlace(e)} · {escapar(e["lugar"])}</li>' for e in eventos)+'</ul>'
    salidas['fichas/index.html'] = documento('Todas las actividades', '<h1>Actividades en Rosario</h1>'+lista, SITIO+'/fichas/')
    urls = [SITIO+'/', SITIO+'/fichas/'] + [SITIO+'/'+ruta_evento(e) for e in eventos]
    salidas['sitemap.xml'] = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+xml_escape(u)+'</loc></url>' for u in urls)+'</urlset>\n'
    entrada = (root/'index.html').read_text(encoding='utf-8')
    bloque = (INICIO+'\n<section id="static-agenda" aria-label="Próximas actividades">'
              '<h2>Próximas actividades en Rosario</h2><p>Consultá las fechas y condiciones en la fuente de cada actividad.</p><ul>'+
              ''.join(f'<li>{escapar(e["fecha"])} · {escapar(e["hora"])} · {enlace(e)}</li>' for e in eventos[:15])+
              '</ul><p><a href="/fichas/">Ver todas las actividades</a></p></section>\n'+FIN)
    if INICIO in entrada and FIN in entrada:
        entrada = entrada[:entrada.index(INICIO)]+bloque+entrada[entrada.index(FIN)+len(FIN):]
    else:
        raise ValueError('Faltan marcadores de la agenda estática en index.html')
    anterior_path = root/'.agenda/paginas_generadas.json'
    anterior = json.loads(anterior_path.read_text()) if anterior_path.exists() else {}
    # Sólo tocar archivos propios. Un archivo editado manualmente exige revisión.
    for nombre, digest in anterior.items():
        if nombre != 'sitemap.xml' and not re.fullmatch(r'fichas/(?:index|[a-f0-9]{20})\.html', nombre):
            raise ValueError('Ruta inválida en el registro de páginas')
        p = root/nombre
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('Página generada modificada manualmente: '+nombre)
    for nombre in salidas:
        if (root/nombre).exists() and nombre not in anterior:
            raise ValueError('La página ya existe y no pertenece al generador: '+nombre)
    for nombre, contenido in salidas.items():
        p=root/nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenido, encoding='utf-8')
    for nombre in set(anterior)-set(salidas):
        (root/nombre).unlink(missing_ok=True)
    (root/'index.html').write_text(entrada, encoding='utf-8')
    anterior_path.parent.mkdir(exist_ok=True)
    anterior_path.write_text(json.dumps({n:hashlib.sha256(c.encode()).hexdigest() for n,c in salidas.items()}, indent=2)+'\n')
    return {'funciones': len(eventos), 'paginas': len(salidas), 'schemas': sum(estructurado(e, '') is not None for e in eventos)}


if __name__ == '__main__':
    print(json.dumps(generar(Path(__file__).resolve().parent), ensure_ascii=False))
