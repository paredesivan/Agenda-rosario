"""Resuelve descubrimientos dinámicos; nunca contiene fichas ni fechas de eventos.

Los medios requieren respaldo primario. Una institución puede publicar sus
propios actos abiertos. El HTML se procesa transitoriamente; sólo se guardan
campos factuales, URLs, cuotas y diagnósticos. No se siguen URLs no auditadas.
"""
import json
import re
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from fuentes_adicionales import host, norm, respaldo_acr, firma_sede
from fuentes_ampliadas import ConsultaAmpliada
from fuentes_refi_folklore import ZONA, schemas, categorias_factuales, guardar
from instituciones_eventos import acceso_publico, condiciones

ROOT = Path(__file__).resolve().parent
SIN_HORA = 'Horario a confirmar'
MESES = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1, 13)))
FORMACION = re.compile(r'\b(cursos?|taller(?:es)?|capacitacion|formacion|seminarios?|masterclass|workshops?|clases?)\b')
ADMINISTRATIVO = re.compile(r'\b(escalafonamiento|mesas (?:complementarias|extraordinarias)|dictamen|llamado a inscripcion|cronograma de pics|nivel superior)\b')
CANCELADO = re.compile(r'\b(cancelad[oa]|suspendid[oa]|postergad[oa]|reprogramad[oa])\b')


def cargar(path, defecto):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else defecto


def url_publica(url, dominios):
    """Permite sólo dominios auditados exactos y páginas públicas HTTPS."""
    try:
        p = urlsplit(url)
        return bool(p.scheme == 'https' and p.hostname and host(url) in dominios
                    and not p.username and not p.password and p.port in (None, 443)
                    and not re.search(r'^/(?:api|admin|wp-admin|go|cuenta|login)(?:/|$)', p.path, re.I))
    except (ValueError, TypeError):
        return False


def canonica(url):
    p = urlsplit(url)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query)
                             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')))
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/'), query, ''))


def fecha_hora(valor):
    if not isinstance(valor, str):
        raise ValueError('Fecha completa no publicada')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', valor):
        return date.fromisoformat(valor).isoformat(), SIN_HORA
    dt = datetime.fromisoformat(valor.replace('Z', '+00:00'))
    if 'T' not in valor:
        raise ValueError('Fecha completa no publicada')
    if dt.tzinfo:
        dt = dt.astimezone(ZONA)
    return dt.date().isoformat(), dt.strftime('%H:%M')


