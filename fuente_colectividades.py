"""Consulta las jornadas de Colectividades publicadas en la portada municipal.

Sin fechas/eventos precargados: el año, los días y las URLs se leen de la web
oficial. La fuente se ejecuta en cada actualización normal de Agenda Rosario.
"""

import re
import requests
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit

BASE = 'https://www.rosario.gob.ar/inicio/colectividades'
ORIGEN = 'Municipalidad de Rosario — Colectividades'
HORIZONTE_DIAS = 180
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
PATRON_DIA = re.compile(r'^/inicio/colectividades-(20\d{2})-dia-(\d{1,2})/?$', re.I)


def limpio(elemento):
    return ' '.join(elemento.get_text(' ', strip=True).split())


def fecha_en_texto(texto, anio):
    coincidencia = re.search(r'(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})(?!\d)', texto)
    if not coincidencia:
        return None
    try:
        return date(anio, int(coincidencia[2]), int(coincidencia[1]))
    except ValueError:
        return None


def rango_publicado(texto, anio):
    patron = r'\bdel?\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')\b'
    m = re.search(patron, texto, re.I)
    if not m:
        return None
    try:
        primero = date(anio, MESES.index(m[3].lower()) + 1, int(m[1]))
        ultimo = date(anio, MESES.index(m[3].lower()) + 1, int(m[2]))
    except ValueError:
        return None
    if ultimo < primero or (ultimo - primero).days > 31:
        return None
    return primero, ultimo


def hora_publicada(texto):
    m = re.search(r'\btodos\s+los\s+d[ií]as\s+desde\s+las\s+(\d{1,2})(?:[:.](\d{2}))?\s*h\b', texto, re.I)
    if not m:
        return None
    hora, minutos = int(m[1]), int(m[2] or '0')
    return f'{hora:02d}:{minutos:02d}' if hora < 24 and minutos < 60 else None


def tarjetas_publicadas(html, hoy):
    cuerpo = limpio(html.select_one('main') or html)
    hora = hora_publicada(cuerpo)
    if not hora:
        raise ValueError('Colectividades: la portada no confirma la hora de apertura')
    if 'parque nacional a la bandera' not in cuerpo.lower():
        raise ValueError('Colectividades: la portada no confirma el lugar')

    tarjetas = {}
    for a in html.select('a[href]'):
        link = urljoin(BASE, a.get('href', ''))
        partes = urlsplit(link)
        match = PATRON_DIA.fullmatch(partes.path)
        if partes.hostname not in ('www.rosario.gob.ar', 'rosario.gob.ar') or not match:
            continue
        anio, ordinal = int(match[1]), int(match[2])
        if ordinal > 31:
            continue
        rango = rango_publicado(cuerpo, anio)
        titulo = limpio(a)
        fecha = fecha_en_texto(titulo, anio)
        if fecha is None and rango:
            # Sólo se usa ordinal si se publica expresamente en el enlace.
            dia = re.search(r'\bd[ií]a\s+(\d{1,2})\b', titulo, re.I)
            if dia and int(dia[1]) == ordinal:
                fecha = rango[0] + timedelta(days=ordinal - 1)
        if fecha is None or (rango and not rango[0] <= fecha <= rango[1]):
            continue
        if not hoy <= fecha <= hoy + timedelta(days=HORIZONTE_DIAS):
            continue
        # La jornada diaria tiene su propia ficha oficial; nunca usar la portada
        # como URL del evento, salvo caída del enlace específico.
        tarjetas[fecha.isoformat()] = (link, hora, anio)
    if not tarjetas:
        # Fuera de temporada es normal tener cero funciones. Un cambio de HTML
        # con días futuros publicados sí es un error detectable en diagnóstico.
        if re.search(r'colectividades\s+20\d{2}', cuerpo, re.I):
            m = re.search(r'colectividades\s+(20\d{2})', cuerpo, re.I)
            periodo = rango_publicado(cuerpo, int(m[1])) if m else None
            if periodo and periodo[1] < hoy:
                return {}, cuerpo
        raise ValueError('Colectividades: no se detectaron jornadas verificables')
    return tarjetas, cuerpo


def revisar_detalle(html, fecha, hora):
    cuerpo = html.select_one('main') or html
    texto = limpio(cuerpo)
    titulo = limpio(cuerpo.select_one('h1')) if cuerpo.select_one('h1') else ''
    if not re.search(r'colectividades', titulo, re.I):
        return None  # No aceptar una ficha redirigida a otro evento.
    if re.search(r'\b(?:suspendid[ao]|cancelad[ao])\b', titulo, re.I):
        return False
    confirmacion = re.search(r'\b(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')\b', texto, re.I)
    if confirmacion:
        dia_mes = fecha_en_texto(f'{confirmacion[1]}.{MESES.index(confirmacion[2].lower()) + 1}', fecha.year)
        if dia_mes != fecha:
            return None
    precio = 0 if re.search(r'\bgratis\b|entrada\s+(?:libre\s+y\s+)?gratuita\b', texto, re.I) else None
    return precio


def recolectar(hoy, descargar):
    """Devuelve una función por fecha oficial; una falla parcial no borra datos."""
    html = descargar(BASE)
    tarjetas, cuerpo = tarjetas_publicadas(html, hoy)
    resultados = []
    for fecha, (url, hora, anio) in sorted(tarjetas.items()):
        precio = None
        try:
            detalle = revisar_detalle(descargar(url), date.fromisoformat(fecha), hora)
            if detalle is False:
                continue  # Cancelación explícita.
            if detalle is not None:
                precio = detalle
        except (requests.RequestException, ValueError) as error:
            # La portada ya confirmó fecha, sede y horario. No perder la jornada
            # si falló la consulta opcional del precio en la ficha específica.
            print(f'Colectividades: detalle no accesible ({type(error).__name__}); usando portada oficial', flush=True)
        evento = {
            'fecha': fecha, 'hora': hora,
            'nombre': f'Encuentro y Fiesta Nacional de Colectividades {anio}',
            'lugar': 'Parque Nacional a la Bandera',
            'direccion': 'Parque Nacional a la Bandera, Rosario, Santa Fe',
            'descripcion': 'Jornada de Colectividades: gastronomía, música y danzas. Programación en el enlace oficial.',
            'evento_url': url, 'precio': precio, 'origen': ORIGEN,
        }
        if precio is None:
            evento['precio_etiqueta'] = 'Consultar condiciones en la fuente oficial'
        resultados.append(evento)
    return resultados
