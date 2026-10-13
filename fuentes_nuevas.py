"""Agenda Rosario: control adicional de salas ATIR, prensa y Rosario en Cartel.

Sólo agrega actividades con fecha, hora y sede verificables. Ante fallas no
elimina actividades previamente publicadas ni bloquea el actualizador principal.
"""
import calendar
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, parse_qs

import requests
from actualizar_eventos import (
    ARCHIVO, ZONA, descargar, normalizar, texto, resumen,
    eventos_schema, calendario_mec, hora_visible, fechas_publicadas,
    actividad_ampliada, evento_extra, DIAS, MESES as MESES_LISTA, sin_repetidos,
)

SALAS = (
    ("Caras y Caretas", "caras-y-caretas", "Corrientes 1518"),
    ("Club Fosse", "club-fosse", "Salta 2829"),
    ("Cultural de Abajo", "cultural-de-abajo", "Entre Ríos 579"),
    ("La Escalera", "la-escalera", "9 de Julio 324"),
    ("Espacio Bravo", "espacio-bravo", "Catamarca 3624"),
    ("La Grieta", "la-grieta", "Centeno 1738"),
    ("Teatro de la Manzana", "teatro-de-la-manzana", "San Juan 1950"),
    ("La Morada", "la-morada", "San Martín 771"),
    ("La Orilla Infinita", "la-orilla-infinita", "Colón 2148"),
    ("Teatro del Rayo", "teatro-del-rayo", "Salta 2991"),
    ("La Sonrisa de Beckett", "la-sonrisa-de-beckett", "Entre Ríos 1051"),
    ("Tandava", "tandava", "9 de Julio 754"),
    ("La Tornería", "la-torneria", "Pasaje Amsterdam 1113"),
)
PRENSA = (
    ("Rosario3", "https://www.rosario3.com/seccion/ocio/", "/ocio/"),
    ("La Capital", "https://www.lacapital.com.ar/secciones/zoom.html", "/zoom/"),
    ("El Ciudadano", "https://elciudadanoweb.com/seccion/espectaculos/", "/"),
)
CARTELERA = ("Rosario en Cartel", "https://rosarioencartel.com.ar/")
INTERES = re.compile(
    r"teatro|obra|recital|festival|funci[oó]n|concierto|agenda|"
    r"espect[aá]culo|orquesta|feria|muestra|cultural|danza|cartelera|show|en rosario", re.I
)
SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
          "viernes": 4, "sabados": 5, "domingos": 6}
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
         "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
PATRON_RECURRENTE = re.compile(
    r"\blos\s+(lunes|martes|miercoles|jueves|viernes|sabados|domingos)"
    r"\s+(?:(\d{1,2}(?:\s*,\s*\d{1,2})*\s+y\s+\d{1,2})\s+)?"
    r"de\s+(" + "|".join(MESES) + r")\s*,?\s*a\s+las?\s+"
    r"(\d{1,2})(?:[.:](\d{2}))?\b"
)
NOMBRE = re.compile(
    r"\bse presenta(?:n)?\s+(?:la obra\s+|el espectaculo\s+)?"
    r"(.{2,80}?)(?:,|\.|;|$)", re.I
)
REGISTRO = Path(__file__).with_name("fuentes_revisadas.json")


def clave(e):
    return (e["fecha"], e["hora"], normalizar(e["nombre"]).strip(),
            normalizar(e["lugar"]).strip())


def mismo_dominio(url, base):
    a, b = urlsplit(url), urlsplit(base)
    return a.scheme == "https" and a.hostname and b.hostname and (
        a.hostname.removeprefix("www.") == b.hostname.removeprefix("www.")
    )


def schema_local(html, fuente, url, hoy):
    """Sólo Event JSON-LD con horario, sede y dirección de Rosario."""
    fichas = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas.extend(eventos_schema(json.loads(tag.get_text())))
        except (ValueError, TypeError):
            continue
    eventos = []
    for ficha in fichas:
        loc = ficha.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if not isinstance(loc, dict):
            continue
        lugar, domicilio = loc.get("name", ""), loc.get("address", "")
        if isinstance(domicilio, dict):
            domicilio = domicilio.get("streetAddress", "")
        if not isinstance(lugar, str) or not isinstance(domicilio, str):
            continue
        raw = ficha.get("startDate", "")
        if not isinstance(raw, str) or "T" not in raw:
            continue
        try:
            momento = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if momento.tzinfo:
                momento = momento.astimezone(ZONA)
        except ValueError:
            continue
        if not hoy <= momento.date() <= hoy + timedelta(days=30):
            continue
        if not lugar or not domicilio:
            continue
        ubicacion = normalizar(lugar + " " + domicilio)
        if "rosario" not in ubicacion and not any(
            normalizar(n) in normalizar(lugar) for n, _, _ in SALAS
        ):
            continue
        nombre = ficha.get("name", "")
        if not isinstance(nombre, str) or not nombre.strip():
            continue
        enlace = ficha.get("url") or url
        if not isinstance(enlace, str) or not enlace.startswith("https://"):
            enlace = url
        eventos.append({
            "fecha": momento.date().isoformat(), "hora": momento.strftime("%H:%M"),
            "nombre": nombre, "lugar": lugar,
            "direccion": domicilio + ", Rosario, Santa Fe",
            "descripcion": resumen(str(ficha.get("description", ""))),
            "evento_url": enlace, "precio": None, "origen": fuente,
            "precio_etiqueta": "Precio a confirmar",
        })
    return eventos


def recurrencias_rosario3(html, url, hoy):
    """Extrae patrones inequívocos: 'Los sábados de octubre a las 21 ...'."""
    fecha_url = re.search(r"(20\d{2})(\d{2})(\d{2})-\d+\.html", url)
    if not fecha_url:
        return []
    try:
        publicado = date(*(int(x) for x in fecha_url.groups()))
    except ValueError:
        return []
    if not 0 <= (hoy - publicado).days <= 45:
        return []
    cuerpo = html.select_one("main") or html.select_one("article") or html
    encontrados = []
    for p in cuerpo.select("p"):
        original = texto(p)
        limpio = normalizar(original)
        fecha_match = PATRON_RECURRENTE.search(limpio)
        titulo_match = NOMBRE.search(limpio)
        if not fecha_match or not titulo_match:
            continue
        salas = [(nombre, direccion) for nombre, _, direccion in SALAS
                 if normalizar(nombre) in limpio]
        if len(salas) != 1:
            continue
        mes, dia_semana = MESES[fecha_match[3]], SEMANA[fecha_match[1]]
        hora, minutos = int(fecha_match[4]), int(fecha_match[5] or 0)
        if hora > 23 or minutos > 59:
            continue
        dia_listado = fecha_match[2]
        explicitos = (set(int(x) for x in re.findall(r"\d{1,2}", dia_listado))
                     if dia_listado else None)
        # El índice de caracteres de texto sin tildes no corresponde al original.
        titulo_original = re.search(
            r"se presenta(?:n)?\s+(?:la obra\s+|el espect[aá]culo\s+)?"
            r"(.{2,80}?)(?:,|\.|;|$)", original, re.I
        )
        nombre = (titulo_original[1] if titulo_original else titulo_match[1]).strip()
        if not 2 <= len(nombre) <= 80:
            continue
        sala, domicilio = salas[0]
        for numero in range(1, calendar.monthrange(publicado.year, mes)[1] + 1):
            funcion = date(publicado.year, mes, numero)
            if funcion.weekday() != dia_semana or (explicitos and numero not in explicitos):
                continue
            if not hoy <= funcion <= hoy + timedelta(days=30):
                continue
            encontrados.append({
                "fecha": funcion.isoformat(), "hora": f"{hora:02d}:{minutos:02d}",
                "nombre": nombre, "lugar": sala,
                "direccion": domicilio + ", Rosario, Santa Fe",
                "descripcion": resumen(original), "evento_url": url,
                "precio": None, "origen": "Rosario3",
                "precio_etiqueta": "Precio a confirmar",
            })
    return encontrados