def hechos_propios(sopa, url):
    """JSON-LD propio, sin recomendaciones, sin precios, imágenes o sinopsis."""
    titulo = sopa.select_one('h1')
    titulo = norm(titulo.get_text(' ', strip=True)) if titulo else ''
    salida, descartes = [], []
    for script in sopa.select('script[type="application/ld+json"]'):
        try:
            objetos = list(schemas(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
        for e in objetos:
            ref = e.get('url')
            # Una oferta puede enlazar a otra ticketera; no es identidad de ficha.
            if ref and (not isinstance(ref, str) or canonica(urljoin(url, ref)) != canonica(url)):
                continue
            nombre = e.get('name')
            if not isinstance(nombre, str) or not nombre.strip():
                continue
            if not ref and (not titulo or norm(nombre) != titulo):
                continue
            if any(v in str(e.get('eventStatus', '')) for v in ('Cancelled', 'Postponed', 'Rescheduled')):
                descartes.append('Evento cancelado, suspendido o reprogramado')
                continue
            if FORMACION.search(norm(nombre)):
                descartes.append('Oferta de formación excluida')
                continue
            loc = e.get('location', {})
            dom = loc.get('address', {}) if isinstance(loc, dict) else {}
            if not isinstance(dom, dict) or norm(dom.get('addressLocality')) != 'rosario':
                descartes.append('Sede Rosario no verificada')
                continue
            if norm(dom.get('addressRegion', '')) not in ('', 'santa fe', 'santa fe province'):
                descartes.append('Sede fuera de Santa Fe')
                continue
            sede = loc.get('name')
            if not isinstance(sede, str) or not sede.strip():
                descartes.append('Sede no publicada')
                continue
            try:
                fecha, hora = fecha_hora(e.get('startDate'))
            except (ValueError, TypeError):
                descartes.append('Fecha completa no publicada')
                continue
            hecho = {'nombre': nombre.strip(), 'fecha': fecha, 'hora': hora,
                     'lugar': sede.strip(), 'direccion': dom.get('streetAddress') or '',
                     'referencia': url}
            if e.get('endDate'):
                try:
                    fin_fecha, fin_hora = fecha_hora(e['endDate'])
                    if fin_hora != SIN_HORA and hora != SIN_HORA and (fin_fecha, fin_hora) > (fecha, hora):
                        hecho.update(fecha_fin=fin_fecha, hora_fin=fin_hora)
                except (ValueError, TypeError):
                    pass
            salida.append(hecho)
    return salida, descartes


def fecha_texto(texto):
    t = norm(texto)
    m = re.search(r'\b(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')\s+(?:de\s+)?(\d{4})\b', t)
    if not m:
        return None
    return date(int(m[3]), MESES[m[2]], int(m[1])).isoformat()


def ficha_ips(sopa, url):
    cuerpo = sopa.select_one('.entry-content') or sopa.select_one('article')
    if not cuerpo:
        raise ValueError('Cambió el cuerpo de la noticia institucional')
    titulo = cuerpo.select_one('h2') or sopa.select_one('h1')
    nombre = titulo.get_text(' ', strip=True) if titulo else ''
    t = norm(cuerpo.get_text(' ', strip=True))
    if ADMINISTRATIVO.search(norm(nombre)) or FORMACION.search(norm(nombre)):
        return [], ['Aviso administrativo u oferta de formación excluidos']
    if CANCELADO.search(t):
        return [], ['Actividad suspendida o cancelada']
    # Requiere el bloque explícito del acto, sin usar la fecha de la noticia.
    m = re.search(r'(?:¿cuando\?|\bcuando\s*:)\s*(.{0,100})', t)
    fecha = fecha_texto(m[1]) if m else None
    if not fecha:
        return [], ['La noticia no informa fecha completa de una actividad']
    lugar = re.search(r'(?:¿donde\?|\bdonde\s*:)\s*([^()]{3,130})\(([^)]*\brosario\b[^)]*)\)', t)
    if not lugar:
        return [], ['Sede y dirección Rosario no verificables en la noticia']
    invitacion = ' abierta a toda la comunidad' if 'te invitamos' in t and 'toda la comunidad' in t else ''
    acceso_publico(t + invitacion)
    if not nombre:
        return [], ['Título de actividad no publicado']
    horarios = re.findall(r'\b([01]?\d|2[0-3])(?:[:.]([0-5]\d))?\s*hs?\b', t)
    # Modalidades distintas son funciones separadas; nunca inventar un rango.
    horas = sorted({f'{int(h):02d}:{m or "00"}' for h, m in horarios}) or [SIN_HORA]
    return [{'nombre': nombre, 'fecha': fecha, 'hora': hora, 'lugar': lugar[1].strip(),
             'direccion': lugar[2].strip(), 'referencia': url,
             'descripcion': condiciones(t)} for hora in horas], []


def ficha_planaxia(sopa, url):
    """Cada viñeta es un candidato; nunca se publica el artículo como un evento.

    Año de la nota sólo sirve para cruzar con otra fuente; no verifica fechas.
    Sin metadato de año no se usa el año del reloj ni del encabezado del sitio.
    """
    cuerpo = sopa.select_one('.entry-content') or sopa.select_one('.post-content') or sopa.select_one('article')
    if not cuerpo:
        return [], ['Cuerpo de agenda no interpretable']
    meta = sopa.select_one('meta[property="article:published_time"]')
    anio = None
    if meta:
        try:
            anio = datetime.fromisoformat(meta.get('content', '').replace('Z', '+00:00')).year
        except ValueError:
            pass
    salida, actual = [], None
    for n in cuerpo.select('h2, h3, h4, li'):
        t = norm(n.get_text(' ', strip=True))
        if n.name != 'li':
            actual = None
            m = re.search(r'\b(\d{1,2}) de (' + '|'.join(MESES) + r')(?: de (\d{4}))?\b', t)
            if m and (m[3] or anio):
                try:
                    actual = date(int(m[3] or anio), MESES[m[2]], int(m[1])).isoformat()
                except ValueError:
                    pass
            continue
        if not actual or FORMACION.search(t) or CANCELADO.search(t):
            continue
        # Se limita a la gramática explícita título + sede + horario.
        m = re.match(r'(.+?)\s+(?:se presenta(?:n)?|sube al escenario|da funcion|suena(?:n)?|en vivo|toca(?:n)?)?\s*en\s+(.+?)\s+a las\s+([01]?\d|2[0-3])(?:[.:]([0-5]\d))?\s*hs?\b', t)
        if not m:
            continue
        salida.append({'nombre': m[1].strip(), 'fecha': actual,
                       'hora': f'{int(m[3]):02d}:{m[4] or "00"}',
                       'lugar': m[2].strip(), 'direccion': '', 'referencia': url})
    return salida, [] if salida else ['Sin funciones fechadas interpretables; no se infiere año ni se publica la nota entera']


def detalle(contenido, url, fuente=''):
    sopa = BeautifulSoup(contenido, 'html.parser')
    hechos, descartes = hechos_propios(sopa, url)
    cuerpo = sopa.select_one('.entry-content') or sopa.select_one('article') or sopa.select_one('main') or sopa
    enlaces = []
    for a in cuerpo.select('a[href]'):
        link = urljoin(url, a['href']).split('#')[0]
        if urlsplit(link).scheme == 'https' and host(link) != host(url) and link not in enlaces:
            enlaces.append(link)
    if not hechos and fuente == 'Instituto Politécnico — Novedades':
        hechos, motivos = ficha_ips(sopa, url)
        descartes.extend(motivos)
    if not hechos and fuente == 'Planaxia':
        hechos, motivos = ficha_planaxia(sopa, url)
        descartes.extend(motivos)
    # En SalePlan los enlaces de calendario incluyen una fecha ISO completa,
    # pero no acreditan por sí solos el organizador: sirven para corroboración.
    if not hechos and fuente == 'SalePlan':
        for a in cuerpo.select('a[href]'):
            u = urlsplit(a['href'])
            if u.hostname != 'calendar.google.com' or u.path != '/calendar/render':
                continue
            q = parse_qs(u.query)
            inicio = q.get('dates', [''])[0].split('/')[0]
            try:
                dt = datetime.strptime(inicio, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).astimezone(ZONA)
            except ValueError:
                continue
            nombre = q.get('text', [''])[0]
            titulo = sopa.select_one('h1')
            if not titulo or norm(nombre) != norm(titulo.get_text(' ', strip=True)):
                continue
            sede = q.get('location', [''])[0]
            # El calendario es secundario y siempre exige cruce posterior.
            partes = re.split(r'\s*[·]\s*', sede, maxsplit=1)
            if nombre and len(partes) == 2 and re.search(r'\brosario\s*,\s*santa fe\b', norm(partes[1])):
                hechos.append({'nombre': nombre, 'fecha': dt.date().isoformat(),
                               'hora': dt.strftime('%H:%M'), 'lugar': partes[0],
                               'direccion': partes[1], 'referencia': url})
    unicos = {(e['nombre'], e['fecha'], e['hora'], e['lugar']): e for e in hechos}
    abierto = False
    if fuente == 'Instituto Politécnico — Novedades':
        t = norm(cuerpo.get_text(' ', strip=True))
        try:
            invitacion = ' abierta a toda la comunidad' if 'te invitamos' in t and 'toda la comunidad' in t else ''
            acceso_publico(t + invitacion)
            abierto = True
        except ValueError:
            descartes.append('Acceso para público general no confirmado')
    return {'hechos': list(unicos.values()), 'enlaces': enlaces[:24],
            'descartes': list(dict.fromkeys(descartes)), 'acceso_publico': abierto}


def coincidencia(hecho, eventos):
    # Sólo tolera diferencias de escritura; fecha, horario y sede deben coincidir.
    encontrado = respaldo_acr(hecho, eventos)
    if encontrado:
        return encontrado
    if hecho.get('hora') != SIN_HORA:
        return None
    candidatos = []
    for e in eventos:
        if e.get('fecha') == hecho.get('fecha') and firma_sede(e.get('lugar')) == firma_sede(hecho.get('lugar')) and norm(e.get('nombre')) == norm(hecho.get('nombre')):
            candidatos.append(e)
    return candidatos[0] if len(candidatos) == 1 else None


def resolver(root=ROOT, acceso=None, hoy=None):
    root = Path(root)
    hoy = hoy or datetime.now(ZONA).date()
    ahora = datetime.now(ZONA).isoformat()
    cfg = cargar(root / 'fuentes_adicionales.json', {})
    ampliadas = cargar(root / 'fuentes_ampliadas.json', {})
    primarios = set(cfg.get('dominios_oficiales_existentes', [])) | set(cfg.get('dominios_prioritarios_acr', []))
    for f in ampliadas.get('fuentes', []):
        if f.get('habilitada') and f.get('tipo') != 'descubrimiento':
            primarios.add(host(f['listado']))
    institucional = 'Instituto Politécnico — Novedades'
    primarios.add('ips.edu.ar')
    fuentes = {f['nombre']: host(f['url']) for f in cfg.get('fuentes', []) if f.get('consulta_automatica')}
    fuentes.update({f['nombre']: host(f['listado']) for f in ampliadas.get('fuentes', [])
                    if f.get('habilitada') and f.get('nombre') in ('Planaxia', institucional)})
    datos = cargar(root / 'eventos.json', {'eventos': []})
    cache = cargar(root / 'cache_resolucion_candidatos.json', {})
    acceso = acceso or ConsultaAmpliada(cache)
    cache = acceso.cache
    cola = cache.setdefault('cola', {})
    entradas = []
    for nombre in ('candidatos_fuentes_adicionales.json', 'candidatos_fuentes_ampliadas.json'):
        entradas.extend(cargar(root / nombre, {}).get('candidatos', []))
    # Persisten los enlaces descubiertos aunque el siguiente listado falle o rote.
    for c in entradas:
        fuente = c.get('fuente')
        url = c.get('url') or c.get('referencia')
        if fuente not in fuentes or not url_publica(url, {fuentes[fuente]}):
            continue
        k = fuente + '|' + url
        previo = cola.setdefault(k, {'fuente': fuente, 'url': url, 'intento': '', 'hechos': []})
        if all(c.get(k) for k in ('nombre', 'fecha', 'hora', 'lugar')):
            previo['hechos'] = [{k: c.get(k, '') for k in ('nombre', 'fecha', 'hora', 'lugar', 'direccion')}]
        previo['visto'] = hoy.isoformat()
    # Un dominio con fuente apagada no se reactiva por una cola antigua.
    permitidos = primarios | set(fuentes.values())
    bases = [e for e in datos['eventos'] if (host(e.get('evento_url', '')) in primarios
             or e.get('origen') == 'Agenda Cultural Rosario') and not e.get('revision_pendiente')]
    nuevos, revisadas, resultados = [], set(), []
    cuotas = cache.setdefault('cuotas', {})
    for k in list(cuotas):
        if not k.endswith(':' + hoy.isoformat()):
            del cuotas[k]

    def leer(url, fuente=''):
        if not url_publica(url, permitidos):
            raise ValueError('Dominio o ruta sin auditoría; no se consulta automáticamente')
        dia = host(url) + ':' + hoy.isoformat()
        previo = cache.setdefault('paginas', {}).get(url, {})
        vigente = acceso.reloj() - previo.get('consultado', 0) < 86400
        usadas = cuotas.setdefault(dia, [])
        if not vigente:
            if url in usadas or len(usadas) >= 4:
                raise ValueError('Cuota diaria de cuatro fichas agotada; reintento automático')
            usadas.append(url)
        return acceso.leer_datos(url, lambda h, u: detalle(h, u, fuente), horas=24)

    # Reintentos rotativos por fuente: primero URLs nunca leídas, después las
    # menos recientes. Cada dominio tiene una cuota diaria persistente.
    por_fuente = {}
    for k, c in cola.items():
        if c['fuente'] in fuentes:
            por_fuente.setdefault(c['fuente'], []).append((k, c))
    for fuente, filas in por_fuente.items():
        # Los descartes se conservan como diagnóstico y se revisan semanalmente;
        # las novedades sin leer tienen prioridad sobre el archivo histórico.
        activas = []
        for k, c in filas:
            previo = c.get('resultado', {})
            if previo.get('estado') == 'descartado' and c.get('revisado_dia') and hoy - date.fromisoformat(c['revisado_dia']) < timedelta(days=7):
                resultados.append(previo)
            else:
                activas.append((k, c))
        filas = activas
        filas.sort(key=lambda par: (par[1].get('intento', ''), -date.fromisoformat(par[1]['visto']).toordinal(), par[0]))
        for indice, (k, c) in enumerate(filas):
            if indice >= 4:
                resultados.append({'fuente': fuente, 'url': c['url'], 'estado': 'diferido', 'motivo': 'Turno de revisión rotativa en otra ejecución'})
                continue
            r = {'fuente': fuente, 'url': c['url'], 'estado': 'pendiente', 'motivo': '', 'funciones': 0}
            try:
                if fuente == institucional and ADMINISTRATIVO.search(norm(urlsplit(c['url']).path.replace('-', ' '))):
                    r.update(estado='descartado', motivo='Aviso administrativo institucional; no es una salida pública')
                    c['intento'], c['resultado'], c['revisado_dia'] = ahora, r, hoy.isoformat()
                    resultados.append(r)
                    continue
                hechos = c.get('hechos', [])
                coincidencias = [coincidencia(h, bases) for h in hechos]
                if fuente == 'EntradaFan' and hechos and all(coincidencias):
                    r.update(estado='corroborado', motivo='Ya publicado con respaldo prioritario', funciones=len(hechos))
                else:
                    ficha = leer(c['url'], fuente)
                    # Las filas fechadas de EntradaFan son evidencia del listado
                    # actual. En otras fuentes no reutilizar funciones de una
                    # versión anterior si la nueva ficha las quitó.
                    hechos = ficha['hechos'] or (hechos if fuente == 'EntradaFan' and not ficha['descartes'] else [])
                    c['hechos'] = hechos
                    oficiales = []
                    if fuente == institucional and any('cancelad' in m.lower() or 'suspendid' in m.lower() for m in ficha['descartes']):
                        revisadas.add((fuente, c['url']))
                    respaldos_enlazados = []
                    for link in ficha['enlaces']:
                        if host(link) not in primarios or not url_publica(link, primarios):
                            continue
                        conocidos = [e for e in bases if canonica(e.get('evento_url', '')) == canonica(link)
                                     and not e.get('origen', '').startswith('Fuente oficial — ')]
                        if conocidos:
                            respaldos_enlazados.extend(conocidos)
                            for e in conocidos:
                                if fuente not in e.setdefault('descubrimiento_fuentes', []):
                                    e['descubrimiento_fuentes'].append(fuente)
                            continue
                        try:
                            prim = leer(link)
                            if prim['hechos']:
                                revisadas.add(('Fuente oficial — ' + fuente, link))
                            if not prim['hechos']:
                                r.setdefault('errores_enlaces', []).append({'url': link, 'motivo': '; '.join(prim['descartes']) or 'Ficha primaria sin metadatos de evento propios interpretables'})
                            if any('cancelad' in m.lower() or 'suspendid' in m.lower() for m in prim['descartes']):
                                revisadas.add(('Fuente oficial — ' + fuente, link))
                            for h in prim['hechos']:
                                oficiales.append({**h, 'evento_url': link, 'origen': 'Fuente oficial — ' + fuente,
                                                  'descubrimiento_fuentes': [fuente], 'fuente_verificada': True})
                        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
                            r.setdefault('errores_enlaces', []).append({'url': link, 'motivo': str(error)[:240]})
                    # Una nota puede descubrir una ficha oficial que ya identifica
                    # por sí misma el evento, incluso sin JSON-LD en el medio.
                    if fuente == institucional and hechos and ficha.get('acceso_publico'):
                        revisadas.add((fuente, c['url']))
                    publicables = oficiales + ([{**h, 'evento_url': c['url'], 'origen': fuente,
                                                 'fuente_verificada': True} for h in hechos] if fuente == institucional else [])
                    aceptados = 0
                    for e in publicables:
                        if FORMACION.search(norm(e['nombre'])):
                            continue
                        if not hoy.isoformat() <= e['fecha'] <= (hoy + timedelta(days=180)).isoformat():
                            continue
                        if fuente == institucional:
                            # También las fichas estructuradas institucionales
                            # deben acreditar apertura, nunca sólo una fecha.
                            if not ficha.get('acceso_publico'):
                                continue
                        nuevos.append({**e, 'descripcion': e.get('descripcion', ''), 'precio': None,
                                       'precio_etiqueta': 'Consultar precio y condiciones en la fuente',
                                       'categorias': categorias_factuales(e['nombre'], ''),
                                       'descubrimiento_fuentes': [fuente]})
                        aceptados += 1
                        revisadas.add((e['origen'], e['evento_url']))
                    referencias = bases + nuevos
                    verificadas = [coincidencia(h, referencias) for h in hechos if hoy.isoformat() <= h.get('fecha', '') <= (hoy + timedelta(days=180)).isoformat()]
                    for e in verificadas:
                        if e and fuente not in e.setdefault('descubrimiento_fuentes', []):
                            e['descubrimiento_fuentes'].append(fuente)
                    if aceptados:
                        r.update(estado='publicado', motivo='Ficha oficial con datos verificables', funciones=aceptados)
                    elif respaldos_enlazados and not hechos:
                        r.update(estado='corroborado', motivo='La nota enlaza funciones oficiales ya publicadas', funciones=len(respaldos_enlazados))
                    elif verificadas and all(verificadas):
                        r.update(estado='corroborado', motivo='Funciones ya publicadas con respaldo prioritario', funciones=len(verificadas))
                    elif hechos and all(h.get('fecha', '') < hoy.isoformat() for h in hechos):
                        r.update(estado='descartado', motivo='Todas las funciones detectadas están vencidas')
                    else:
                        motivos = ficha['descartes']
                        if motivos and all(any(v in m.lower() for v in ('administrativo', 'formacion', 'cancelad', 'suspendid', 'fuera de santa fe')) for m in motivos):
                            r['estado'] = 'descartado'
                        r['motivo'] = '; '.join(motivos) or 'Sin coincidencia oficial ni ficha primaria interpretable; reintento automático'
            except (requests.RequestException, ValueError, KeyError, TypeError) as error:
                r.update(estado='reintentar', motivo=str(error)[:400])
            # No avanzar el turno de una ficha que no pudo consultarse por
            # cuota: hacerlo dejaría las últimas URLs sin leer indefinidamente.
            if 'Cuota diaria' not in r['motivo']:
                c['intento'] = ahora
                c['revisado_dia'] = hoy.isoformat()
            c['resultado'] = r
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    # Reemplazo de URLs sólo si hubo lectura oficial válida. Los errores nunca
    # quitan datos. El protector global reconoce este identificador de revisión.
    from fuentes_ampliadas import fusionar
    datos['eventos'] = fusionar(datos['eventos'], nuevos, revisadas, hoy)
    datos['revision_resolucion'] = {'id': uuid.uuid4().hex, 'fichas_revisadas': [list(p) for p in sorted(revisadas)]}
    resumen = {}
    for fuente in por_fuente:
        conteos = Counter(r['estado'] for r in resultados if r['fuente'] == fuente)
        resumen[fuente] = dict(conteos)
    # Separar el resultado de la cola del número de posibles eventos.
    estados_por_url = {(r['fuente'], r['url']): r for r in resultados}
    for archivo in ('candidatos_fuentes_adicionales.json', 'candidatos_fuentes_ampliadas.json'):
        documento = cargar(root / archivo, {})
        if not documento:
            continue
        for c in documento.get('candidatos', []):
            r = estados_por_url.get((c.get('fuente'), c.get('url') or c.get('referencia')))
            if r:
                c.update(estado=r['estado'], motivo=r['motivo'])
        guardar(root / archivo, documento)
    if any(r['estado'] in ('pendiente', 'reintentar') for r in resultados):
        datos['estado'] = 'parcial'
    guardar(root / 'eventos.json', datos)
    guardar(root / 'cache_resolucion_candidatos.json', cache)
    guardar(root / 'revision_resolucion_candidatos.json', {'revision': ahora, 'fuentes': resumen, 'resultados': resultados})
    registro = cargar(root / 'fuentes_revisadas.json', {})
    for fuente, conteos in resumen.items():
        registro.setdefault('fuentes', {})[fuente] = 'resolución automática: ' + ', '.join(f'{n} {e}' for e, n in sorted(conteos.items()))
    guardar(root / 'fuentes_revisadas.json', registro)
    print(json.dumps(resumen, ensure_ascii=False), flush=True)
    return resultados


if __name__ == '__main__':
    resolver()
