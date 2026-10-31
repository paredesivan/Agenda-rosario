"""Lectores de carteleras oficiales HTML; fechas explícitas, sin eventos fijos."""
import json
import re
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
import requests
from cobertura_fuentes import HORIZONTE_DIAS
from descubrimiento_html import descubrir, huella_html, seleccionar, combinar

MESES = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
EXCLUIDOS = re.compile(r'^(?:curso|taller|seminario|convocatoria|residencia|profesorado)\b')


def texto(tag):
    return tag.get_text(' ', strip=True) if tag else ''


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def local(u, base):
    p, b = urlsplit(u), urlsplit(base)
    return p.scheme == 'https' and p.hostname == b.hostname and not p.username and not p.port


def anio_publicado(html):
    meta = html.select_one('meta[property="article:published_time"], time[datetime]')
    if meta:
        valor = meta.get('content') or meta.get('datetime', '')
        if re.match(r'20\d{2}-', valor):
            return int(valor[:4])
    visible = texto(html.select_one('.published, .post-meta'))
    m = re.search(r'\b(20\d{2})\b', visible)
    return int(m[1]) if m else None


def publicar_evento(crear, fecha, hora, titulo, url, fuente, direccion, descripcion, lugar=None):
    evento = crear(fecha, hora, titulo, url, fuente, direccion, descripcion, lugar)
    if 'biblioteca vigil' in norm(fuente):
        # El beneficio para socios no equivale a entrada gratuita general.
        lineas = descripcion.split('\n')
        generales = [x for x in lineas if re.search(r'general|anticipadas|en puerta', norm(x))]
        precio_texto = ' '.join(generales)
        otro = crear(fecha, hora, titulo, url, fuente, direccion, precio_texto, lugar)
        evento.update(precio=otro['precio'], precio_etiqueta=otro.get('precio_etiqueta', ''))
        if not generales:
            evento.update(precio=None, precio_etiqueta='Consultar precio para público general')
    elif 'parque de espana' in norm(fuente):
        general = re.search(r'\bgeneral\s*:?\s*(\$\s*[\d.,]+)', norm(descripcion))
        if general:
            otro = crear(fecha, hora, titulo, url, fuente, direccion, general[1], lugar)
            evento.update(precio=otro['precio'], precio_etiqueta='')
    return evento


def lineas_parrafo(p):
    copia = BeautifulSoup(str(p), 'html.parser')
    for br in copia.select('br'):
        br.replace_with('\n')
    return [' '.join(x.split()) for x in copia.get_text(' ').splitlines() if x.strip()]


def fechas_del_indice(html):
    fechas_indice = {}
    for script in html.select('script[type="application/ld+json"]'):
        try:
            dato = json.loads(script.get_text())
            if isinstance(dato, dict) and dato.get('url') and dato.get('startDate'):
                fechas_indice[dato['url']] = dato['startDate'][:10]
        except (ValueError, TypeError):
            pass
    return fechas_indice


def ccpe(html, fuente, url, direccion, hoy, descargar, crear, fechas, elegir=None):
    enlaces = descubrir(html, url, '.mec-event-title a[href]', descargar,
                        admitir=lambda a: not EXCLUIDOS.search(norm(texto(a.parent))))
    elegir = elegir or (lambda e, n: list(e.items())[:n])
    if not enlaces:
        raise ValueError('CCPE: la agenda no contiene fichas públicas reconocibles')
    eventos, fallidos = [], set()
    fechas_indice = fechas_del_indice(html)
    for link, titulo in elegir(enlaces, 16):
        if not local(link, url) or EXCLUIDOS.search(norm(titulo)):
            continue
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', fechas_indice.get(link, '')) and fechas_indice[link] < hoy.isoformat():
            continue
        try:
            detalle = descargar(link)
            cuerpo = detalle.select_one('.mec-single-event-description')
            if cuerpo and re.search(r'participar del taller|inscripcion al (?:curso|taller)|residencia de creacion', norm(texto(cuerpo)[:250])):
                continue
            fecha = texto(detalle.select_one('.mec-single-event-date .mec-start-date-label'))
            hora = texto(detalle.select_one('.mec-single-event-time .mec-events-abbr'))
            m = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b', fecha)
            h = re.match(r'(\d{1,2}):(\d{2})\b', hora)
            if not cuerpo or not m or not h:
                raise ValueError('CCPE: falta fecha, horario o descripción verificable')
            anio = int(m[3]); anio = anio + 2000 if anio < 100 else anio
            dia = date(anio, int(m[2]), int(m[1]))
            if int(h[1]) > 23 or int(h[2]) > 59:
                raise ValueError('CCPE: horario inválido')
            if hoy <= dia <= hoy + timedelta(days=HORIZONTE_DIAS):
                desc = texto(cuerpo)
                if not re.search(r'\b(?:evento|funcion|espectaculo)\s+(?:cancelado|suspendido)', norm(desc)):
                    eventos.append(publicar_evento(crear, dia.isoformat(), f'{int(h[1]):02d}:{h[2]}', titulo, link, fuente, direccion, desc))
        except (requests.RequestException, ValueError, TypeError, KeyError):
            # Cada ficha fallida queda identificada para conservar su respaldo.
            fallidos.add(link)
    return eventos, fallidos


