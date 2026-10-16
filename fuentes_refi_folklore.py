"""Descubre funciones nuevas; no contiene títulos, fechas ni slugs de eventos.

RefiTicket: catálogo público usado por home.js + selector real de funciones.
Rosario Folklore: conector opt-in; sus términos exigen permiso previo.
Guarda sólo campos factuales y enlaces, nunca afiches ni descripciones ajenas.
"""
import json
import re
import unicodedata
from html import unescape
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from fuentes_adicionales import Acceso

ROOT = Path(__file__).resolve().parent
ZONA = ZoneInfo('America/Argentina/Cordoba')
CONFIG = ROOT / 'fuentes_refi_folklore.json'
CACHE = ROOT / 'cache_refi_folklore.json'
ORIGEN_REFI = 'RefiTicket'
ORIGEN_FOLK = 'Rosario Folklore'


def norm(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', str(v).lower())
                           if unicodedata.category(c) != 'Mn').split())


def texto(nodo):
    return nodo.get_text(' ', strip=True) if nodo else ''


def categorias_factuales(titulo, descripcion, tipo=''):
    # Se analiza transitoriamente el texto publicado; sólo se guarda la etiqueta.
    valor = norm(titulo + ' ' + texto(BeautifulSoup(unescape(descripcion or ''), 'html.parser')))
    reglas = {
        'musica': r'\b(musica|musical|recital|concierto|disco|banda|rock|jazz|punk|dj|folklore|tango)\b',
        'teatro': r'\b(teatro|teatral|comedia|stand.up|unipersonal|humor)\b',
        'cine': r'\b(cine|pelicula|documental|cinematografico|proyeccion)\b',
        'libros': r'\b(libro|lectura|literatura|poesia|charla|conferencia)\b',
        'danza': r'\b(danza|ballet|baile|milonga)\b',
        'infancias': r'\b(infantil|infancias|ninos|ninas|titeres)\b',
    }
    etiquetas = [k for k, patron in reglas.items() if re.search(patron, valor)]
    tipos = tipo if isinstance(tipo, list) else [tipo]
    for k, categoria in {'MusicEvent': 'musica', 'TheaterEvent': 'teatro', 'ScreeningEvent': 'cine', 'DanceEvent': 'danza'}.items():
        if k in tipos and categoria not in etiquetas:
            etiquetas.append(categoria)
    return etiquetas