def funciones_prensa(html, fuente, url, hoy):
    """Fecha y hora de la función en un mismo párrafo; año de nota reciente."""
    meta = html.select_one('meta[property="article:published_time"]')
    if not meta or not meta.get("content"):
        return []
    try:
        publicado = datetime.fromisoformat(meta["content"].replace("Z", "+00:00")).date()
    except ValueError:
        return []
    if not 0 <= (hoy - publicado).days <= 45:
        return []
    sedes = [(n, d) for n, _, d in SALAS] + [
        ("Centro Cultural Parque de España", "Sarmiento y el río"),
        ("Teatro Astengo", "Mitre 754"),
        ("Teatro Broadway", "San Lorenzo 1223"),
        ("Metropolitano", "Junín 501"),
        ("Plataforma Lavardén", "Sarmiento y Mendoza"),
        ("Teatro Municipal La Comedia", "Mitre 958"),
    ]
    eventos = []
    cuerpo = html.select_one('.entry-content, .article-body, article, main') or html
    for p in cuerpo.select('p'):
        original = texto(p)
        limpio = normalizar(original)
        lugares = [(n, d) for n, d in sedes if normalizar(n) in limpio]
        if len(lugares) != 1 or re.search(r'cancelad|suspendid|reprogramad', limpio):
            continue
        titulo = re.search(r'^(.{2,100}?)\s+se presentar[aá]\b', original, re.I)
        if not titulo:
            titulo = re.search(r'[“«]([^”»]{2,100})[”»]', original)
        if not titulo:
            continue
        horario_explicito = re.sub(r'(a las?\s+\d{1,2}[.:]\d{2})(?!\d)(?!\s*(?:hs?|horas)\b)', r'\1 hs', original, flags=re.I)
        fechas = fechas_publicadas(horario_explicito.replace(',', ''), hoy, True)
        for fecha, hora in fechas:
            if date.fromisoformat(fecha).year not in (publicado.year, publicado.year + (publicado.month == 12)):
                continue
            nombre, direccion = lugares[0]
            eventos.append(actividad_ampliada(fecha, hora, titulo[1].strip(), url,
                fuente, direccion, original, nombre))
    return eventos

def leer_prensa(fuente, indice, ruta, hoy):
    portada = descargar(indice)
    enlaces = []
    for a in portada.select("a[href]"):
        titular = texto(a)
        link = urljoin(indice, a["href"]).split("#", 1)[0]
        if not mismo_dominio(link, indice) or ruta not in urlsplit(link).path:
            continue
        if not INTERES.search(titular) or "/seccion/" in link or "/secciones/" in link or "/tag/" in link:
            continue
        if link not in enlaces:
            enlaces.append(link)
    # Revisitar notas que todavía sostienen funciones futuras; sin URL fija.
    if ARCHIVO.exists():
        anteriores = json.loads(ARCHIVO.read_text(encoding="utf-8")).get("eventos", [])
        for evento in anteriores:
            link = evento.get("evento_url", "")
            if evento.get("origen") == fuente and evento.get("fecha", "") >= hoy.isoformat() and mismo_dominio(link, indice) and link not in enlaces:
                enlaces.insert(0, link)
    eventos, consultadas, fallidas = [], 0, 0
    for link in enlaces[:14]:
        try:
            articulo = descargar(link)
            eventos.extend(schema_local(articulo, fuente, link, hoy))
            eventos.extend(funciones_prensa(articulo, fuente, link, hoy))
            if fuente == "Rosario3":
                eventos.extend(recurrencias_rosario3(articulo, link, hoy))
            consultadas += 1
        except (requests.RequestException, ValueError, TypeError):
            fallidas += 1
    return eventos, consultadas, fallidas


def leer_atir(hoy, estado):
    nuevos = []
    for nombre, slug, domicilio in SALAS:
        url = f"https://www.teatrosatir.ar/salas/{slug}/"
        try:
            html = descargar(url)
            fichas = []
            for s in html.select('script[type="application/ld+json"]'):
                try:
                    fichas.extend(eventos_schema(json.loads(s.get_text())))
                except (ValueError, TypeError):
                    continue
            if fichas:
                # Algunas páginas individuales muestran la cartelera de otras salas.
                # El calendario existente extrae el lugar real de cada ficha.
                eventos, fallidos = calendario_mec(html, "ATIR", url, domicilio, hoy)
                eventos = [e for e in eventos if nombre_sala(e["lugar"]) == nombre_sala(nombre)]
                nuevos.extend(eventos)
                estado[nombre] = f"revisada: {len(eventos)} funciones propias, {len(fallidos)} errores"
            elif "no events" in normalizar(texto(html)) or html.select(".mec-calendar"):
                estado[nombre] = "revisada: sin funciones propias estructuradas"
            else:
                estado[nombre] = "revisada: sin cartelera interpretable"
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[nombre] = f"no accesible: {type(error).__name__}"
    return nuevos



def calendario_encartel(html, fuente, url, direccion, hoy):
    tarjetas = [a for a in html.select("a[href]") if
                a.select_one("h3.title") or a.parent.get("class") == ["position_info"]]
    if not tarjetas:
        raise ValueError("Cambió el formato de Rosario en Cartel")
    eventos, fallidos, vistos = [], set(), set()
    for a in tarjetas:
        enlace = urljoin(url, a["href"])
        if enlace in vistos or urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        vistos.add(enlace)
        try:
            detalle = descargar(enlace)
            titulo = texto(detalle.select_one(".title-category-form h2"))
            fecha = texto(detalle.select_one(".fecha-col .result-form"))
            hora = hora_visible(texto(detalle.select_one(".horario-col .result-form")))
            lugar = texto(detalle.select_one(".cinema-name"))
            domicilio = texto(detalle.select_one(".cine-list .cinema-dir")) or lugar
            if not titulo or not fecha or not hora or not lugar:
                continue
            # La Comedia se toma de su fuente oficial, que informa suspensiones.
            if "comedia" in normalizar(lugar):
                continue
            fechas = fechas_publicadas(fecha + " " + hora + " hs", hoy)
            descripcion = texto(detalle.select_one(".text-description-other p"))
            precios = texto(detalle.select_one(".cine-list"))
            for dia, horario in fechas:
                e = actividad_ampliada(dia, horario, titulo, enlace, fuente, domicilio,
                      precios, lugar, desde="desde" in normalizar(precios))
                e["descripcion"] = resumen(descripcion)
                eventos.append(e)
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos

def nombre_sala(valor):
    valor = normalizar(valor)
    return re.sub(r"^(?:teatro|sala|espacio)\s+", "", valor).strip()

def calendario_orilla(html, fuente, url, direccion, hoy):
    enlaces = {urljoin(url, a["href"]).lower().rstrip("/") + "/"
               for a in html.select("a[href*='/productos/']")
               if len(urlsplit(urljoin(url, a["href"])).path.strip("/").split("/")) == 2}
    if not enlaces:
        raise ValueError("No se encontraron entradas de la sala")
    eventos, fallidos = [], set()
    for enlace in sorted(enlaces):
        if urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        try:
            detalle = descargar(enlace)
            nodo = detalle.select_one("[data-variants]")
            if not nodo:
                continue
            variantes = json.loads(nodo["data-variants"])
            titulo = texto(detalle.select_one("h1"))
            vistos = set()
            for v in variantes:
                if not v.get("available") or v.get("stock") == 0:
                    continue
                if "general" not in normalizar(v.get("option1") or ""):
                    continue
                opcion = v.get("option0") or ""
                m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\s*[-–]\s*(\d{1,2}:\d{2})", opcion)
                if not m:
                    continue
                anio = int(m[3]) if m[3] else hoy.year + (hoy.month == 12 and int(m[2]) == 1)
                dia = date(anio, int(m[2]), int(m[1]))
                hora = hora_visible(m[4])
                if not hora or not hoy <= dia <= hoy + timedelta(days=30):
                    continue
                clave_funcion = (dia.isoformat(), hora)
                if clave_funcion in vistos:
                    continue
                vistos.add(clave_funcion)
                precio = v.get("price_number")
                if not isinstance(precio, (int, float)) or precio <= 0:
                    continue
                e = evento_extra(dia.isoformat(), hora, titulo, enlace, fuente, direccion,
                                 "Entrada general. Consultá descuentos y disponibilidad en la tienda oficial.", precio, "")
                e["precio_etiqueta"] = f"General ${precio:,.0f}".replace(",", ".")
                eventos.append(e)
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos

def calendario_rayo(html, fuente, url, direccion, hoy):
    eventos = []
    tabs = html.select(".sppb-nav-tabs a[href]")
    if not tabs:
        raise ValueError("Cambió la programación del Rayo")
    for tab in tabs:
        mes_texto = normalizar(texto(tab))
        if mes_texto not in MESES_LISTA:
            continue
        mes = MESES_LISTA.index(mes_texto) + 1
        anio = hoy.year + (hoy.month == 12 and mes == 1)
        panel = html.select_one(tab["href"])
        if not panel:
            continue
        for h in panel.select("h3.sppb-addon-title"):
            spans = h.select("span")
            if len(spans) != 2:
                continue
            regla, titulo = normalizar(texto(spans[0])), texto(spans[1])
            m = re.fullmatch(r"(lunes|martes|miercoles|jueves|viernes|sabados|domingos) de " + mes_texto + r"\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*hs?\.?", regla)
            if not m:
                continue
            dia_semana = DIAS.index(m[1].rstrip("s") if m[1] in ("sabados", "domingos") else m[1])
            hora = hora_visible(f"{m[2]}:{m[3] or '00'}")
            if not hora:
                continue
            for i in range(31):
                dia = hoy + timedelta(days=i)
                if dia.year == anio and dia.month == mes and dia.weekday() == dia_semana:
                    e = evento_extra(dia.isoformat(), hora, titulo, url, fuente, direccion,
                            "Entradas y reservas por el enlace oficial. Consultá el valor vigente.", None, "")
                    eventos.append(e)
    return eventos, set()


