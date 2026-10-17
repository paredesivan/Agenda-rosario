"""Adaptadores de actividades públicas. Sin títulos, fechas ni fichas fijas."""
import json
import re
from datetime import date, datetime
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from fuentes_adicionales import norm
from fuentes_refi_folklore import categorias_factuales, enlace_local

MESES = {m: i for i, m in enumerate(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), 1)}
ABREV = dict(zip(('ene feb mar abr may jun jul ago sep oct nov dic').split(), range(1, 13)))
ABREV.update(jan=1, apr=4, aug=8, dec=12)


def texto(n):
    return n.get_text(' ', strip=True) if n else ''


def acceso_publico(t):
    t = norm(t)
    if re.search(r'exclusiv[oa]s? para|solo (?:para )?(?:socios|estudiantes|personal|profesionales)|unicamente para|actividad interna', t):
        raise ValueError('Actividad restringida: no publicar como abierta')
    if not re.search(r'entrada (?:es )?(?:libre|gratuita)|abiert[oa]s? (?:a|para) (?:toda )?la comunidad|publico en general|charla(?:s)? a la comunidad', t):
        raise ValueError('Acceso para público general no confirmado')


def condiciones(t):
    t = norm(t)
    datos = []
    if 'inscrib' in t or 'inscrip' in t:
        datos.append('Requiere inscripción en la fuente oficial.')
    if 'cupos limitados' in t:
        datos.append('Cupos limitados; consultar disponibilidad.')
    return ' '.join(datos)


def resultado(nombre, fecha, hora, sede, calle, cuerpo, fin=None):
    if not nombre or not sede or not calle:
        raise ValueError('Faltan título, sede o dirección')
    datetime.strptime(hora, '%H:%M')
    gratuito = bool(re.search(r'sin cargo|entrada (?:es )?(?:libre y gratuita|gratuita)|actividad gratuita', norm(cuerpo)))
    return {'cancelado': False, 'nombre': nombre, 'fecha': fecha.isoformat(),
            'hora': hora, 'lugar': sede, 'direccion': calle,
            'categorias': categorias_factuales(nombre, '', ''),
            'descripcion': condiciones(cuerpo), 'acceso': 'Público general',
            'precio': 0 if gratuito else None,
            'precio_etiqueta': 'Gratis' if gratuito else 'Consultar precio en la fuente',
            **({'fecha_fin': fecha.isoformat(), 'hora_fin': fin} if fin else {})}


def ficha_gamma(contenido, url, fuente):
    s = BeautifulSoup(contenido, 'html.parser')
    a = s.select_one('main article')
    if not a or not a.select_one('h1'):
        raise ValueError('Cambió la ficha de charla')
    titulo = texto(a.select_one('h1'))
    encabezado = a.select_one('h1').parent
    if 'charlas a la comunidad' not in norm(texto(encabezado)):
        raise ValueError('No pertenece a charlas para la comunidad')
    meta = a.select_one('ul')
    filas = [texto(li) for li in meta.select('li')] if meta else []
    if len(filas) != 3 or 'presencial' not in norm(filas[2]):
        raise ValueError('Ficha sin fecha, sede o modalidad presencial verificables')
    cuerpo = texto(a.select_one('section.markdown'))
    if any('inscrib' in norm(texto(x)) for x in encabezado.select('a,button')):
        cuerpo += ' Requiere inscripción.'
    acceso_publico(texto(encabezado) + ' ' + cuerpo)
    if re.search(r'\b(?:cancelad[oa]|suspendid[oa]|postergad[oa])\b', norm(titulo + ' ' + cuerpo)):
        return [{'cancelado': True}]
    m = re.fullmatch(r'(\d{1,2}) de (\w+) de (\d{4})\s*[-–]\s*(\d{1,2}:\d{2})(?:\s*a\s*(\d{1,2}:\d{2}))?\s*hs\.?', norm(filas[0]))
    if not m or m[2] not in MESES:
        raise ValueError('Fecha completa u horario no interpretables')
    fecha = date(int(m[3]), MESES[m[2]], int(m[1]))
    inicio = datetime.strptime(m[4], '%H:%M').strftime('%H:%M')
    fin = datetime.strptime(m[5], '%H:%M').strftime('%H:%M') if m[5] else None
    if fin and fin <= inicio:
        raise ValueError('Fin anterior al inicio; requiere revisión')
    lugar = re.fullmatch(r'(.+?)\s*\(([^()]+),\s*Rosario\)', filas[1], re.I)
    if not lugar:
        raise ValueError('Sede y dirección en Rosario no confirmadas')
    e = resultado(titulo, fecha, inicio, lugar[1].strip(), lugar[2].strip(), cuerpo, fin)
    return [e]