def argentina(html, fuente, url, direccion, hoy, descargar, crear, fechas, elegir=None):
    enlaces = descubrir(html, url, 'article .entry-title a[href], h2.entry-title a[href], h3.entry-title a[href]', descargar)
    if not enlaces:
        raise ValueError('Biblioteca Argentina: falta el listado de publicaciones')
    eventos, fallidos = [], set()
    elegir = elegir or (lambda e, n: list(e.items())[:n])
    for link, titulo in elegir(enlaces, 12):
        if not local(link, url) or EXCLUIDOS.search(norm(titulo)) or 'profesorado' in norm(titulo):
            continue
        try:
            detalle = descargar(link)
            cuerpo = detalle.select_one('article .entry-content, .entry-content')
            if not cuerpo:
                raise ValueError('Biblioteca Argentina: ficha incompleta')
            # Excluir biografías, recomendaciones y navegación posterior.
            parrafos = cuerpo.select('p')
            anuncio = next((texto(p) for p in parrafos[:4] if not p.find_parent('blockquote') and
                           fechas(texto(p), hoy)), '')
            descripcion = texto(cuerpo)
            if re.search(r'(?:actividad|funcion|evento|presentacion|concierto)\s+(?:fue |esta |se encuentra )?(?:cancelad|suspendid|postergad)[oa]', norm(descripcion)):
                continue
            if not re.search(r'\b20\d{2}\b', anuncio) and anio_publicado(detalle) != hoy.year:
                continue
            for dia, hora in fechas(anuncio, hoy):
                if not re.search(r'\b(?:se realizo|se presento|se llevo a cabo)\b', norm(anuncio)):
                    eventos.append(publicar_evento(crear, dia, hora, titulo, link, fuente, direccion, descripcion))
        except (requests.RequestException, ValueError, TypeError, KeyError):
            fallidos.add(link)
    return eventos, fallidos


def funciones_vigil(html, url, hoy, crear, fechas):
    cuerpo = html.select_one('article .entry-content, .entry-content')
    if not cuerpo:
        raise ValueError('Vigil: falta el cuerpo de la noticia')
    temporada = re.search(r'temporada\s+(20\d{2})', norm(texto(cuerpo)))
    anio = int(temporada[1]) if temporada else anio_publicado(html)
    if not anio:
        return []
    contexto = texto(html.select_one('h1')) + ' ' + texto(cuerpo)[:500]
    if 'teatro vigil' not in norm(contexto):
        return []
    eventos, bloque = [], []
    def cerrar():
        if not bloque:
            return
        lineas = lineas_parrafo(bloque[0])
        patron = r'\b(\d{1,2}\s+(?:de\s+)?(?:'+ '|'.join(MESES) +r'))\b(?!\s*,?\s*(?:de\s+)?20\d{2})'
        anuncio = re.sub(patron, lambda m: m[1]+' de '+str(anio), norm(lineas[0]))
        turnos = fechas(anuncio, hoy)
        titulo = lineas[1] if len(lineas) > 1 else ''
        if not titulo and len(bloque) > 1:
            titulo = texto(bloque[1].select_one('strong'))
        if not titulo or EXCLUIDOS.search(norm(titulo)):
            return
        descripcion = '\n'.join(linea for p in bloque for linea in lineas_parrafo(p))
        if re.search(r'\b(?:cancelad|suspendid|postergad)[oa]\b', norm(lineas[0]+' '+titulo)):
            return
        for dia, hora in turnos:
            eventos.append(publicar_evento(crear, dia, hora, titulo.rstrip('.'), url,
                'Biblioteca Vigil', 'Alem 3086', descripcion, 'Teatro Vigil'))
    for p in cuerpo.select('p'):
        primera = lineas_parrafo(p)
        es_fecha = primera and re.search(r'\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+\d', norm(primera[0]))
        if es_fecha:
            cerrar(); bloque = [p]
        elif bloque:
            bloque.append(p)
    cerrar()
    return eventos