# Directorio oficial: se descubren todas las páginas y fichas, no una lista fija.
DIRECTORIO_MUSEOS = "https://www.rosario.tur.ar/donde-ir/cultura/museos"


def fichas_museos(html, base):
    fichas = {}
    for titulo in html.select('h6.titulo'):
        tarjeta = titulo.find_parent(class_='item')
        enlace = tarjeta.select_one('a.vermas[href]') if tarjeta else None
        if enlace:
            url = urljoin(base, enlace['href'])
            if mismo_dominio(url, base) and '/cultura/museos/' in urlsplit(url).path:
                fichas[url] = texto(titulo)
    return fichas


def informacion_museo(html, base):
    direccion, webs = '', []
    bloque = html.select_one('.recverde')
    if bloque:
        contenido = bloque.get_text('\n', strip=True)
        direccion_match = re.search(r'Dirección:\s*([^\n]+)', contenido)
        if direccion_match:
            direccion = direccion_match[1].strip()
        for a in bloque.select('a[href]'):
            # El enlace bajo Web es el sitio de la institución, no redes sociales.
            url = urljoin(base, a['href'])
            if urlsplit(url).scheme in ('http', 'https'):
                webs.append(url.replace('http://', 'https://', 1))
    return direccion, list(dict.fromkeys(webs))


def schema_museo(html, nombre, url, direccion, hoy):
    """Eventos fechados; los horarios generales del museo no son funciones."""
    resultado = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas = list(eventos_schema(json.loads(tag.get_text())))
        except (ValueError, TypeError):
            continue
        for ficha in fichas:
            raw = ficha.get('startDate')
            if not isinstance(raw, str) or 'T' not in raw:
                continue
            try:
                momento = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if momento.tzinfo:
                    momento = momento.astimezone(ZONA)
            except ValueError:
                continue
            if not hoy <= momento.date() <= hoy + timedelta(days=30):
                continue
            if any(x in str(ficha.get('eventStatus', '')) for x in ('Cancelled', 'Postponed', 'Rescheduled')):
                continue
            titulo = ficha.get('name')
            if not isinstance(titulo, str) or not titulo.strip():
                continue
            loc = ficha.get('location') or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            if not isinstance(loc, dict):
                continue
            lugar = loc.get('name') or nombre
            if not isinstance(lugar, str):
                continue
            # Una portada puede mostrar eventos ajenos: sólo aceptar sede compatible.
            aliases = ('castagnino', 'macro', 'memoria', 'estevez', 'ciudad', 'deporte', 'marc', 'gallardo', 'democracia', 'barnes', 'parana', 'islas', 'experimental', 'opera', 'banderas', 'bolsa', 'salud', 'capital', 'beatmemo')
            claves = [normalizar(nombre)] + [n for n in aliases if n in normalizar(nombre)]
            if loc.get('name') and not any(n in normalizar(lugar) for n in claves):
                continue
            domicilio = loc.get('address') or direccion
            if isinstance(domicilio, dict):
                if domicilio.get('addressLocality') and 'rosario' not in normalizar(domicilio['addressLocality']):
                    continue
                domicilio = domicilio.get('streetAddress') or direccion
            if not isinstance(domicilio, str) or not domicilio:
                continue
            enlace = ficha.get('url')
            if not isinstance(enlace, str) or not mismo_dominio(enlace, url):
                enlace = url
            descripcion = str(ficha.get('description') or '')
            if re.search(r'funcion suspendida|evento cancelado', normalizar(descripcion)):
                continue
            precio_texto = descripcion
            if ficha.get('isAccessibleForFree') is True:
                precio_texto += ' Entrada gratuita'
            evento = actividad_ampliada(momento.date().isoformat(), momento.strftime('%H:%M'),
                titulo, enlace, nombre, domicilio, precio_texto, lugar)
            # Un cero genérico en offers no confirma entrada gratuita.
            evento['categorias'] = ['museos']
            # Un importe positivo en pesos puede usarse; el cero requiere gratuidad explícita.
            ofertas = ficha.get('offers') or []
            if isinstance(ofertas, dict):
                ofertas = [ofertas]
            if isinstance(ofertas, list):
                importes = []
                for oferta in ofertas:
                    if not isinstance(oferta, dict) or oferta.get('priceCurrency') != 'ARS':
                        continue
                    try:
                        precio = float(oferta.get('price'))
                    except (TypeError, ValueError):
                        continue
                    if 0 < precio < 50_000_000:
                        importes.append(precio)
                if len(set(importes)) == 1:
                    evento['precio'] = importes[0]
                    evento.pop('precio_etiqueta', None)
            resultado.append(evento)
    return resultado


def leer_museos(hoy, estado):
    fichas, paginas, pendientes = {}, [DIRECTORIO_MUSEOS + '?page=1&lang=es'], set()
    vistas = set()
    while paginas and len(vistas) < 20:
        indice = paginas.pop(0)
        if indice in vistas:
            continue
        vistas.add(indice)
        try:
            html = descargar(indice)
            actuales = fichas_museos(html, indice)
            if not actuales:
                raise ValueError('No se encontraron las fichas del directorio')
            fichas.update(actuales)
            for a in html.select('a[href*="page="]'):
                link = urljoin(indice, a['href'])
                if mismo_dominio(link, DIRECTORIO_MUSEOS) and urlsplit(link).path == urlsplit(DIRECTORIO_MUSEOS).path and link not in vistas:
                    pagina = parse_qs(urlsplit(link).query).get('page', [''])[0]
                    if pagina.isdigit():
                        canonica = DIRECTORIO_MUSEOS + '?page=' + pagina + '&lang=es'
                        if canonica not in vistas and canonica not in paginas:
                            paginas.append(canonica)
        except (requests.RequestException, ValueError, TypeError):
            pendientes.add(indice)
    # El museo urbano municipal no aparece en el catálogo de ETUR.
    fichas['https://www.rosario.gob.ar/inicio/museos-municipales'] = 'Museo Urbano Arte a la Vista'
    eventos, detalle_revision, cache_webs = [], [], {}
    def consultar_web(link):
        if link not in cache_webs:
            cache_webs[link] = descargar(link)
        return cache_webs[link]
    for url, nombre in fichas.items():
        revision = {'nombre': nombre, 'ficha': url, 'estado': 'revisado', 'actividades': 0}
        try:
            html = descargar(url)
            direccion, webs = informacion_museo(html, url)
            revision['webs'] = webs
            nuevos = []
            for web in webs:
                try:
                    portada = consultar_web(web)
                    nuevos.extend(schema_museo(portada, nombre, web, direccion, hoy))
                    enlaces = []
                    for a in portada.select('a[href]'):
                        link = urljoin(web, a['href']).split('#', 1)[0]
                        if mismo_dominio(link, web) and link != web and re.search(
                            r'agenda|actividad|programacion|evento|exposicion|muestra|visita|noticias|setsede',
                            normalizar(texto(a)) + ' ' + urlsplit(link).path,
                        ) and link not in enlaces:
                            enlaces.append(link)
                    profundas = 0
                    for link in enlaces[:6]:
                        try:
                            pagina = consultar_web(link)
                            nuevos.extend(schema_museo(pagina, nombre, link, direccion, hoy))
                            # También seguir fichas enlazadas desde la sección Agenda.
                            fichas_eventos = []
                            for a in pagina.select('h2 a[href], h3 a[href]'):
                                detalle = urljoin(link, a['href'])
                                if mismo_dominio(detalle, web) and detalle not in enlaces and detalle not in fichas_eventos:
                                    fichas_eventos.append(detalle)
                            for detalle in fichas_eventos[:max(0, 4 - profundas)]:
                                profundas += 1
                                nuevos.extend(schema_museo(consultar_web(detalle), nombre, detalle, direccion, hoy))
                        except (requests.RequestException, ValueError, TypeError):
                            revision['estado'] = 'revisión parcial'
                except (requests.RequestException, ValueError, TypeError):
                    revision['estado'] = 'web pendiente de consulta'
            propios = {clave(e): e for e in nuevos}
            eventos.extend(propios.values())
            revision['actividades'] = len(propios)
            if not propios and revision['estado'] == 'revisado':
                revision['estado'] = 'sin eventos fechados interpretables; también consultar la agenda municipal'
        except (requests.RequestException, ValueError, TypeError):
            revision['estado'] = 'ficha pendiente de consulta'
        detalle_revision.append(revision)
        estado[nombre] = f"{revision['estado']}: {revision['actividades']} actividades"
    estado['Directorio de museos'] = f'{len(fichas)} espacios descubiertos; {len(pendientes)} páginas pendientes'
    return eventos, detalle_revision