def guardar(path, datos):
    temporal = path.with_suffix(path.suffix + '.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporal.replace(path)


def enlace_local(base, href):
    url = urljoin(base, str(href))
    p, b = urlsplit(url), urlsplit(base)
    if p.scheme != 'https' or p.netloc != b.netloc or p.username or p.password:
        raise ValueError('Enlace externo o inseguro')
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


class Consulta(Acceso):
    """Reutiliza robots, pausas 403/429, User-Agent y ritmo del proyecto."""
    def leer_datos(self, url, parser, horas=2):
        dominio = urlsplit(url).hostname.removeprefix('www.')
        if self.cache.get('pausas', {}).get(dominio, 0) > self.reloj():
            raise ValueError('Fuente pausada por HTTP 403/429')
        paginas = self.cache.setdefault('paginas', {})
        previo = paginas.get(url)
        if previo and self.reloj() - previo['consultado'] < horas * 3600:
            return previo['datos']
        demora = self.robots(url)
        headers = {}
        if previo:
            if previo.get('etag'):
                headers['If-None-Match'] = previo['etag']
            if previo.get('last_modified'):
                headers['If-Modified-Since'] = previo['last_modified']
        respuesta = self.pedir(url, demora, headers)
        if respuesta.status_code == 304:
            if not previo:
                raise ValueError('304 sin datos previos')
            previo['consultado'] = self.reloj()
            return previo['datos']
        datos = parser(respuesta.text, url)
        paginas[url] = {'consultado': self.reloj(), 'datos': datos,
                        'etag': respuesta.headers.get('ETag'),
                        'last_modified': respuesta.headers.get('Last-Modified')}
        return datos


def catalogo_refi(contenido, url):
    datos = json.loads(contenido)
    if not isinstance(datos, dict) or not isinstance(datos.get('eventos'), list):
        raise ValueError('Cambió el catálogo público de RefiTicket')
    campos = ('nombre', 'slug', 'unica_fecha', 'desde_fecha', 'moneda',
              'entradas_online_desde', 'lugar', 'lugar_responsive', 'texto_precio_home')
    filas = [{k: f.get(k) for k in campos} for f in datos['eventos'] if isinstance(f, dict)]
    total = datos.get('cantidad_total_fechas_activas')
    if isinstance(total, int) and total > len(filas):
        raise ValueError('Catálogo truncado; no se publica una revisión incompleta')
    return filas


def schemas(obj):
    if isinstance(obj, list):
        for v in obj:
            yield from schemas(v)
    elif isinstance(obj, dict):
        tipos = obj.get('@type', [])
        tipos = [tipos] if isinstance(tipos, str) else tipos
        if isinstance(tipos, list) and any(t.endswith('Event') or t == 'Festival' for t in tipos if isinstance(t, str)):
            yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from schemas(v)


def instante(valor):
    if not isinstance(valor, str) or 'T' not in valor:
        raise ValueError('Fecha sin hora explícita')
    dt = datetime.fromisoformat(valor.replace('Z', '+00:00'))
    return dt.astimezone(ZONA) if dt.tzinfo else dt


def datos_ficha_refi(contenido, url):
    html = BeautifulSoup(contenido, 'html.parser')
    eventos = []
    for script in html.select('script[type="application/ld+json"]'):
        try:
            eventos.extend(schemas(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    # No mezclar funciones de recomendaciones u otros productos de la página.
    propios = [e for e in eventos if norm(e.get('offers', {}).get('url', url) if isinstance(e.get('offers'), dict) else e.get('url', url)).rstrip('/') == norm(url).rstrip('/')]
    ficha = propios[0] if propios else {}
    estado = str(ficha.get('eventStatus', ''))
    if any(v in estado for v in ('Cancelled', 'Postponed', 'Rescheduled')):
        return {'cancelado': True, 'fechas': []}
    loc = ficha.get('location', {})
    loc = loc if isinstance(loc, dict) else {}
    direccion = loc.get('address', {})
    direccion = direccion if isinstance(direccion, dict) else {}
    fechas = []
    selector = html.select_one('select#idFechasEventos')
    if selector:
        for opcion in selector.select('option'):
            if opcion.has_attr('disabled') or not str(opcion.get('value', '')).strip():
                continue
            try:
                dt = datetime.strptime(texto(opcion), '%d-%m-%Y, %H:%M')
            except ValueError:
                continue
            fechas.append(dt.isoformat(timespec='minutes'))
    elif ficha.get('startDate'):
        fechas.append(instante(ficha['startDate']).isoformat(timespec='minutes'))
    if not fechas and not selector:
        raise ValueError('Ficha sin selector ni fecha estructurada interpretable')
    return {'cancelado': False, 'fechas': list(dict.fromkeys(fechas)),
            'selector': selector is not None, 'lugar': loc.get('name', ''),
            'direccion': direccion.get('streetAddress', ''),
            'ciudad': direccion.get('addressLocality', ''),
            'provincia': direccion.get('addressRegion', ''),
            'categorias': categorias_factuales(str(ficha.get('name', '')), ficha.get('description', ''), ficha.get('@type', ''))}


def es_rosario(fila):
    # Evita Rosario del Tala y localidades del Gran Rosario.
    sede = norm(fila.get('lugar', ''))
    return bool(re.search(r',\s*rosario(?:,\s*santa fe)?$', sede))


def convertir_refi(fila, ficha, url, hoy, dias=30):
    if not es_rosario(fila) or ficha.get('cancelado'):
        return []
    if ficha.get('ciudad') and norm(ficha['ciudad']) != 'rosario':
        return []
    if ficha.get('provincia') and norm(ficha['provincia']) not in ('santa fe', 'santa fe province'):
        return []
    titulo = fila.get('nombre')
    lugar = ficha.get('lugar') or fila.get('lugar', '').split(',')[0]
    if not isinstance(titulo, str) or not titulo.strip() or not lugar:
        raise ValueError('Ficha sin nombre o sede')
    if fila.get('unica_fecha') is not True and not ficha.get('selector'):
        raise ValueError('Evento con múltiples funciones sin selector verificable')
    salida = []
    for valor in ficha.get('fechas', []):
        dt = instante(valor)
        if not hoy <= dt.date() <= hoy + timedelta(days=dias):
            continue
        precio = None
        if len(ficha['fechas']) == 1 and fila.get('moneda') == 'ARS':
            try:
                candidato = float(fila.get('entradas_online_desde'))
                if 0 < candidato < 50_000_000:
                    precio = candidato
            except (ValueError, TypeError):
                pass
        # El JSON-LD real puede decir price=0 aunque la venta tenga precio.
        # Nunca se interpreta ese cero como entrada gratuita.
        e = {'fecha': dt.date().isoformat(), 'hora': dt.strftime('%H:%M'),
             'nombre': titulo.strip(), 'lugar': lugar,
             'direccion': ', '.join(filter(None, [ficha.get('direccion'), 'Rosario, Santa Fe'])),
             'descripcion': '', 'evento_url': url, 'entradas_url': url,
             'origen': ORIGEN_REFI, 'precio': precio,
             'precio_etiqueta': f'Desde ${precio:,.0f}'.replace(',', '.') if precio else 'Consultar precio en RefiTicket',
             'fuente_verificada': True}
        if ficha.get('categorias'):
            e['categorias'] = ficha['categorias']
        salida.append(e)
    return salida


def listado_folklore(contenido, url):
    html = BeautifulSoup(contenido, 'html.parser')
    fichas, siguientes = [], []
    for a in html.select('a[href]'):
        try:
            link = enlace_local(url, a['href'])
        except ValueError:
            continue
        if urlsplit(link).path.startswith('/evento/') and not urlsplit(link).query:
            fichas.append(link)
        elif 'next' in a.get('rel', []) or norm(texto(a)) in ('siguientes', 'siguiente', 'siguientes →'):
            siguientes.append(link)
    return {'fichas': list(dict.fromkeys(fichas)), 'siguientes': list(dict.fromkeys(siguientes))}


def ficha_folklore(contenido, url):
    """Lee JSON-LD o metadatos visibles de la ficha, sin inferir el año."""
    html = BeautifulSoup(contenido, 'html.parser')
    main = html.select_one('main') or html
    resultado = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            for e in schemas(json.loads(tag.get_text())):
                loc = e.get('location', {})
                dom = loc.get('address', {}) if isinstance(loc, dict) else {}
                if isinstance(dom, dict) and norm(dom.get('addressLocality')) == 'rosario':
                    resultado.append({'nombre': e.get('name'), 'inicio': e.get('startDate'),
                                      'lugar': loc.get('name'), 'direccion': dom.get('streetAddress', ''),
                                      'estado': e.get('eventStatus', '')})
        except (ValueError, TypeError):
            continue
    if resultado:
        return resultado
    # Alternativa: el calendario iCalendar proporciona fecha completa y año.
    ics = main.select_one('a[href*="ics=1"], a[href$=".ics"]')
    return {'ics': enlace_local(url, ics['href'])} if ics else {'pendiente': 'sin metadatos de fecha completa'}


def datos_ics(contenido, url):
    lineas = re.sub(r'\r?\n[ \t]', '', contenido).splitlines()
    eventos, actual = [], None
    for linea in lineas:
        if linea == 'BEGIN:VEVENT':
            actual = {}
        elif linea == 'END:VEVENT' and actual is not None:
            eventos.append(actual)
            actual = None
        elif actual is not None and ':' in linea:
            k, v = linea.split(':', 1)
            actual[k] = v.replace('\\n', ' ').replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\')
    return eventos


def convertir_folk_schema(filas, url, hoy, dias):
    salida = []
    for f in filas:
        if any(s in str(f.get('estado')) for s in ('Cancelled', 'Postponed', 'Rescheduled')):
            continue
        dt = instante(f.get('inicio'))
        if not hoy <= dt.date() <= hoy + timedelta(days=dias):
            continue
        if not f.get('nombre') or not f.get('lugar'):
            raise ValueError('Nombre o sede pendientes')
        salida.append({'fecha': dt.date().isoformat(), 'hora': dt.strftime('%H:%M'),
                       'nombre': f['nombre'], 'lugar': f['lugar'], 'direccion': f.get('direccion', ''),
                       'descripcion': '', 'evento_url': url, 'origen': ORIGEN_FOLK,
                       'precio': None, 'precio_etiqueta': 'Consultar con el organizador',
                       'fuente_verificada': False})
    return salida


def convertir_folk_ics(filas, url, hoy, dias):
    schemas_filas = []
    for f in filas:
        if f.get('STATUS') == 'CANCELLED':
            continue
        inicio = next(((k, v) for k, v in f.items() if k.startswith('DTSTART')), None)
        if not inicio or 'RRULE' in f or 'RECURRENCE-ID' in f:
            raise ValueError('Calendario sin fecha/hora única verificable')
        k, v = inicio
        dt = datetime.strptime(v.rstrip('Z'), '%Y%m%dT%H%M%S' if len(v.rstrip('Z')) == 15 else '%Y%m%dT%H%M')
        if v.endswith('Z'):
            dt = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZONA)
        elif 'TZID=' in k:
            dt = dt.replace(tzinfo=ZoneInfo(k.split('TZID=', 1)[1])).astimezone(ZONA)
        loc = f.get('LOCATION', '')
        if not re.search(r'(?:^|,)\s*rosario(?:,\s*santa fe)?\s*$', norm(loc)):
            raise ValueError('Ciudad no confirmada por calendario')
        partes = loc.split(',')
        schemas_filas.append({'nombre': f.get('SUMMARY'), 'inicio': dt.isoformat(),
                              'lugar': partes[0].strip(), 'direccion': ','.join(partes[1:]).strip()})
    return convertir_folk_schema(schemas_filas, url, hoy, dias)


def revisar(config, hoy, acceso):
    nuevos, estado, exitosas, fallidos = [], {}, set(), set()
    dias = int(config.get('dias_futuros', 30))
    maximo = int(config.get('max_fichas_por_revision', 30))
    refi = config['refiticket']
    if refi.get('habilitada'):
        try:
            catalogo = acceso.leer_datos(refi['catalogo'], catalogo_refi)
            filas = [f for f in catalogo if es_rosario(f)]
            # Consulta también fichas con más de una función aunque la primera sea pasada.
            filas = [f for f in filas if f.get('unica_fecha') is not True or
                     hoy <= datetime.strptime(f.get('desde_fecha', ''), '%d/%m/%Y, %H:%M').date() <= hoy + timedelta(days=dias)]
            if len(filas) > maximo:
                raise ValueError('Límite de fichas excedido; revisión pendiente')
            for fila in filas:
                url = enlace_local(refi['base'], str(fila.get('slug', '')).strip('/') + '/')
                if not fila.get('slug'):
                    raise ValueError('Evento sin enlace')
                try:
                    ficha = acceso.leer_datos(url, datos_ficha_refi)
                    nuevos.extend(convertir_refi(fila, ficha, url, hoy, dias))
                except (requests.RequestException, ValueError, TypeError) as error:
                    fallidos.add(url)
            exitosas.add(ORIGEN_REFI)
            cantidad = sum(e['origen'] == ORIGEN_REFI for e in nuevos)
            estado[ORIGEN_REFI] = f'revisada: {cantidad} funciones; {len(fallidos)} fichas pendientes'
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[ORIGEN_REFI] = f'no accesible: {type(error).__name__}: {error}'
    folk = config['rosario_folklore']
    if not (folk.get('habilitada') and folk.get('permiso_automatizacion') and folk.get('referencia_permiso')):
        estado[ORIGEN_FOLK] = 'desactivada: falta permiso de automatización del titular'
    else:
        try:
            paginas, fichas, vistas = [folk['listado']], [], set()
            while paginas and len(vistas) < int(config.get('max_paginas_folklore', 3)):
                url = paginas.pop(0)
                if url in vistas:
                    continue
                vistas.add(url)
                listado = acceso.leer_datos(url, listado_folklore)
                fichas.extend(listado['fichas'])
                paginas.extend(u for u in listado['siguientes'] if u not in vistas)
            if paginas:
                raise ValueError('Paginación incompleta; revisión pendiente')
            fichas = list(dict.fromkeys(fichas))
            if not fichas or len(fichas) > maximo:
                raise ValueError('Listado vacío o límite de fichas excedido')
            for url in fichas:
                try:
                    datos = acceso.leer_datos(url, ficha_folklore)
                    if isinstance(datos, list):
                        nuevos.extend(convertir_folk_schema(datos, url, hoy, dias))
                    elif datos.get('ics'):
                        calendario = acceso.leer_datos(datos['ics'], datos_ics)
                        nuevos.extend(convertir_folk_ics(calendario, url, hoy, dias))
                    else:
                        raise ValueError('Fecha completa pendiente')
                except (requests.RequestException, ValueError, TypeError, KeyError) as error:
                    fallidos.add(url)
            exitosas.add(ORIGEN_FOLK)
            estado[ORIGEN_FOLK] = f'revisada: {sum(e["origen"] == ORIGEN_FOLK for e in nuevos)} funciones; {sum("rosariofolklore" in u for u in fallidos)} fichas pendientes'
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[ORIGEN_FOLK] = f'no accesible: {type(error).__name__}: {error}'
    return nuevos, estado, exitosas, fallidos


def misma_funcion(a, b):
    if (a.get('fecha'), a.get('hora')) != (b.get('fecha'), b.get('hora')):
        return False
    def limpio(v):
        return ' '.join(re.findall(r'\w+', norm(v)))
    na, nb = limpio(a.get('nombre', '')), limpio(b.get('nombre', ''))
    nombres = na == nb or min(len(na), len(nb)) >= 8 and (
        na in nb or nb in na or SequenceMatcher(None, na, nb).ratio() >= .92)
    la, lb = limpio(a.get('lugar', '')), limpio(b.get('lugar', ''))
    sede = bool(la and lb) and (la == lb or min(len(la), len(lb)) >= 4 and (la in lb or lb in la))
    return bool(nombres and sede)


def combinar(anteriores, nuevos, exitosas, fallidos, hoy):
    previos = [e for e in anteriores if e.get('fecha', '') >= hoy.isoformat() and
               (e.get('origen') not in exitosas or e.get('evento_url') in fallidos)]
    # Las fuentes primarias existentes prevalecen sobre el agregador secundario.
    for e in sorted(nuevos, key=lambda e: e.get('origen') == ORIGEN_FOLK):
        if not any(misma_funcion(e, p) for p in previos):
            previos.append(e)
    return sorted(previos, key=lambda e: (e['fecha'], e['hora'], e['nombre']))


def actualizar(root=ROOT, acceso=None, hoy=None):
    root = Path(root)
    ahora = datetime.now(ZONA)
    hoy = hoy or ahora.date()
    config = json.loads((root / CONFIG.name).read_text(encoding='utf-8'))
    archivo, cache_path = root / 'eventos.json', root / CACHE.name
    datos = json.loads(archivo.read_text(encoding='utf-8'))
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    except (ValueError, OSError):
        cache = {}
    acceso = acceso or Consulta(cache)
    nuevos, estado, exitosas, fallidos = revisar(config, hoy, acceso)
    datos['eventos'] = combinar(datos.get('eventos', []), nuevos, exitosas, fallidos, hoy)
    if fallidos or any('no accesible' in e for e in estado.values()):
        datos['estado'] = 'parcial'
    # No cambia la hora global de una agenda que no pudo actualizarse.
    if exitosas:
        datos['actualizado_fuentes_refi_folklore'] = ahora.strftime('%Y-%m-%d %H:%M')
    guardar(archivo, datos)
    guardar(cache_path, acceso.cache)
    registro_path = root / 'fuentes_revisadas.json'
    registro = json.loads(registro_path.read_text(encoding='utf-8')) if registro_path.exists() else {}
    registro.setdefault('fuentes', {}).update(estado)
    registro['revision_refi_folklore'] = ahora.strftime('%Y-%m-%d %H:%M')
    guardar(registro_path, registro)
    for fuente, resultado in estado.items():
        print(f'{fuente}: {resultado}', flush=True)
    return nuevos, estado


if __name__ == '__main__':
    actualizar()