def ficha_mec(contenido, url, fuente):
    s = BeautifulSoup(contenido, 'html.parser')
    a = s.select_one('article.mec-single-event')
    cuerpo = texto(a.select_one('.mec-single-event-description')) if a else ''
    titulo = texto(a.select_one('h1')) if a else ''
    if not cuerpo or not titulo:
        raise ValueError('Ficha institucional sin contenido de evento identificable')
    acceso_publico(cuerpo)
    if re.search(r'\b(?:cancelad[oa]|suspendid[oa]|postergad[oa])\b', norm(titulo + ' ' + cuerpo)):
        return [{'cancelado': True}]
    # El año pertenece a la tarjeta del MISMO evento; nunca a datePublished.
    fechas = set()
    for tarjeta in s.select('article.mec-event-article'):
        enlaces = tarjeta.select('.mec-event-title a[href]')
        if not any(enlace_local(url, x['href']).rstrip('/') == url.rstrip('/') for x in enlaces if urlsplit(x['href']).netloc in ('', urlsplit(url).netloc)):
            continue
        raw = texto(tarjeta.select_one('.mec-start-date-label'))
        if tarjeta.select_one('.mec-end-date-label'):
            raise ValueError('Actividad de varios días: falta cronograma de funciones')
        m = re.fullmatch(r'([A-Za-z]{3}) (\d{1,2}) (\d{4})', raw)
        if m and norm(m[1]) in ABREV:
            fechas.add(date(int(m[3]), ABREV[norm(m[1])], int(m[2])))
    # Fecha íntegra en el cuerpo también es válida, sin inferir el año actual.
    for m in re.finditer(r'\b(\d{1,2}) de (\w+) de (\d{4})\b', norm(cuerpo)):
        if m[2] in MESES:
            fechas.add(date(int(m[3]), MESES[m[2]], int(m[1])))
    if len(fechas) != 1:
        raise ValueError('Falta fecha única y completa del evento')
    fecha = next(iter(fechas))
    # Debe coincidir día/mes visible y contener una sola hora explícita.
    dias = {(int(m[1]), MESES[m[2]]) for m in re.finditer(r'\b(\d{1,2}) de (\w+)\b', norm(cuerpo)) if m[2] in MESES}
    horas = set(re.findall(r'\ba las\s+(\d{1,2})(?::(\d{2}))?\s*(?:hs?\.?|horas)\b', norm(cuerpo)))
    if dias != {(fecha.day, fecha.month)} or len(horas) != 1:
        raise ValueError('Cronograma ambiguo o sin hora explícita')
    h, mi = next(iter(horas))
    hora = f'{int(h):02d}:{mi or "00"}'
    # No usar domicilio de la institución por defecto: verificarlo en el cuerpo.
    lineas = [texto(p) for p in a.select('.mec-single-event-description p')]
    posibles = [p for p in lineas if re.search(r',\s*[^,]+\s+\d+[A-Za-z]?,\s*Rosario\.?$', p, re.I)]
    if len(posibles) != 1:
        raise ValueError('Sede y dirección no verificables en el cuerpo')
    p = posibles[0]
    calle = p.rsplit(',', 2)[1].strip()
    sede = re.search(r'(?:en el|en la|lugar:|sede:)\s+(.+?),\s*' + re.escape(calle), p, re.I)
    if not sede:
        raise ValueError('Nombre de la sede no verificable')
    return [resultado(titulo, fecha, hora, sede[1].strip(), calle, cuerpo)]