ESPACIOS_SEGUIDOS = (
    ('Circo Rodas', ('circo rodas',), 'Linke-arte y Rosario en Cartel', 'Av. Circunvalación, Rosario, Santa Fe'),
    ('La Surfera Beach', ('surfera',), 'Agenda municipal y Rosario en Cartel', 'Av. Costanera 2558, Granadero Baigorria, Santa Fe'),
    ('Espacio Bravo', ('espacio bravo',), 'ATIR y prensa cultural', 'Catamarca 3624, Rosario, Santa Fe'),
    ('Teatro del Rayo', ('teatro del rayo', 'rayo misterioso'), 'Web del Rayo y ATIR', 'Salta 2991, Rosario, Santa Fe'),
    ('La Morada', ('la morada',), 'ATIR y prensa cultural', 'San Martín 771, Rosario, Santa Fe'),
    ('Complejo Cultural Atlas', ('complejo cultural atlas',), 'CentroTicket, venta enlazada por Atlas', 'Mitre 645, Rosario, Santa Fe'),
    ('La Segunda Seguros Arena', ('la segunda seguros arena', 'bioceres arena', 'l2 arena'), 'Entrada Play y Rosario en Cartel', 'Córdoba 3475, Rosario, Santa Fe'),
    ('Estadio Central Córdoba', ('central cordoba', 'gabino sosa'), 'Entrada Play y agendas culturales', 'Estadio Gabino Sosa, Rosario, Santa Fe'),
)


def espacio_seguido(lugar):
    nombre = normalizar(lugar)
    return next((e for e in ESPACIOS_SEGUIDOS if any(alias in nombre for alias in e[1])), None)


def descargar_catalogo(url):
    """La misma consulta GET pública que realiza el catálogo de venta."""
    from actualizar_eventos import SESION, BLOQUEADOS, ULTIMA, monotonic, sleep
    host = urlsplit(url).hostname
    if host in BLOQUEADOS:
        raise requests.RequestException('Fuente pausada en esta revisión')
    espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))
    if espera > 0:
        sleep(espera)
    try:
        respuesta = SESION.get(url, timeout=(10, 25))
        if respuesta.status_code in (403, 429):
            BLOQUEADOS.add(host)
        respuesta.raise_for_status()
        return respuesta.json()
    finally:
        ULTIMA[host] = monotonic()


def eventos_catalogo(datos, base, proveedor, hoy):
    filas = datos.get('eventos')
    if not isinstance(filas, list):
        raise ValueError('Cambió el catálogo de entradas')
    resultado, pendientes = [], 0
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        sede = fila.get('lugar') or ''
        espacio = espacio_seguido(sede)
        if not espacio or not re.search(r'rosario|baigorria', normalizar(sede)):
            continue
        # Las carteleras con varias funciones sólo informan la primera fecha.
        if fila.get('unica_fecha') is not True:
            pendientes += 1
            continue
        try:
            instante = datetime.strptime(fila.get('desde_fecha', ''), '%d/%m/%Y, %H:%M')
        except (ValueError, TypeError):
            pendientes += 1
            continue
        if not hoy <= instante.date() <= hoy + timedelta(days=30):
            continue
        titulo, slug = fila.get('nombre'), fila.get('slug')
        if not isinstance(titulo, str) or not isinstance(slug, str) or not titulo or not slug:
            continue
        enlace = urljoin(base, slug.strip('/') + '/')
        if not mismo_dominio(enlace, base):
            continue
        descripcion = texto(BeautifulSoup(fila.get('descripcion_evento') or titulo, 'html.parser'))
        evento = actividad_ampliada(instante.date().isoformat(), instante.strftime('%H:%M'),
            titulo, enlace, proveedor, espacio[3], descripcion, espacio[0])
        evento['entradas_url'] = enlace
        evento['entrada_paga'] = True
        evento['funcion_unica_verificada'] = True
        try:
            precio = float(fila.get('entradas_online_desde'))
        except (ValueError, TypeError):
            precio = None
        # Cero, ausencia de cifra o texto promocional no confirman gratuidad.
        moneda = fila.get('moneda') or datos.get('moneda')
        if precio and 0 < precio < 50_000_000 and moneda == 'ARS':
            evento['precio'] = precio
            evento['precio_etiqueta'] = f'Desde ${precio:,.0f}'.replace(',', '.')
        else:
            evento['precio'] = None
            evento['precio_etiqueta'] = 'Precio a confirmar'
        resultado.append(evento)
    return resultado, pendientes


def leer_rodas(html, url, hoy):
    """Fechas efectivamente habilitadas en el selector; nunca expande horarios genéricos."""
    script = str(html)
    patron = r'window\[`linkearte_map_landing_widget_Sessions_.*?`\]\s*=\s*'
    grupos = []
    for match in re.finditer(patron, script):
        try:
            valor, _ = json.JSONDecoder().raw_decode(script[match.end():])
            grupos.extend(valor)
        except ValueError:
            continue
    sesiones = []
    for grupo in grupos:
        sesiones.extend(grupo if isinstance(grupo, list) else [grupo])
    if not sesiones:
        raise ValueError('No se encontraron funciones vendidas por el circo')
    contenido = texto(html)
    precio_texto = ' '.join(m[0] for m in re.finditer(r'(?:Platea|Preferencia lateral|Preferencia frontal|Palco lateral|Palco frontal|VIP)\s*:\s*\$[\d.]+', contenido, re.I))
    eventos = {}
    for sesion in sesiones:
        if not isinstance(sesion, dict):
            continue
        sede = normalizar(str(sesion.get('litSala', '')))
        if 'rodas' not in sede or 'rosario' not in sede or sesion.get('streamingOnly') is True:
            continue
        capacidad = [sesion.get(c) for c in ('aforo', 'entradasVendidas', 'entradasReservadas', 'entradasBloqueadas')]
        if all(isinstance(v, (int, float)) for v in capacidad) and capacidad[0] - sum(capacidad[1:]) <= 0:
            continue
        try:
            instante = datetime.fromisoformat(sesion.get('fechaCelebracionRecinto') or '')
        except (ValueError, TypeError):
            continue
        if not hoy <= instante.date() <= hoy + timedelta(days=30):
            continue
        evento = actividad_ampliada(instante.date().isoformat(), instante.strftime('%H:%M'),
            'Circo Rodas', url, 'Circo Rodas — Linke-arte', ESPACIOS_SEGUIDOS[0][3],
            precio_texto, 'Circo Rodas')
        evento['descripcion'] = 'Espectáculo circense para toda la familia. Consultá sectores, promociones y disponibilidad en la venta oficial.'
        evento['entradas_url'] = url
        evento['entrada_paga'] = True
        evento['categorias'] = ['infancias']
        eventos[clave(evento)] = evento
    return list(eventos.values())


def categorias_espacio(titulo, descripcion):
    contenido = normalizar(titulo + ' ' + descripcion)
    categorias = []
    patrones = {
        'musica': r'musica|musical|concierto|recital|orquesta|\bbanda|rock|jazz|cumbia|swing|folklore|blues|cantante|cantora|discograf|guitarrista|pianista|bandoneon|angela torres|ke personajes|\bbresh\b|nocheros|sergio dalma',
        'teatro': r'teatr|stand.?up|humor|comedia|unipersonal',
        'cine': r'pelicula|documental|proyeccion|cinematograf',
        'libros': r'\blibro|lectura|charla|conferencia',
        'danza': r'danza|ballet|flamenco|milonga',
        'infancias': r'infancias|infantil|titeres|para toda la familia',
    }
    for categoria, patron in patrones.items():
        if re.search(patron, contenido):
            categorias.append(categoria)
    return categorias


def leer_espacios_extra(hoy, estado):
    nuevos = []
    for proveedor, base in (('Entrada Play', 'https://entradaplay.com/'),
                            ('CentroTicket', 'https://centroticket.com.ar/')):
        try:
            datos = descargar_catalogo(urljoin(base, 'obtener_eventos/?cantidad_eventos=100'))
            funciones, pendientes = eventos_catalogo(datos, base, proveedor, hoy)
            for evento in funciones:
                try:
                    ficha = descargar(evento['evento_url'])
                    cuerpo = ficha.select_one('.col-12.text-center.mt-3 > div.mt-3')
                    descripcion = texto(cuerpo)
                    if descripcion:
                        evento['descripcion'] = resumen(descripcion)
                    categorias = categorias_espacio(evento['nombre'], descripcion)
                    if categorias:
                        evento['categorias'] = categorias
                except (requests.RequestException, ValueError, TypeError):
                    pendientes += 1
                    categorias = categorias_espacio(evento['nombre'], '')
                    if categorias:
                        evento['categorias'] = categorias
            nuevos.extend(funciones)
            estado[proveedor] = f'revisada: {len(funciones)} funciones; {pendientes} fichas pendientes'
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[proveedor] = f'no accesible: {type(error).__name__}'
    url = 'https://linke-arte.com/arg/es/circo-rodas-rosario'
    try:
        funciones = leer_rodas(descargar(url), url, hoy)
        nuevos.extend(funciones)
        estado['Circo Rodas — Linke-arte'] = f'revisada: {len(funciones)} funciones habilitadas'
    except (requests.RequestException, ValueError, TypeError) as error:
        estado['Circo Rodas — Linke-arte'] = f'no accesible: {type(error).__name__}'
    return nuevos


