"""Extractor dinámico para la agenda oficial del Autódromo Ciudad de Rosario.

No contiene eventos prefijados. Si una página falla, no elimina eventos existentes.
Requiere requests y beautifulsoup4, ya usados por Agenda-rosario.
"""
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
BASE = 'https://autodromorosario.com'
AGENTE = 'AgendaRosario/3.1 (+https://github.com/paredesivan/Agenda-rosario)'
MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5,
         'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9,
         'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def normalizar(texto):
    texto = unicodedata.normalize('NFD', str(texto).casefold())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def fechas(texto):
    texto = normalizar(texto)
    # Formato de las fichas oficiales: "24 al 25 de Octubre, 2026".
    patron = (r'\b(\d{1,2})(?:\s*(?:al|a|-)\s*(\d{1,2}))?'
              r'\s+de\s+(' + '|'.join(MESES) + r')\s*,?\s*(?:de\s*)?(20\d{2})\b')
    for m in re.finditer(patron, texto, flags=re.I):
        dia, fin, mes, anio = m.groups()
        try:
            inicio = date(int(anio), MESES[mes], int(dia))
            termino = date(int(anio), MESES[mes], int(fin)) if fin else inicio
            if inicio <= termino and (termino - inicio).days <= 14:
                return inicio, termino
        except ValueError:
            continue
    return None


def enlaces_de_eventos(html):
    sopa = BeautifulSoup(html, 'html.parser')
    encontrados = set()
    for a in sopa.select('a[href]'):
        url = urljoin(BASE, a['href']).split('#')[0].split('?')[0].rstrip('/')
        parsed = urlparse(url)
        if parsed.netloc.lower() in ('autodromorosario.com', 'www.autodromorosario.com') and re.fullmatch(r'/eventos/[^/]+', parsed.path):
            encontrados.add(url)
    # Algunos despliegues Next/React incluyen enlaces dentro de JSON escapado.
    for match in re.findall(r'(?:https?://(?:www\.)?autodromorosario\.com)?/eventos/[\w%-]+', html):
        encontrados.add(urljoin(BASE, match).rstrip('/'))
    return sorted(encontrados)


def extraer_ficha(html, url, hoy=None):
    hoy = hoy or date.today()
    sopa = BeautifulSoup(html, 'html.parser')
    nombre = sopa.select_one('h1')
    if not nombre:
        return None
    nombre = nombre.get_text(' ', strip=True)
    if not nombre or normalizar(nombre) in ('cargando', 'eventos'):
        return None
    texto = sopa.get_text(' ', strip=True)
    rango = fechas(texto)
    if not rango:
        return None  # No inferir fecha a partir de la URL ni de la noticia.
    inicio, fin = rango
    if fin < hoy or inicio > hoy + timedelta(days=365):
        return None
    descripcion = ''
    encabezado = sopa.find(string=re.compile(r'sobre el evento', re.I))
    if encabezado:
        for nodo in encabezado.parent.next_elements:
            if getattr(nodo, 'name', None) in ('p', 'div'):
                candidato = nodo.get_text(' ', strip=True)
                if 35 <= len(candidato) <= 1000:
                    descripcion = candidato
                    break
    # El horario solo se añade si está indicado expresamente en la ficha.
    horas = re.search(r'\b(?:hora(?:rio)?|inicio)\s*:?\s*(\d{1,2}:\d{2})\s*(?:hs|h)?\b', texto, re.I)
    hora = horas.group(1).zfill(5) if horas else 'Horario a confirmar'
    return {
        'fecha': inicio.isoformat(), 'fecha_fin': fin.isoformat(),
        'hora': hora, 'nombre': nombre,
        'lugar': 'Autódromo Municipal Juan Manuel Fangio',
        'direccion': 'Av. Jorge Newbery y García del Cossio, Rosario, Santa Fe',
        'descripcion': descripcion or 'Competencia o actividad anunciada por el Autódromo de Rosario. Consultar condiciones en la fuente oficial.',
        'evento_url': url, 'origen': 'Autódromo Rosario',
        'precio': None, 'precio_etiqueta': 'Consultar entradas y condiciones',
        'categorias': ['otros'], 'fuente_verificada': True,
    }


