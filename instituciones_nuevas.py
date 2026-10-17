"""Adaptadores estrictos para agendas institucionales de Rosario.

Sin eventos ni fechas fijas: solo parsea fichas HTML verificables.
NO hace HTTP: la capa de acceso existente verifica robots, pausas y caché.
"""
import re
import unicodedata
from datetime import date, datetime
from bs4 import BeautifulSoup

MESES = {nombre: i for i, nombre in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), 1)}


def normalizar(valor):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', str(valor).lower())
                           if unicodedata.category(c) != 'Mn').split())


def es_formacion(evento):
    """Excluye oferta de cursos sin eliminar festivales que mencionen talleres."""
    if isinstance(evento, str):
        titulo, categorias = evento, ''
    else:
        titulo = evento.get('nombre', '')
        cats = evento.get('categorias', [])
        categorias = ' '.join(cats) if isinstance(cats, list) else str(cats)
    t, c = normalizar(titulo), normalizar(categorias)
    if re.search(r'\b(aprendizaje|formacion|capacitacion|cursos|educacion continua)\b', c):
        return True
    # Anclar al principio: "Encuentro de Academias y Talleres" es un espectáculo.
    return bool(re.search(
        r'^(?:convocatoria(?:s)?\b|inscripciones?\b|becas?\b|charla[- ]taller\b|'
        r'jornada de formacion\b)|^(?:inscripcion(?:es)? (?:a|al|para)\s+|convocatoria (?:a|para)\s+)?'
        r'(?:curso(?:s)?\b|taller(?:es)?\b|workshop(?:s)?\b|'
        r'capacitacion(?:es)?\b|diplomatura(?:s)?\b|'
        r'posgrado(?:s)?\b|maestria(?:s)?\b|'
        r'clase(?:s)?\b|clinica(?:s)? de formacion\b|'
        r'seminario(?:s)? de formacion\b|jornada de capacitacion\b)', t))


def _hora(raw):
    try:
        return datetime.strptime(raw, '%H:%M').strftime('%H:%M')
    except ValueError as exc:
        raise ValueError('Hora fuera de rango') from exc


def _fecha(dia, mes, anio):
    try:
        return date(int(anio), MESES[normalizar(mes)], int(dia))
    except (ValueError, KeyError) as exc:
        raise ValueError('Fecha incompleta o imposible') from exc


def _acceso_publico(texto):
    t = normalizar(texto)
    if re.search(r'\b(?:solo (?:para )?socios|exclusivo para|actividad interna|solo estudiantes|solo docentes)\b', t):
        raise ValueError('Acceso restringido')
    if not re.search(r'entrada(?:s)? (?:libre|gratuita|general|a la venta)|'
                     r'abiert[oa] (?:a |para )?(?:toda )?la comunidad|'
                     r'publico general|acceso libre|arancelad[oa]|'
                     r'entradas? (?:disponibles|desde)|'
                     r'compra (?:tu|tus) entradas?', t):
        raise ValueError('No se confirmó acceso del público')


def _precio(texto):
    t = normalizar(texto)
    if re.search(r'entrada (?:libre y )?gratuita|entrada libre|acceso libre y gratuito|\blibre,? gratuita\b|sin cargo|show gratis', t):
        return 0, 'Gratis'
    m = re.search(r'entrada general\s*:\s*\$\s*([\d.]+)', texto, re.I)
    if m:
        return int(m.group(1).replace('.', '')), 'Precio informado por la sede'
    return None, 'Consultar precio en la fuente'


def _registro(nombre, fecha, hora, lugar, direccion, contenido, fin=None):
    if not nombre or es_formacion(nombre):
        raise ValueError('No es un evento cultural abierto: formación')
    _acceso_publico(contenido)
    hora = _hora(hora)
    if fin is not None:
        fin = _hora(fin)
        if fin <= hora:
            raise ValueError('Hora de finalización incompatible')
    precio, etiqueta = _precio(contenido)
    n = normalizar(nombre)
    cats = [cat for cat, patron in (
        ('teatro', r'\b(teatro|obra|escenica|comedia)\b'),
        ('musica', r'\b(concierto|recital|musica|banda|dj)\b'),
        ('danza', r'\b(danza|baile)\b'),
        ('libros', r'\b(libro|lectura|presentacion)\b')) if re.search(patron, n)]
    return {'cancelado': False, 'nombre': nombre, 'fecha': fecha.isoformat(),
            'hora': hora, 'lugar': lugar, 'direccion': direccion,
            'categorias': cats, 'descripcion': '', 'acceso': 'Público general',
            'precio': precio, 'precio_etiqueta': etiqueta,
            **({'fecha_fin': fecha.isoformat(), 'hora_fin': fin} if fin else {})}