def misma_propuesta(a, b):
    sede_a, sede_b = espacio_seguido(a.get('lugar', '')), espacio_seguido(b.get('lugar', ''))
    if not sede_a or not sede_b or sede_a[0] != sede_b[0]:
        return False
    def titulo(e):
        return ' '.join(re.findall(r'\w+', normalizar(e.get('nombre', ''))))
    na, nb = titulo(a), titulo(b)
    return na == nb or min(len(na), len(nb)) >= 8 and (na in nb or nb in na)


def preferir_venta_oficial(eventos, nuevos):
    # Sólo corrige fechas secundarias si el vendedor afirma que hay una única función.
    verificados = [e for e in nuevos if e.get('funcion_unica_verificada')]
    return [e for e in eventos if not (e.get('origen') == 'Rosario en Cartel' and
            any(misma_propuesta(e, n) and (e['fecha'], e['hora']) != (n['fecha'], n['hora']) for n in verificados))]

# Una ficha comprobada sirve de arranque y deja de consultarse al finalizar su edición.
SEMILLAS_ESPACIOS = (
    ('https://www.rosario.gob.ar/inicio/festival-gualicho-cofradia-encuentro-y-fiesta-ricotera', date(2026, 10, 17)),
)


def municipal_espacios(html, url, hoy):
    from actualizar_eventos import ubicacion, fechas_regla
    titulo = texto(html.select_one('main h1, h1'))
    descripcion = texto(html.select_one('.descripcion'))
    eventos = {}
    for bloque in html.select('.cuando-fechas'):
        lugar, direccion = ubicacion(bloque)
        espacio = espacio_seguido(lugar)
        if not espacio:
            continue
        fechas = []
        for regla in bloque.select('.rule'):
            fechas.extend(fechas_regla(regla, hoy))
        for instante in bloque.select('time[datetime]'):
            if not instante.select_one('.hora-desde'):
                continue
            momento = datetime.fromisoformat(instante['datetime'])
            if momento.tzinfo:
                momento = momento.astimezone(ZONA)
            if hoy <= momento.date() <= hoy + timedelta(days=30):
                fechas.append((momento.date().isoformat(), momento.strftime('%H:%M')))
        paga = bool(re.search(r'\bpaga\b', normalizar(texto(bloque))))
        for fecha, hora in fechas:
            evento = actividad_ampliada(fecha, hora, titulo, url, 'Agenda municipal — Espacios',
                espacio[3], descripcion, espacio[0])
            evento['direccion'] = espacio[3]
            if paga:
                if evento['precio'] == 0:
                    evento['precio'] = None
                evento['entrada_paga'] = True
                if evento['precio'] is None:
                    evento['precio_etiqueta'] = 'Pago'
            compra = next((urljoin(url, a['href']) for a in html.select('.descripcion a[href]')
                           if 'entrada' in normalizar(texto(a)) and urlsplit(urljoin(url, a['href'])).scheme == 'https'), None)
            if compra:
                evento['entradas_url'] = compra
            categorias = categorias_espacio(titulo, descripcion)
            if categorias:
                evento['categorias'] = categorias
            eventos[clave(evento)] = evento
    return list(eventos.values())


def leer_municipal_espacios(hoy, estado):
    candidatos = {url for url, hasta in SEMILLAS_ESPACIOS if hoy <= hasta}
    # Revisitar fichas publicadas de estos espacios sin depender de una fecha mensual.
    if ARCHIVO.exists():
        anteriores = json.loads(ARCHIVO.read_text(encoding='utf-8')).get('eventos', [])
        candidatos.update(e['evento_url'] for e in anteriores if e.get('fecha', '') >= hoy.isoformat()
            and espacio_seguido(e.get('lugar', '')) and e.get('evento_url', '').startswith('https://www.rosario.gob.ar/inicio/'))
    nuevos, fallidos = [], 0
    for url in sorted(candidatos):
        try:
            nuevos.extend(municipal_espacios(descargar(url), url, hoy))
        except (requests.RequestException, ValueError, TypeError):
            fallidos += 1
    estado['Agenda municipal — Espacios'] = f'revisada: {len(nuevos)} funciones; {fallidos} fichas pendientes'
    return nuevos

FERIA_LIBRO_URL = "https://feriadellibrorosario.gob.ar/"
MICROTEATRO_URL = "https://www.microteatrorosario.com/"


def leer_feria_libro(hoy, estado):
    """Lee del sitio oficial el período y los horarios diarios de la Feria."""
    fuente = "Feria Internacional del Libro de Rosario"
    try:
        pagina = normalizar(texto(descargar(FERIA_LIBRO_URL)))
        periodo = re.search(
            r"del?\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            pagina,
        )
        if not periodo:
            raise ValueError("no se encontró el período publicado")
        dia_inicio, dia_fin, nombre_mes, anio = periodo.groups()
        mes = MESES.get(nombre_mes)
        if not mes:
            raise ValueError("mes del período no reconocido")
        inicio = date(int(anio), mes, int(dia_inicio))
        fin = date(int(anio), mes, int(dia_fin))

        horarios = {}
        reglas = (
            (r"de lunes a miercoles de (\d{1,2}) a (\d{1,2})h", {0, 1, 2}),
            (r"jueves y viernes de (\d{1,2}) a (\d{1,2})h", {3, 4}),
            (r"sabados? de (\d{1,2}) a (\d{1,2})h", {5}),
        )
        for patron, dias in reglas:
            coincidencia = re.search(patron, pagina)
            if coincidencia:
                apertura, cierre = map(int, coincidencia.groups())
                for dia in dias:
                    horarios[dia] = (apertura, cierre)

        for dia, mes_texto, apertura, cierre in re.findall(
            r"domingo (\d{1,2}) de ([a-z]+) de (\d{1,2}) a (\d{1,2})h",
            pagina,
        ):
            mes_domingo = MESES.get(mes_texto)
            if mes_domingo == mes:
                fecha_domingo = date(int(anio), mes_domingo, int(dia))
                horarios[fecha_domingo.weekday()] = (int(apertura), int(cierre))

        descripcion_base = (
            "Feria con stands de librerías y editoriales, presentaciones, charlas y "
            "actividades para todas las edades. Entrada gratuita con QR."
        )
        eventos = []
        actual = max(inicio, hoy)
        limite = min(fin, hoy + timedelta(days=30))
        while actual <= limite:
            horario = horarios.get(actual.weekday())
            if horario:
                apertura, cierre = horario
                hora = f"{apertura:02d}:00"
                fin_visible = f"{cierre:02d}:00"
                eventos.append({
                    "fecha": actual.isoformat(),
                    "hora": hora,
                    "nombre": fuente,
                    "lugar": "Centro Cultural Roberto Fontanarrosa",
                    "direccion": "San Martín 1080, Rosario, Santa Fe",
                    "descripcion": (
                        f"{descripcion_base} Horario oficial: {hora} a {fin_visible}."
                    ),
                    "evento_url": FERIA_LIBRO_URL,
                    "precio": 0,
                    "origen": fuente,
                    "categorias": ["ferias"],
                })
            actual += timedelta(days=1)
        if not eventos:
            raise ValueError("sin jornadas futuras con horario publicado")
        estado[fuente] = f"revisada: {len(eventos)} jornadas; fuente oficial"
        return eventos
    except (requests.RequestException, ValueError, TypeError) as error:
        estado[fuente] = f"no accesible: {type(error).__name__}"
        return []


def importe_microteatro(valor, meta=False):
    """Convierte precios de Tiendanube, ignorando importes en cero."""
    if not isinstance(valor, str):
        return None
    if meta:
        try:
            numero = float(valor.strip().replace(",", "."))
            return numero if 0 < numero < 50_000_000 else None
        except ValueError:
            return None

    for encontrado in re.finditer(r"\$\s*([\d.]+(?:,[0-9]{1,2})?)", valor):
        numero = encontrado[1].replace(".", "").replace(",", ".")
        try:
            resultado = float(numero)
        except ValueError:
            continue
        if 0 < resultado < 50_000_000:
            return resultado
    return None


