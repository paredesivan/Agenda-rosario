"""Agenda Rosario: control adicional de salas ATIR, prensa y Rosario en Cartel.

Sólo agrega actividades con fecha, hora y sede verificables. Ante fallas no
elimina actividades previamente publicadas ni bloquea el actualizador principal.
"""
import calendar
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

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

def actualizar_fuentes():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    estado = {}
    # Los eventos previos permanecen en eventos.json si una fuente no responde.
    # No se requiere ningún archivo de respaldo mensual.
    nuevos = []
    nuevos.extend(leer_atir(hoy, estado))
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
    vistos = {clave(e): e for e in datos.get("eventos", []) if e["fecha"] >= hoy.isoformat()}
    agregados = 0
    for e in nuevos:
        key = clave(e)
        if key not in vistos:
            vistos[key] = e
            agregados += 1
    for evento in vistos.values():
        if evento.get("origen") == "Teatro Astengo" and not re.search(r"\d", evento.get("direccion", "")):
            evento["direccion"] = "Mitre 754, Rosario, Santa Fe"
        if not evento.get("origen"):
            evento["origen"] = "Manual"
        if not evento.get("evento_url"):
            evento["fuente_pendiente"] = True
    datos["eventos"] = sorted(sin_repetidos(vistos.values()), key=lambda e: (e["fecha"], e["hora"], e["nombre"]))
    if any("no accesible" in status or re.search(r"[1-9]\d* (?:errores|pendientes|fichas pendientes)", status) for status in estado.values()):
        datos["estado"] = "parcial"
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ARCHIVO)
    REGISTRO.write_text(json.dumps({
        "fecha_revision": ahora.strftime("%Y-%m-%d %H:%M"),
        "salas_independientes": len(SALAS), "medios": len(PRENSA),
        "funciones_agregadas": agregados, "fuentes": estado,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fuentes complementarias: {len(estado)} revisadas, {agregados} funciones agregadas")
    for fuente, resultado in estado.items():
        print(f"  {fuente}: {resultado}")


if __name__ == "__main__":
    actualizar_fuentes()