def vigil(html, fuente, url, direccion, hoy, descargar, crear, fechas, elegir=None):
    # El calendario MEC puede estar vacío aunque haya programación en noticias.
    portada_url = urljoin(url, '/inicio/')
    portada = html if html.select('article .entry-title a[href], article h2 a[href]') else descargar(portada_url)
    enlaces = descubrir(portada, portada_url, 'article h2 a[href], article .entry-title a[href]', descargar)
    if not enlaces:
        raise ValueError('Vigil: no se reconocen las noticias de la portada')
    eventos, fallidos = [], set()
    elegir = elegir or (lambda e, n: list(e.items())[:n])
    for link, titulo in elegir(enlaces, 4):
        if not local(link, portada_url):
            continue
        try:
            eventos.extend(funciones_vigil(descargar(link), link, hoy, crear, fechas))
        except (requests.RequestException, ValueError, TypeError, KeyError):
            fallidos.add(link)
    return eventos, fallidos


def adaptar(html, fuente, url, direccion, hoy, descargar, crear, fechas, cache_path):
    lectores = {'Centro Cultural Parque de España': ccpe,
                'Biblioteca Argentina Dr. Juan Álvarez': argentina, 'Biblioteca Vigil': vigil}
    if fuente == 'ATIR':
        vacios = html.select('.mec-calendar .mec-event-title')
        if vacios and all(norm(texto(x)) in ('no events', 'no hay eventos') for x in vacios):
            return [], set()
        return None
    if fuente not in lectores:
        return None
    path = Path(cache_path)
    cache = json.loads(path.read_text()) if path.exists() else {}
    anterior = cache.get(fuente, {})
    if fuente == 'Biblioteca Vigil':
        html = descargar(urljoin(url, '/inicio/'))
    huella = huella_html(html, url)
    ahora = time.time()
    pendientes = set(anterior.get('enlaces', {})) - set(anterior.get('intentos', {}))
    if not pendientes and ahora - anterior.get('consultado', 0) < 7200 and anterior.get('huella') == huella:
        return [e for e in anterior['eventos'] if hoy.isoformat() <= e['fecha'] <= (hoy+timedelta(days=HORIZONTE_DIAS)).isoformat()], set()
    consultadas = set()
    def consultar(link):
        consultadas.add(link)
        return descargar(link)
    def elegir(enlaces, limite):
        return seleccionar(enlaces, limite, anterior, ahora)
    nuevos, fallidos = lectores[fuente](html, fuente, url, direccion, hoy, consultar, crear, fechas, elegir)
    eventos = combinar(anterior.get('eventos', []), nuevos, consultadas, fallidos, hoy)
    cache[fuente] = {**anterior, 'consultado': ahora if not fallidos else 0,
        'huella': huella, 'eventos': eventos,
        'revision': {'enlaces_descubiertos': len(anterior.get('enlaces', {})),
                     'paginas_consultadas': sorted(consultadas), 'fichas_fallidas': sorted(fallidos)}}
    temporal = path.with_suffix('.tmp')
    temporal.write_text(json.dumps(cache, ensure_ascii=False))
    temporal.replace(path)
    return eventos, fallidos