def leer_microteatro(hoy, estado):
    """Lee productos públicos de Microteatro y expande fechas/horarios disponibles."""
    fuente = "Microteatro Rosario"
    indice = urljoin(MICROTEATRO_URL, "productos/")
    eventos, pendientes, revisadas = {}, 0, 0
    try:
        portada = descargar(indice)
        enlaces = []
        for a in portada.select("a[href]"):
            enlace = urljoin(indice, a["href"]).split("#", 1)[0]
            ruta = urlsplit(enlace).path
            if (mismo_dominio(enlace, indice) and ruta.startswith("/productos/")
                    and ruta != "/productos/" and enlace not in enlaces):
                enlaces.append(enlace)
        if not enlaces:
            raise ValueError("no se encontraron productos de la cartelera")

        for enlace in enlaces[:40]:
            try:
                ficha = descargar(enlace)
                titulo = texto(ficha.select_one("h1"))
                if not titulo:
                    pendientes += 1
                    continue
                formulario = (ficha.select_one(".product_form, .product-form, "
                    ".js-product-form, form[action*='cart']") or ficha)
                texto_formulario = texto(formulario)
                normalizado = normalizar(texto_formulario)
                posicion_horarios = normalizado.find("horarios")
                if posicion_horarios < 0:
                    pendientes += 1
                    continue
                fechas_raw = set(re.findall(
                    r"\b(\d{2}/\d{2}/\d{4})\b", texto_formulario
                ))
                fechas = []
                for fecha_raw in fechas_raw:
                    try:
                        fecha = datetime.strptime(fecha_raw, "%d/%m/%Y").date()
                    except ValueError:
                        continue
                    if hoy <= fecha <= hoy + timedelta(days=30):
                        fechas.append(fecha)
                horas_segmento = texto_formulario[posicion_horarios:posicion_horarios + 300]
                horas = sorted(set(re.findall(
                    r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)", horas_segmento
                )))
                if not fechas or not horas:
                    continue

                precio = None
                for nodo in ficha.select(
                    'meta[itemprop="price"], meta[property="product:price:amount"]'
                ):
                    precio = importe_microteatro(nodo.get("content"), meta=True)
                    if precio:
                        break
                if not precio:
                    for selector in (
                        '[itemprop="price"]', ".js-price-display", ".price-display",
                        ".product-price", "[data-product-price]",
                    ):
                        nodo = ficha.select_one(selector)
                        if nodo:
                            precio = importe_microteatro(
                                nodo.get("content") or nodo.get("data-product-price") or texto(nodo)
                            )
                            if precio:
                                break
                if not precio:
                    texto_pagina = texto(ficha)
                    inicio_titulo = texto_pagina.find(titulo)
                    zona_precio = texto_pagina[inicio_titulo + len(titulo):inicio_titulo + len(titulo) + 180]
                    precio = importe_microteatro(zona_precio)

                descripcion_nodo = ficha.select_one(
                    ".product-description, .product_description, [itemprop='description']"
                )
                descripcion = texto(descripcion_nodo) if descripcion_nodo else ""
                if precio:
                    precio_etiqueta = "$" + f"{precio:,.0f}".replace(",", ".")
                    texto_precio = f"Entrada: {precio_etiqueta}. "
                else:
                    precio_etiqueta = "Precio a confirmar"
                    texto_precio = "Entrada paga; consultar precio en la ficha oficial. "

                for fecha in fechas:
                    for hora in horas:
                        evento = actividad_ampliada(
                            fecha.isoformat(), hora, titulo, enlace, fuente,
                            "San Lorenzo 1329, Rosario, Santa Fe",
                            texto_precio + descripcion, fuente,
                        )
                        evento["precio"] = precio
                        evento["precio_etiqueta"] = precio_etiqueta
                        evento["entrada_paga"] = True
                        evento["categorias"] = ["teatro"]
                        eventos[clave(evento)] = evento
                revisadas += 1
            except (requests.RequestException, ValueError, TypeError):
                pendientes += 1
        estado[fuente] = (
            f"revisada: {len(eventos)} funciones en {revisadas} obras; "
            f"{pendientes} fichas pendientes"
        )
        return list(eventos.values())
    except (requests.RequestException, ValueError, TypeError) as error:
        estado[fuente] = f"no accesible: {type(error).__name__}"
        return []