def ficha_cec(html, url, fuente=None):
    """CEC /events/<slug>: fecha de la ficha, no de publicación; sin inventar horas."""
    sopa = BeautifulSoup(html, 'html.parser')
    titulo = sopa.select_one('h1')
    if not titulo:
        raise ValueError('Sin título en ficha CEC')
    nombre = titulo.get_text(' ', strip=True)
    if es_formacion(nombre):
        raise ValueError('Formación excluida')
    texto = sopa.get_text('\n', strip=True)
    normal = normalizar(texto)
    if re.search(r'\b(cancelado|suspendido|postergado)\b', normal[:700]):
        return [{'cancelado': True}]
    # Las etiquetas de MEC están dentro de la ficha; no inferir fechas de artículos.
    patron_fecha = r'\bFecha\s*(\d{1,2}(?:\s*-\s*\d{1,2})?/\d{1,2}/\d{4})\b'
    patron_hora = r'\bHora\s*(Todo el d[ií]a|\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\b'
    fechas = re.findall(patron_fecha, texto, re.I)
    horas = re.findall(patron_hora, texto, re.I)
    if len(fechas) != 1 or len(horas) != 1:
        raise ValueError('Ficha CEC sin fecha y hora únicas')
    if not re.search(r'\b(?:cec|centro de expresiones contemporaneas)\b', normal):
        raise ValueError('Sede CEC no identificada')
    if 'rosario' not in normal:
        raise ValueError('Localidad Rosario no confirmada')
    cuerpo = texto.split(re.search(r'\bFecha\s*'+re.escape(fechas[0]), texto, re.I).group(0))[0]
    # Validación de acceso en contenido del evento; el pie no cuenta.
    _acceso_publico(cuerpo)
    sede = 'Centro de Expresiones Contemporáneas (CEC)'
    direccion = 'Paseo de las Artes 310, Rosario'
    raw_fecha = fechas[0]
    if '-' not in raw_fecha:
        d, m, y = (int(v) for v in raw_fecha.split('/'))
        fecha = date(y, m, d)
        if normalizar(horas[0]) == 'todo el dia':
            raise ValueError('Evento sin horario de inicio confirmado')
        partes = [v.strip() for v in horas[0].split('-')]
        return [_registro(nombre, fecha, partes[0], sede, direccion, cuerpo,
                          partes[1] if len(partes) == 2 else None)]
    # Un rango no significa una única función ni "todo el día".
    m = re.fullmatch(r'(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})', raw_fecha)
    if not m:
        raise ValueError('Rango de fechas ambiguo')
    inicio, fin_dia, mes, anio = map(int, m.groups())
    if not 1 <= fin_dia-inicio <= 6:
        raise ValueError('Rango demasiado largo o inválido')
    resultados = []
    # Solo expandir cuando cada día tenga horario inequívoco en el cuerpo.
    for dia in range(inicio, fin_dia + 1):
        fecha = date(anio, mes, dia)
        # Ej.: "Sábado 17 de octubre de 13 a 20 hs" / "Domingo 18 ... 15 a 18hs".
        patron = (r'\b' + str(dia) + r'\s+de\s+' + list(MESES)[mes-1] +
                  r'\s+(?:de\s+)?(\d{1,2})(?::(\d{2}))?\s*a\s*'
                  r'(\d{1,2})(?::(\d{2}))?\s*h(?:s)?\b')
        ocurrencias = re.findall(patron, normalizar(cuerpo), re.I)
        if len(ocurrencias) != 1:
            raise ValueError('Falta cronograma inequívoco por fecha')
        h, mm, hf, mf = ocurrencias[0]
        resultados.append(_registro(nombre, fecha, f'{int(h):02d}:{mm or "00"}',
                                    sede, direccion, cuerpo,
                                    f'{int(hf):02d}:{mf or "00"}'))
    return resultados


def ficha_ucsf(html, url, fuente=None):
    """UCSF: se prioriza punto de encuentro real sobre el local administrativo."""
    sopa = BeautifulSoup(html, 'html.parser')
    h1 = sopa.select_one('h1')
    if not h1:
        raise ValueError('Ficha UCSF sin título')
    nombre = h1.get_text(' ', strip=True)
    if es_formacion(nombre):
        raise ValueError('Formación excluida')
    texto = sopa.get_text('\n', strip=True)
    if re.search(r'\b(?:suspendido|cancelado|postergado)\b', normalizar(texto[:800])):
        return [{'cancelado': True}]
    # No tomar datePublished ni la fecha de la nota; exigir la etiqueta de evento.
    fechas = re.findall(r'\bFecha\s*:\s*\d{1,2}\s+de\s+\w+\s*\((\d{4}-\d{2}-\d{2})\)', texto, re.I)
    horarios = re.findall(r'\bHora\s*:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', texto, re.I)
    if len(fechas) != 1 or len(horarios) != 1:
        raise ValueError('Fecha u hora UCSF no verificables')
    fecha = date.fromisoformat(fechas[0])
    inicio, fin = horarios[0]
    # No usar el domicilio administrativo de "Local"; exigir ubicación en cuerpo.
    m = re.search(r'Punto de encuentro\s*:\s*([^,\n.]+),\s*([^\n.]*?\d+[A-Za-z]?)\b', texto, re.I)
    if not m:
        raise ValueError('Punto de encuentro del evento no confirmado')
    sede, calle = m.group(1).strip(), m.group(2).strip()
    if not re.search(r'\brosario\b', normalizar(texto)):
        raise ValueError('No se confirma Rosario')
    # Validar acceso antes del bloque de "Detalles" de la ficha.
    cuerpo = re.split(r'\bDetalles\b', texto, maxsplit=1)[0]
    return [_registro(nombre, fecha, inicio, sede, calle+', Rosario', cuerpo, fin)]