def obtener(session, url, robots):
    if not robots.can_fetch(AGENTE, url):
        raise RuntimeError('Consulta prohibida por robots.txt: ' + url)
    respuesta = session.get(url, timeout=18, allow_redirects=False)
    respuesta.raise_for_status()
    if respuesta.is_redirect:
        raise RuntimeError('Redirección sin auditar: ' + url)
    return respuesta.text


def actualizar(root=ROOT, session=None, hoy=None):
    hoy = hoy or date.today()
    session = session or requests.Session()
    session.headers.update({'User-Agent': AGENTE, 'Accept': 'text/html'})
    robots = RobotFileParser()
    respuesta_robots = session.get(BASE + '/robots.txt', timeout=15, allow_redirects=False)
    if respuesta_robots.status_code == 404:
        robots.parse([])
    elif respuesta_robots.status_code == 200:
        robots.parse(respuesta_robots.text.splitlines())
    else:
        raise RuntimeError('No se pudo verificar robots.txt: HTTP ' + str(respuesta_robots.status_code))
    # Ambas páginas: la agenda general puede estar renderizada por JS;
    # la portada ofrece enlaces cuando el catálogo se presenta allí.
    enlaces = set()
    for pagina in (BASE + '/eventos', BASE + '/'):
        try:
            enlaces.update(enlaces_de_eventos(obtener(session, pagina, robots)))
        except (requests.RequestException, RuntimeError) as exc:
            print('Autódromo: página inaccesible:', pagina, str(exc), flush=True)
    if not enlaces:
        print('AVISO Autódromo: catálogo sin enlaces verificables; se conserva la agenda', flush=True)
        return {'nuevos': 0, 'revisados': 0, 'errores': [{'motivo': 'sin_enlaces_verificables'}]}
    path = Path(root) / 'eventos.json'
    datos = json.loads(path.read_text(encoding='utf-8'))
    anteriores = datos['eventos']
    nuevos = []
    errores = []
    for url in sorted(enlaces)[:80]:
        try:
            evento = extraer_ficha(obtener(session, url, robots), url, hoy)
            if evento:
                nuevos.append(evento)
        except (requests.RequestException, RuntimeError) as exc:
            errores.append({'url': url, 'error': str(exc)})
    if not nuevos:
        print('Autódromo: sin fichas futuras verificables; se conserva la agenda', flush=True)
        return {'nuevos': 0, 'revisados': len(enlaces), 'errores': errores}
    def clave(e):
        return (normalizar(e.get('nombre', '')).strip(), e.get('fecha', ''),
                normalizar(e.get('lugar', '')).strip())
    def similar(e, nuevo):
        return e.get('fecha') == nuevo['fecha'] and (
            e.get('evento_url', '').rstrip('/') == nuevo['evento_url'] or
            (clave(e)[0] == clave(nuevo)[0] and ('autodromo' in normalizar(e.get('lugar', '')) or 'fangio' in normalizar(e.get('lugar', '')))))
    agregados = 0
    for nuevo in nuevos:
        indices = [i for i, anterior in enumerate(anteriores) if similar(anterior, nuevo)]
        if indices:
            i = indices[0]
            # Actualiza los datos de la ficha, sin borrar información previa más precisa.
            anterior = anteriores[i]
            anteriores[i] = {**anterior, **{k: v for k, v in nuevo.items()
                if k not in ('hora', 'descripcion', 'precio', 'precio_etiqueta') or
                (v not in (None, '', 'Horario a confirmar') and
                 (k != 'precio_etiqueta' or not anterior.get(k)))}}
        else:
            anteriores.append(nuevo)
            agregados += 1
    anteriores.sort(key=lambda e: (e['fecha'], e.get('hora', ''), e['nombre']))
    # Escritura atómica: nunca truncar eventos.json ante un fallo.
    temp = path.with_suffix('.autodromo.tmp')
    temp.write_text(json.dumps(datos, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temp.replace(path)
    print('Autódromo: agregados:', agregados, 'fichas verificadas:', len(nuevos), 'errores:', len(errores), flush=True)
    return {'nuevos': agregados, 'revisados': len(enlaces), 'errores': errores}


if __name__ == '__main__':
    actualizar()