FUENTES_CSV = (
    ('Teatro Broadway', 'teatro', 'https://teatrobroadwayrosario.com/', 'alta'),
    ('Complejo Cultural Atlas', 'centro cultural', 'https://ccatlas.org.ar/', 'alta'),
    ('Teatro Municipal La Comedia', 'teatro municipal', 'https://teatrolacomedia.gob.ar/', 'alta'),
    ('Centro Cultural Roberto Fontanarrosa', 'centro cultural municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('Feria Internacional del Libro de Rosario', 'feria del libro', 'https://feriadellibrorosario.gob.ar/', 'alta'),
    ('Microteatro Rosario', 'teatro', 'https://www.microteatrorosario.com/productos/', 'alta'),
    ('Plataforma Lavarden', 'centro cultural provincial', 'https://plataformalavarden.gob.ar/', 'alta'),
    ('Teatro El Circulo', 'teatro', 'https://www.teatroelcirculo.com/home', 'alta'),
    ('Teatro Astengo', 'teatro', 'https://teatroastengo.ar/agenda-espectaculos/', 'alta'),
    ('Metropolitano Rosario', 'salon/eventos', 'https://www.metropolitanoros.com.ar/', 'alta'),
    ('La Segunda Seguros Arena', 'arena/eventos', 'https://www.instagram.com/bioceresarena/', 'alta'),
    ('Anfiteatro Municipal Humberto de Nito', 'anfiteatro municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('Estadio Central Cordoba', 'estadio/club', 'https://www.centralcordoba.com.ar/', 'media'),
    ('Club Atletico Provincial', 'club/eventos', 'https://www.clubprovincial.com.ar/', 'media'),
    ('El Cairo Cine Publico', 'cine municipal', 'https://www.rosario.gob.ar/inicio/cine-el-cairo', 'alta'),
    ('Centro Cultural Parque de Espana', 'centro cultural', 'https://www.ccpe.org.ar/', 'alta'),
    ('Centro de Expresiones Contemporaneas', 'centro cultural municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('Centro Cultural Cine Lumiere', 'cine/centro cultural municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('Galpon de la Musica', 'centro cultural municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('Complejo Astronomico Municipal', 'espacio municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'alta'),
    ('La Granja de la Infancia', 'espacio municipal', 'https://www.rosario.gob.ar/inicio/triptico-de-la-infancia', 'media'),
    ('El Jardin de los Ninos', 'espacio municipal', 'https://www.rosario.gob.ar/inicio/triptico-de-la-infancia', 'media'),
    ('La Isla de los Inventos', 'espacio municipal', 'https://www.rosario.gob.ar/inicio/triptico-de-la-infancia', 'media'),
    ('Museo Castagnino', 'museo', 'https://castagninomacro.org/', 'alta'),
    ('Museo Macro', 'museo', 'https://castagninomacro.org/', 'alta'),
    ('Museo de la Ciudad', 'museo municipal', 'https://www.rosario.gob.ar/inicio/museos-municipales', 'alta'),
    ('Museo Estevez', 'museo municipal', 'https://www.rosario.gob.ar/inicio/museos-municipales', 'alta'),
    ('Museo de la Memoria', 'museo', 'https://www.museodelamemoria.gob.ar/', 'alta'),
    ('Museo Historico Provincial Julio Marc', 'museo provincial', 'https://www.santafe.gob.ar/index.php/web/content/view/full/93664', 'media'),
    ('Museo de Arte Sacro Eduardo Barnes', 'museo', 'https://www.teatroelcirculo.com/', 'media'),
    ('Sala Cultural de Abajo', 'sala independiente', 'https://www.instagram.com/salaculturaldeabajo/', 'media'),
    ('Teatro del Rayo', 'sala independiente', 'https://www.elrayomisterioso.org.ar/', 'media'),
    ('Espacio Bravo', 'sala independiente', 'https://www.instagram.com/espaciobravorosario/', 'media'),
    ('Teatro La Morada', 'sala independiente', 'https://www.facebook.com/pages/La-Morada-Teatro/653965228022129', 'media'),
    ('La Orilla Infinita', 'sala independiente', 'https://www.instagram.com/laorillainfinita/', 'media'),
    ('Circo Rodas', 'circo itinerante', 'https://www.instagram.com/circorodasoficial/', 'media'),
    ('La Surfera Beach', 'bar/espacio', 'https://www.instagram.com/lasurferabeach/', 'media'),
    ('Bar El Cairo', 'bar cultural', 'https://www.instagram.com/barelcairorosario/', 'media'),
    ('Casa de la Cultura Arijon', 'centro cultural municipal', 'https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros', 'media'),
    ('ECU Espacio Cultural Universitario', 'espacio universitario', 'https://www.unr.edu.ar/', 'media'),
    ('Monumento Nacional a la Bandera', 'espacio patrimonial', 'https://www.rosario.gob.ar/inicio/monumento-nacional-la-bandera', 'media'),
    ('Mercado del Patio', 'mercado/espacio', 'https://www.mercadodelpatio.gob.ar/', 'media'),
    ('Alto Rosario Shopping', 'shopping', 'https://www.altorosario.com.ar/', 'baja'),
    ('Diferentes ambitos de Rosario', 'variable', 'https://www.rosario.gob.ar/inicio/agenda', 'baja'),
)

# Fuente aportada: fuentes_oficiales_agenda_rosario.csv. Se mantiene el enlace original
# y se registra por separado la agenda específica usada para consultar.

CSV_AGENDAS = (
    ('Teatro El Circulo', 'https://www.teatroelcirculo.com/home', 'https://www.teatroelcirculo.com/tambi%C3%A9nenelcirculo', ''),
    ('Club Atletico Provincial', 'https://www.clubprovincial.com.ar/', '', ''),
    ('ECU Espacio Cultural Universitario', 'https://unr.edu.ar/agenda/', '', 'San Martín 750, Rosario, Santa Fe'),
    ('Mercado del Patio', 'https://mercadodelpatio.gob.ar/', '', ''),
    ('Alto Rosario Shopping', 'https://www.altorosario.com.ar/', '', ''),
)


def descargar_texto_publico(url):
    from actualizar_eventos import SESION, BLOQUEADOS, ULTIMA, monotonic, sleep
    host = urlsplit(url).hostname
    if host in BLOQUEADOS:
        raise requests.RequestException('Fuente pausada en esta revisión')
    espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))
    if espera > 0:
        sleep(espera)
    try:
        respuesta = SESION.get(url, timeout=(8, 15))
        if respuesta.status_code in (403, 429):
            BLOQUEADOS.add(host)
        respuesta.raise_for_status()
        respuesta.encoding = 'utf-8'
        return respuesta.text
    finally:
        ULTIMA[host] = monotonic()


def eventos_calendario_ics(contenido, hoy):
    """Lee fechas completas de calendarios públicos, incluyendo líneas plegadas."""
    if 'BEGIN:VCALENDAR' not in contenido:
        raise ValueError('La fuente no devolvió un calendario')
    contenido = re.sub(r'\r?\n[ \t]', '', contenido)
    eventos = []
    for bloque in re.findall(r'BEGIN:VEVENT\s*\n(.*?)END:VEVENT', contenido, re.S):
        propiedades = {}
        for linea in bloque.splitlines():
            if ':' not in linea:
                continue
            nombre, valor = linea.split(':', 1)
            propiedades[nombre] = valor.replace(r'\n', '\n').replace(r'\,', ',').replace(r'\;', ';').strip()
        if propiedades.get('STATUS') in ('CANCELLED', 'TENTATIVE'):
            continue
        fecha_campo = next((k for k in propiedades if k == 'DTSTART' or k.startswith('DTSTART;')), '')
        raw = propiedades.get(fecha_campo, '')
        # Fechas sin horario y reglas recurrentes requieren un parser específico.
        if 'T' not in raw or 'RRULE' in propiedades or 'RDATE' in propiedades:
            continue
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            momento = datetime.strptime(raw.rstrip('Z'), '%Y%m%dT%H%M%S')
            tz = re.search(r'TZID=([^;]+)', fecha_campo)
            zona = ZoneInfo('UTC') if raw.endswith('Z') else ZoneInfo(tz[1].strip(chr(34))) if tz else ZONA
            momento = momento.replace(tzinfo=zona).astimezone(ZONA)
        except (ValueError, ZoneInfoNotFoundError):
            continue
        if not hoy <= momento.date() <= hoy + timedelta(days=30):
            continue
        titulo = propiedades.get('SUMMARY')
        if titulo:
            eventos.append({'fecha': momento.date().isoformat(), 'hora': momento.strftime('%H:%M'),
                'nombre': titulo, 'evento_url': propiedades.get('URL', ''),
                'descripcion': propiedades.get('DESCRIPTION', '')})
    return eventos


def leer_cairo(hoy):
    base = 'https://elcairocinepublico.gob.ar/'
    meses = {hoy.strftime('%Y-%m'), (hoy + timedelta(days=30)).strftime('%Y-%m')}
    eventos, errores, cache = {}, 0, {}
    for mes in sorted(meses):
        # El formato de la navegación mensual y la exportación son enlaces públicos del cine.
        url = urljoin(base, f'cartelera-de-sala/{mes}/?ical=1')
        try:
            funciones = eventos_calendario_ics(descargar_texto_publico(url), hoy)
            for funcion in funciones:
                enlace = funcion['evento_url']
                if not mismo_dominio(enlace, base):
                    enlace = urljoin(base, 'cartelera-de-sala/')
                descripcion, precio_texto = funcion['descripcion'], ''
                if enlace != urljoin(base, 'cartelera-de-sala/'):
                    try:
                        if enlace not in cache:
                            cache[enlace] = descargar(enlace)
                        ficha = cache[enlace]
                        # Sólo el rótulo de entrada, no el año de la película ni precios relacionados.
                        titulo_precio = next((h for h in ficha.select('h2, h3, h4') if normalizar(texto(h)).strip(': ') == 'entrada'), None)
                        if titulo_precio:
                            valores = []
                            for nodo in titulo_precio.next_siblings:
                                if getattr(nodo, 'name', '') in ('h1', 'h2', 'h3', 'h4'):
                                    break
                                if getattr(nodo, 'get_text', None):
                                    valores.append(texto(nodo))
                                elif isinstance(nodo, str):
                                    valores.append(nodo.strip())
                                if len(valores) >= 2:
                                    break
                            precio_texto = ' '.join(valores)
                    except (requests.RequestException, ValueError):
                        errores += 1
                evento = actividad_ampliada(funcion['fecha'], funcion['hora'], funcion['nombre'], enlace,
                    'El Cairo Cine Público', 'Santa Fe 1120, Rosario, Santa Fe', precio_texto,
                    'El Cairo Cine Público')
                evento['descripcion'] = resumen(texto(BeautifulSoup(descripcion, 'html.parser')))
                evento['categorias'] = ['cine']
                eventos[clave(evento)] = evento
        except (requests.RequestException, ValueError):
            errores += 1
    return list(eventos.values()), errores


def eventos_schema_culturales(valor):
    tipos_evento = {'Event', 'MusicEvent', 'TheaterEvent', 'ScreeningEvent', 'ExhibitionEvent',
                    'DanceEvent', 'EducationEvent', 'Festival', 'SportsEvent'}
    if isinstance(valor, list):
        for item in valor:
            yield from eventos_schema_culturales(item)
    elif isinstance(valor, dict):
        tipos = valor.get('@type')
        tipos = [tipos] if isinstance(tipos, str) else tipos if isinstance(tipos, list) else []
        if set(t for t in tipos if isinstance(t, str)) & tipos_evento:
            yield valor
        for item in valor.values():
            if isinstance(item, (list, dict)):
                yield from eventos_schema_culturales(item)


def schema_csv(html, fuente, url, direccion, hoy):
    eventos = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas = list(eventos_schema_culturales(json.loads(tag.get_text())))
        except (ValueError, TypeError):
            continue
        for ficha in fichas:
            raw = ficha.get('startDate')
            if not isinstance(raw, str) or 'T' not in raw:
                continue
            try:
                instante = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if instante.tzinfo:
                    instante = instante.astimezone(ZONA)
            except ValueError:
                continue
            if not hoy <= instante.date() <= hoy + timedelta(days=30):
                continue
            if any(x in str(ficha.get('eventStatus', '')) for x in ('Cancelled', 'Postponed', 'Rescheduled')):
                continue
            loc = ficha.get('location') or {}
            if not isinstance(loc, dict):
                continue
            lugar = loc.get('name') or ''
            domicilio = loc.get('address') or direccion
            if isinstance(domicilio, dict):
                localidad = domicilio.get('addressLocality') or ''
                if localidad and 'rosario' not in normalizar(localidad):
                    continue
                domicilio = domicilio.get('streetAddress') or direccion
            if not isinstance(lugar, str) or not isinstance(domicilio, str) or not domicilio:
                continue
            if fuente == 'ECU Espacio Cultural Universitario' and not re.search(r'\becu\b|espacio cultural universitario', normalizar(lugar)):
                continue
            if fuente != 'ECU Espacio Cultural Universitario' and not (normalizar(fuente) in normalizar(lugar) or 'rosario' in normalizar(lugar + ' ' + domicilio)):
                continue
            titulo = ficha.get('name')
            if not isinstance(titulo, str) or not titulo:
                continue
            enlace = ficha.get('url')
            if not isinstance(enlace, str) or not mismo_dominio(enlace, url):
                enlace = url
            descripcion = texto(BeautifulSoup(str(ficha.get('description') or ''), 'html.parser'))
            if ficha.get('isAccessibleForFree') is True:
                descripcion_precio = descripcion + ' Entrada gratuita'
            else:
                descripcion_precio = descripcion
            evento = actividad_ampliada(instante.date().isoformat(), instante.strftime('%H:%M'), titulo,
                enlace, fuente, domicilio, descripcion_precio, lugar or fuente)
            categorias = categorias_espacio(titulo, descripcion)
            if categorias:
                evento['categorias'] = categorias
            eventos.append(evento)
    return eventos


def leer_agenda_csv(fuente, indice, segunda, direccion, hoy):
    eventos, errores, visitadas, cache = [], 0, set(), {}
    for portada in [u for u in (indice, segunda) if u]:
        try:
            html = descargar(portada)
            cache[portada] = html
            eventos.extend(schema_csv(html, fuente, portada, direccion, hoy))
            links = []
            for a in html.select('a[href]'):
                link = urljoin(portada, a['href']).split('#', 1)[0]
                if mismo_dominio(link, indice) and link not in links and re.search(
                    r'agenda|evento|actividad|programacion|cartelera|concierto', normalizar(texto(a) + ' ' + urlsplit(link).path)):
                    links.append(link)
            for link in links[:8]:
                if link in visitadas:
                    continue
                visitadas.add(link)
                try:
                    if link not in cache:
                        cache[link] = descargar(link)
                    eventos.extend(schema_csv(cache[link], fuente, link, direccion, hoy))
                    if fuente == 'ECU Espacio Cultural Universitario':
                        detalle = cache[link]
                        titulo = texto(detalle.select_one('h1'))
                        cuerpo = detalle.select_one('.mec-single-event-description')
                        descripcion = texto(cuerpo)
                        confirmado = bool(re.search(rf'(?:datePublished|dateModified|startDate)[^\n]{{0,60}}{hoy.year}-', str(detalle)))
                        if titulo and cuerpo and confirmado and re.search(r'\becu\b|espacio cultural universitario', normalizar(descripcion)):
                            for fecha, hora in fechas_publicadas(descripcion, hoy):
                                evento = actividad_ampliada(fecha, hora, titulo, link, fuente, direccion, descripcion, fuente)
                                categorias = categorias_espacio(titulo, descripcion)
                                if categorias:
                                    evento['categorias'] = categorias
                                eventos.append(evento)
                except (requests.RequestException, ValueError):
                    errores += 1
        except (requests.RequestException, ValueError):
            errores += 1
    return list({clave(e): e for e in eventos}.values()), errores


def leer_fuentes_del_csv(hoy, estado):
    nuevos = []
    for fuente, indice, segunda, direccion in CSV_AGENDAS:
        funciones, pendientes = leer_agenda_csv(fuente, indice, segunda, direccion, hoy)
        nuevos.extend(funciones)
        estado[fuente + ' — CSV'] = f'revisada: {len(funciones)} funciones; {pendientes} consultas pendientes'
    funciones, pendientes = leer_cairo(hoy)
    nuevos.extend(funciones)
    estado['El Cairo — CSV'] = f'revisada: {len(funciones)} funciones; {pendientes} consultas pendientes'
    return nuevos


def revision_fuentes_csv(eventos, estado):
    revision = []
    for nombre, tipo, url, prioridad in FUENTES_CSV:
        social = urlsplit(url).hostname in ('www.instagram.com', 'instagram.com', 'www.facebook.com', 'facebook.com')
        estado_fuente = estado.get(nombre + ' — CSV', '')
        if nombre == 'El Cairo Cine Publico':
            estado_fuente = estado.get('El Cairo — CSV', '')
        if not estado_fuente:
            if tipo == 'variable':
                estado_fuente = 'requiere identificar el organizador de cada evento'
            elif social:
                estado_fuente = 'referencia social; se usan ATIR, ticketeras o agendas públicas cuando están disponibles'
            elif 'museo' in tipo:
                estado_fuente = 'revisión del directorio y de las webs de museos'
            else:
                estado_fuente = 'revisión mediante recolectores existentes y agenda municipal; no garantiza cartelera completa'
        patron = normalizar(nombre).replace('teatro la morada', 'la morada')
        cantidad = sum(1 for e in eventos if patron in normalizar(e.get('lugar', '') + ' ' + e.get('origen', '')))
        revision.append({'nombre': nombre, 'url_aportada': url, 'tipo': tipo,
            'prioridad': prioridad, 'estado': estado_fuente, 'actividades': cantidad})
    return revision

def actualizar_fuentes():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    estado = {}
    # Los eventos previos permanecen en eventos.json si una fuente no responde.
    # No se requiere ningún archivo de respaldo mensual.
    nuevos = []
    nuevos.extend(leer_feria_libro(hoy, estado))
    nuevos.extend(leer_microteatro(hoy, estado))
    nuevos.extend(leer_atir(hoy, estado))
    nuevos.extend(leer_fuentes_del_csv(hoy, estado))
    espacios_nuevos = leer_espacios_extra(hoy, estado)
    nuevos.extend(espacios_nuevos)
    nuevos.extend(leer_municipal_espacios(hoy, estado))
    actividades_museos, revision_museos = leer_museos(hoy, estado)
    nuevos.extend(actividades_museos)
    for fuente, url, direccion, parser in (
        ("La Orilla Infinita", "https://laorillainfinita.com.ar/", "Colón 2148", calendario_orilla),
        ("Teatro del Rayo", "https://elrayomisterioso.org.ar/index.php/es/component/sppagebuilder/?view=page&id=219", "Salta 2991", calendario_rayo),
    ):
        try:
            funciones, fallos = parser(descargar(url), fuente, url, direccion, hoy)
            nuevos.extend(funciones)
            estado[fuente] = f"revisada: {len(funciones)} funciones; {len(fallos)} pendientes"
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[fuente] = f"no accesible: {type(error).__name__}"
    for fuente, indice, ruta in PRENSA:
        try:
            encontrados, leidas, fallidas = leer_prensa(fuente, indice, ruta, hoy)
            nuevos.extend(encontrados)
            estado[fuente] = f"revisada: {leidas} notas, {len(encontrados)} funciones, {fallidas} errores"
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[fuente] = f"no accesible: {type(error).__name__}"
    nombre, url = CARTELERA
    try:
        url = "https://www.rosarioencartel.com.ar/"
        nuevos_cartel, fallos = calendario_encartel(descargar(url), nombre, url, "", hoy)
        nuevos.extend(nuevos_cartel)
        estado[nombre] = f"revisada: {len(nuevos_cartel)} funciones verificadas; {len(fallos)} fichas pendientes"
    except (requests.RequestException, ValueError, TypeError) as error:
        estado[nombre] = f"no accesible: {type(error).__name__}"
    anteriores = preferir_venta_oficial(datos.get("eventos", []), espacios_nuevos)
    nuevos = preferir_venta_oficial(nuevos, espacios_nuevos)
    vistos = {clave(e): e for e in anteriores if e["fecha"] >= hoy.isoformat()}
    agregados = 0
    for e in nuevos:
        key = clave(e)
        if key not in vistos:
            vistos[key] = e
            agregados += 1
        elif e.get("funcion_unica_verificada") or e.get("origen") == "Circo Rodas — Linke-arte":
            vistos[key] = e
    for evento in vistos.values():
        if evento.get("origen") == "Teatro Astengo" and not re.search(r"\d", evento.get("direccion", "")):
            evento["direccion"] = "Mitre 754, Rosario, Santa Fe"
        if not evento.get("origen"):
            evento["origen"] = "Manual"
        if not evento.get("evento_url"):
            evento["fuente_pendiente"] = True
    ordenados = sorted(vistos.values(), key=lambda e: not e.get("funcion_unica_verificada", False))
    datos["eventos"] = sorted(sin_repetidos(ordenados), key=lambda e: (e["fecha"], e["hora"], e["nombre"]))
    if any("pendiente de consulta" in status or "revisión parcial" in status or "no accesible" in status or re.search(r"[1-9]\d* (?:errores|pendientes|fichas pendientes|consultas pendientes|páginas pendientes)", status) for status in estado.values()):
        datos["estado"] = "parcial"
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ARCHIVO)
    REGISTRO.write_text(json.dumps({
        "fecha_revision": ahora.strftime("%Y-%m-%d %H:%M"),
        "salas_independientes": len(SALAS), "medios": len(PRENSA),
        "funciones_agregadas": agregados, "fuentes": estado,
        "museos": revision_museos,
        "fuentes_csv": revision_fuentes_csv(datos["eventos"], estado),
        "espacios_seguidos": [{"nombre": e[0], "fuentes": e[2],
            "actividades": sum(1 for a in datos["eventos"] if (espacio_seguido(a.get("lugar", "")) or (None,))[0] == e[0])}
            for e in ESPACIOS_SEGUIDOS],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fuentes complementarias: {len(estado)} revisadas, {agregados} funciones agregadas")
    for fuente, resultado in estado.items():
        print(f"  {fuente}: {resultado}")


if __name__ == "__main__":
    actualizar_fuentes()


