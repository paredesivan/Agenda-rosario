"""Descubrimiento acotado de hechos; publica sólo con respaldo oficial.

No descarga imágenes, APIs privadas ni bases completas. Un listado por fuente
cada dos horas; hasta cuatro notas de Rosario Times al día. HTTP 403/429 pausa
el dominio por al menos 24 horas. El caché conserva datos normalizados, no HTML.
"""
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
UA = 'AgendaRosario/3.0 (+https://paredesivan.github.io/Agenda-rosario/)'
LIMITES = {'listado': 7200, 'nota': 86400, 'robots': 604800}


def norm(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', str(value).lower())
                           if unicodedata.category(c) != 'Mn').split())


def host(url):
    return (urlsplit(url).hostname or '').removeprefix('www.')


def clave(e):
    return (e.get('fecha'), e.get('hora'), norm(e.get('nombre')), norm(e.get('lugar')))


def guardar(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


class Acceso:
    def __init__(self, cache, session=None, reloj=time.time, dormir=time.sleep):
        self.cache, self.session = cache, session or requests.Session()
        self.reloj, self.dormir, self.ultima = reloj, dormir, {}

    def pedir(self, url, demora=5, headers=None):
        dominio = host(url)
        self.ultima_url = url
        if self.cache.get('pausas', {}).get(dominio, 0) > self.reloj():
            raise ValueError('dominio pausado por respuesta anterior')
        espera = demora - (self.reloj() - self.ultima.get(dominio, 0))
        if espera > 0:
            self.dormir(espera)
        try:
            # Un único reintento ante fallos transitorios de transporte. No se
            # reintenta ante 403/429 ni se siguen redirecciones no auditadas.
            for intento in range(2):
                try:
                    r = self.session.get(url, headers={'User-Agent': UA, **(headers or {})},
                                         timeout=(8, 15), allow_redirects=False)
                    break
                except (requests.ConnectionError, requests.Timeout):
                    if intento:
                        raise
                    self.dormir(2)
            if r.status_code in (403, 429):
                pausa = 86400
                retry = r.headers.get('Retry-After', '')
                if retry.isdigit():
                    pausa = max(pausa, int(retry))
                elif retry:
                    try:
                        pausa = max(pausa, parsedate_to_datetime(retry).timestamp() - self.reloj())
                    except (ValueError, TypeError, OverflowError):
                        pass
                self.cache.setdefault('pausas', {})[dominio] = self.reloj() + pausa
            if 300 <= r.status_code < 400 and r.status_code != 304:
                raise ValueError('redirección pendiente de auditoría')
            r.raise_for_status()
            r.encoding = 'utf-8'
            return r
        finally:
            self.ultima[dominio] = self.reloj()

    def robots(self, url):
        robots_url = urljoin(url, '/robots.txt')
        registro = self.cache.setdefault('robots', {}).get(robots_url)
        if not registro or self.reloj() - registro['consultado'] >= LIMITES['robots']:
            try:
                r = self.pedir(robots_url)
            except requests.HTTPError as error:
                if error.response is None or error.response.status_code != 404:
                    raise
                # Ausencia verificada del archivo: sin reglas de exclusión
                # técnicas. No concede una licencia de reutilización.
                registro = {'consultado': self.reloj(), 'reglas': '', 'http': 404}
            else:
                if '<html' in r.text.lower() or '<!doctype' in r.text.lower():
                    raise ValueError('robots no interpretable')
                registro = {'consultado': self.reloj(), 'reglas': r.text, 'http': 200}
            self.cache['robots'][robots_url] = registro
        parser = RobotFileParser()
        parser.parse(registro['reglas'].splitlines())
        if not parser.can_fetch(UA, url):
            raise ValueError('ruta excluida por robots.txt')
        return max(5, parser.crawl_delay(UA) or 0)

    def leer(self, url, parser, tipo='listado'):
        # Aun con caché no se ignora una pausa activa.
        if self.cache.get('pausas', {}).get(host(url), 0) > self.reloj():
            raise ValueError('dominio pausado por HTTP 403/429')
        anterior = self.cache.setdefault('paginas', {}).get(url)
        if anterior and self.reloj() - anterior['consultado'] < LIMITES[tipo]:
            return anterior['datos']
        demora = self.robots(url)
        if tipo == 'nota':
            dia = datetime.fromtimestamp(self.reloj()).date().isoformat()
            clave_dia = host(url) + ':' + dia
            presupuestos = self.cache.setdefault('notas_diarias', {})
            for key in list(presupuestos):
                if not key.endswith(dia):
                    del presupuestos[key]
            consultadas = presupuestos.setdefault(clave_dia, [])
            if url not in consultadas:
                if len(consultadas) >= 4:
                    raise ValueError('límite de cuatro fichas diarias; revisar en próxima ejecución')
                consultadas.append(url)
        headers = {}
        if anterior:
            if anterior.get('etag'):
                headers['If-None-Match'] = anterior['etag']
            if anterior.get('last_modified'):
                headers['If-Modified-Since'] = anterior['last_modified']
        r = self.pedir(url, demora, headers)
        if r.status_code == 304 and anterior:
            anterior['consultado'] = self.reloj()
            return anterior['datos']
        if r.status_code == 304:
            raise ValueError('304 sin caché anterior')
        datos = parser(BeautifulSoup(r.text, 'html.parser'), url)
        self.cache['paginas'][url] = {'consultado': self.reloj(), 'datos': datos,
                                    'etag': r.headers.get('ETag'),
                                    'last_modified': r.headers.get('Last-Modified')}
        return datos


def schemas(obj):
    if isinstance(obj, list):
        for item in obj:
            yield from schemas(item)
    elif isinstance(obj, dict):
        tipo = obj.get('@type', '')
        tipos = [tipo] if isinstance(tipo, str) else tipo if isinstance(tipo, list) else []
        if any(t in ('Event', 'MusicEvent', 'TheaterEvent', 'Festival',
                     'ExhibitionEvent', 'ScreeningEvent', 'SportsEvent') for t in tipos):
            yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from schemas(value)


def hechos_schema(html, url):
    """Lista blanca de campos. Ignora precios de reventa, sinopsis y afiches."""
    from actualizar_eventos import ZONA
    hechos = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas = list(schemas(json.loads(tag.get_text())))
        except (ValueError, TypeError):
            continue
        for f in fichas:
            if any(x in str(f.get('eventStatus', '')) for x in ('Cancelled', 'Postponed', 'Rescheduled')):
                continue
            inicio = f.get('startDate')
            loc = f.get('location')
            if not isinstance(inicio, str) or 'T' not in inicio or not isinstance(loc, dict):
                continue
            domicilio = loc.get('address')
            if not isinstance(domicilio, dict):
                continue
            # Coincidencia exacta: no Rosario de otra provincia ni alrededores.
            if norm(domicilio.get('addressLocality')) != 'rosario':
                continue
            provincia = norm(domicilio.get('addressRegion', ''))
            if provincia and provincia not in ('santa fe', 'santa fe province'):
                continue
            try:
                momento = datetime.fromisoformat(inicio.replace('Z', '+00:00'))
                if momento.tzinfo:
                    momento = momento.astimezone(ZONA)
            except ValueError:
                continue
            titulo, lugar = f.get('name'), loc.get('name')
            if not isinstance(titulo, str) or not isinstance(lugar, str) or not titulo or not lugar:
                continue
            oferta = f.get('offers')
            link = f.get('url') or (oferta.get('url') if isinstance(oferta, dict) else '') or url
            if not isinstance(link, str) or urlsplit(link).scheme != 'https':
                link = url
            h = {'nombre': titulo, 'fecha': momento.date().isoformat(),
                 'hora': momento.strftime('%H:%M'), 'lugar': lugar,
                 'direccion': domicilio.get('streetAddress', ''), 'referencia': link}
            if isinstance(f.get('endDate'), str) and 'T' in f['endDate']:
                try:
                    fin = datetime.fromisoformat(f['endDate'].replace('Z', '+00:00'))
                    if fin.tzinfo:
                        fin = fin.astimezone(ZONA)
                    if fin > momento:
                        h['hora_fin'], h['fecha_fin'] = fin.strftime('%H:%M'), fin.date().isoformat()
                except (ValueError, TypeError):
                    pass
            hechos.append(h)
    return list({(e.get('fecha'), e.get('hora'), norm(e.get('nombre')),
                  firma_sede(e.get('lugar', ''))): e for e in hechos}.values())[:40]


def portada_times(html, url):
    refs = []
    for a in html.select('a.card__link[href]'):
        link = urljoin(url, a['href']).split('#')[0]
        # El titular sólo se usa transitoriamente para seleccionar la nota.
        valor = norm(a.get_text(' ', strip=True))
        if host(link) == host(url) and 'rosario' in valor and not re.search(
                r'participaron|se realizo|se celebro', valor) and re.search(
                r'musical|teatro|obra|recital|festival|concierto|feria|colectividades|espumantes|salon del automovil', valor):
            if link not in refs:
                refs.append(link)
    return refs[:12]


def nota_times(html, url):
    # No guarda titulares periodísticos ni párrafos; sólo hechos estructurados
    # y enlaces para encontrar la fuente oficial.
    cuerpo = html.select_one('article') or html.select_one('main') or html
    links = []
    for a in cuerpo.select('a[href]'):
        link = urljoin(url, a['href']).split('#')[0]
        if urlsplit(link).scheme == 'https' and host(link) != host(url):
            if link not in links:
                links.append(link)
    return {'hechos': hechos_schema(html, url), 'enlaces': links[:12]}


def listado_saleplan(html, url):
    hechos = hechos_schema(html, url)
    if hechos:
        return hechos
    # Sin año completo y sede no inferimos fechas del encabezado de la agenda.
    refs = []
    for a in html.select('article.event-card h2 a[href]'):
        link = urljoin(url, a['href'])
        if host(link) == host(url) and '/rosario/' in urlsplit(link).path:
            refs.append({'nombre': a.get_text(' ', strip=True), 'referencia': link,
                         'estado': 'fecha completa y sede pendientes de fuente oficial'})
    return refs[:24]


def listado_entradafan(html, url):
    """El listado expone fechas ISO en filas, además de JSON-LD parcial."""
    from actualizar_eventos import ZONA
    hechos = hechos_schema(html, url)
    for a in html.select('a.event-row-link[href]')[:40]:
        fecha = a.select_one('[itemprop="startDate"][content]')
        titulo = a.select_one('.event-title-text')
        titulo_bloque = a.select_one('.event-title-with-badge')
        lugar_nodo = titulo_bloque.find_next_sibling('span') if titulo_bloque else None
        lugar = lugar_nodo.get_text(' ', strip=True) if lugar_nodo else ''
        if not fecha or not titulo or not norm(lugar).endswith('rosario'):
            continue
        try:
            momento = datetime.fromisoformat(fecha['content'].replace('Z', '+00:00'))
            if 'T' not in fecha['content']:
                continue
            if momento.tzinfo:
                momento = momento.astimezone(ZONA)
        except ValueError:
            continue
        nombre = titulo.get_text(' ', strip=True)
        hechos.append({'nombre': nombre, 'fecha': momento.date().isoformat(),
                       'hora': momento.strftime('%H:%M'), 'lugar': lugar,
                       'direccion': '', 'referencia': urljoin(url, a['href'])})
    return list({(e.get('fecha'), e.get('hora'), norm(e.get('nombre')),
                  firma_sede(e.get('lugar', ''))): e for e in hechos}.values())[:40]


def firma_sede(value):
    base = re.sub(r'\b(teatro|centro|cultural|rosario|municipal|de|del|la|el)\b', '', norm(value))
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', base).split())


def corroborar(hecho, oficiales):
    for e in oficiales:
        if (hecho.get('fecha'), hecho.get('hora'), norm(hecho.get('nombre'))) != (
                e.get('fecha'), e.get('hora'), norm(e.get('nombre'))):
            continue
        if firma_sede(hecho.get('lugar', '')) and firma_sede(hecho.get('lugar')) == firma_sede(e.get('lugar')):
            return e
    return None


def completar_verificados(eventos, hoy):
    """Incorpora sólo metadatos de funciones ya presentes y con la misma fuente.

    No importa cinco eventos por segunda vez ni reemplaza precios existentes.
    """
    archivo = ROOT / 'eventos_verificados_adicionales.json'
    if not archivo.exists():
        return
    fichas = json.loads(archivo.read_text(encoding='utf-8'))['events']
    for f in fichas:
        if f['date'] < hoy.isoformat():
            continue
        for e in eventos:
            if (e.get('fecha'), e.get('hora'), norm(e.get('nombre'))) != (
                    f['date'], f['start'], norm(f['title'])):
                continue
            if host(e.get('evento_url', '')) != host(f['source_url']):
                continue
            if firma_sede(e.get('lugar', '')) != firma_sede(f['venue']):
                continue
            if f.get('end'):
                e['hora_fin'] = f['end']
            e['descripcion'] = f['description_original']



def cargar_candidatos_passline(hoy, archivo=None):
    """Convierte fichas curadas de Passline en eventos con enlace de origen.

    Passline se toma como fuente primaria de los datos que publica en su ficha.
    No se descarga ni modifica su descripción o sus imágenes. Sólo se incluyen
    fichas futuras hasta 90 días, con referencia directa a la publicación.
    """
    archivo = archivo or ROOT / 'candidatos_passline.json'
    if not archivo.exists():
        return []
    datos = json.loads(archivo.read_text(encoding='utf-8'))
    limite = (hoy + timedelta(days=90)).isoformat()
    salida = []
    for ficha in datos.get('candidatos', []):
        fecha = ficha.get('fecha', '')
        if not (hoy.isoformat() <= fecha <= limite):
            continue
        salida.append({
            'fecha': fecha,
            'hora': ficha.get('hora'),
            'nombre': ficha.get('nombre'),
            'lugar': ficha.get('lugar'),
            'direccion': ficha.get('direccion') or '',
            'descripcion': '',
            'evento_url': ficha.get('referencia'),
            'precio': None,
            'precio_etiqueta': 'Consultar precio actualizado en Passline',
            'origen': 'Passline',
            'fuente_verificada': True,
            'descubrimiento_fuentes': ['Passline'],
        })
    return salida


def revisar(hoy, eventos, estado, acceso=None):
    completar_verificados(eventos, hoy)
    config = json.loads((ROOT / 'fuentes_adicionales.json').read_text(encoding='utf-8'))
    archivo_cache = ROOT / 'cache_fuentes_adicionales.json'
    try:
        cache = json.loads(archivo_cache.read_text(encoding='utf-8')) if archivo_cache.exists() else {}
    except (ValueError, OSError):
        cache = {}
    acceso = acceso or Acceso(cache)
    aprobados = set(config['dominios_oficiales_existentes'])
    oficiales = [e for e in eventos if host(e.get('evento_url', '')) in aprobados]
    nuevos, pendientes = [], []
    for fuente in config['fuentes']:
        nombre, url = fuente['nombre'], fuente['url']
        if not fuente['consulta_automatica']:
            estado[nombre] = 'consulta manual; auditoría pendiente'
            continue
        try:
            if nombre == 'Rosario Times':
                refs = acceso.leer(url, portada_times)
                encontrados, enlaces_oficiales = [], []
                notas_pendientes = 0
                for ref in refs[:4]:
                    try:
                        nota = acceso.leer(ref, nota_times, 'nota')
                    except (requests.RequestException, ValueError) as error:
                        notas_pendientes += 1
                        pendientes.append({'fuente': nombre, 'referencia': ref,
                                           'estado': 'nota pendiente', 'motivo': str(error)[:180]})
                        continue
                    encontrados.extend(nota['hechos'])
                    pendientes.append({'fuente': nombre, 'referencia': ref,
                                       'enlaces': nota['enlaces'], 'estado': 'comprobar organizador'})
                    enlaces_oficiales.extend(u for u in nota['enlaces'] if host(u) in aprobados)
                # Sólo dominios ya presentes en el proyecto. Los nuevos esperan auditoría.
                vinculados = 0
                for oficial in list(dict.fromkeys(enlaces_oficiales))[:4]:
                    registros = [e for e in oficiales if host(e.get('evento_url', '')) == host(oficial)
                                 and urlsplit(e.get('evento_url', '')).path.rstrip('/') == urlsplit(oficial).path.rstrip('/')]
                    if registros:
                        for e in registros:
                            fuentes = e.setdefault('descubrimiento_fuentes', [])
                            if nombre not in fuentes:
                                fuentes.append(nombre)
                        vinculados += len(registros)
                        continue
                    try:
                        hechos = acceso.leer(oficial, hechos_schema, 'nota')
                        for h in hechos:
                            if hoy.isoformat() <= h['fecha'] <= (hoy + timedelta(days=30)).isoformat() and h['direccion']:
                                e = {k: v for k, v in h.items() if k != 'referencia'}
                                e.update(evento_url=oficial, origen='Fuente oficial — Rosario Times',
                                         descripcion='', precio=None, precio_etiqueta='Precio a confirmar',
                                         fuente_verificada=True, descubrimiento_fuentes=[nombre])
                                nuevos.append(e)
                    except (requests.RequestException, ValueError):
                        notas_pendientes += 1
            else:
                encontrados = acceso.leer(url, listado_entradafan if nombre == 'EntradaFan' else listado_saleplan)
                notas_pendientes = 0
                vinculados = 0
                if nombre == 'SalePlan':
                    for candidato in encontrados[:4]:
                        if candidato.get('fecha'):
                            continue
                        try:
                            detalle = acceso.leer(candidato['referencia'], nota_times, 'nota')
                            encontrados.extend(detalle['hechos'])
                            candidato['enlaces'] = detalle['enlaces']
                        except (requests.RequestException, ValueError):
                            notas_pendientes += 1
            coincidencias = vinculados
            for h in encontrados:
                if h.get('fecha') and not hoy.isoformat() <= h['fecha'] <= (hoy + timedelta(days=30)).isoformat():
                    continue
                oficial = corroborar(h, oficiales)
                if oficial:
                    # Nunca sustituye precio, horario ni disponibilidad oficial con reventa.
                    fuentes = oficial.setdefault('descubrimiento_fuentes', [])
                    if nombre not in fuentes:
                        fuentes.append(nombre)
                    coincidencias += 1
                else:
                    pendientes.append({**h, 'fuente': nombre, 'estado': 'pendiente de confirmación oficial'})
            estado[nombre] = (f'revisada: {coincidencias} coincidencias con registros oficiales; '
                              f'{sum(p["fuente"] == nombre for p in pendientes)} candidatos pendientes; '
                              f'{notas_pendientes} consultas pendientes')
        except (requests.RequestException, ValueError) as error:
            estado[nombre] = f'no accesible: {str(error)[:180]}; se conservan datos'
    # Passline funciona como fuente primaria para sus propias fichas. Se añaden
    # los datos mínimos con enlace directo; el precio vigente se consulta allí.
    claves_eventos = {(e.get('fecha'), e.get('hora'), norm(e.get('nombre', '')),
                       firma_sede(e.get('lugar', ''))) for e in eventos + nuevos}
    for evento in cargar_candidatos_passline(hoy):
        firma = (evento.get('fecha'), evento.get('hora'), norm(evento.get('nombre', '')),
                 firma_sede(evento.get('lugar', '')))
        if firma not in claves_eventos:
            nuevos.append(evento)
            claves_eventos.add(firma)
    estado['Passline'] = 'fichas futuras incorporadas con enlace directo; precio actualizado en Passline'
    guardar(archivo_cache, acceso.cache)
    guardar(ROOT / 'candidatos_fuentes_adicionales.json',
            {'fecha_revision': hoy.isoformat(), 'nota': 'Candidatos de fuentes secundarias; las fichas de Passline se importan como eventos con enlace directo.',
             'candidatos': pendientes})
    return nuevos

