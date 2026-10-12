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
    eventos_schema, calendario_mec,
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
ARTICULO_COMPROBADO = (
    "https://www.rosario3.com/ocio/funciones-de-las-obras-el-viaje-del-tambor-"
    "para-anormales-hervidero-caballito-de-batalla-ito-teatro-para-bebes-"
    "y-quemarlo-todo-20261002-0028.html"
)
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
RESPALDO = Path(__file__).with_name("eventos_verificados_octubre_2026.json")


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


def leer_prensa(fuente, indice, ruta, hoy):
    portada = descargar(indice)
    enlaces = []
    for a in portada.select("a[href]"):
        titular = texto(a)
        link = urljoin(indice, a["href"]).split("#", 1)[0]
        if not mismo_dominio(link, indice) or ruta not in urlsplit(link).path:
            continue
        if not INTERES.search(titular) or "/seccion/" in link or "/tag/" in link:
            continue
        if link not in enlaces:
            enlaces.append(link)
    # Esta nota contiene cuatro series de funciones futuras verificables.
    if fuente == "Rosario3" and ARTICULO_COMPROBADO not in enlaces:
        enlaces.insert(0, ARTICULO_COMPROBADO)
    eventos, consultadas, fallidas = [], 0, 0
    for link in enlaces[:14]:
        try:
            articulo = descargar(link)
            eventos.extend(schema_local(articulo, fuente, link, hoy))
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
                nuevos.extend(eventos)
                estado[nombre] = f"revisada: {len(eventos)} funciones, {len(fallidos)} errores"
            elif "no events" in normalizar(texto(html)) or html.select(".mec-calendar"):
                estado[nombre] = "revisada: sin funciones estructuradas"
            else:
                estado[nombre] = "revisada: sin cartelera interpretable"
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[nombre] = f"no accesible: {type(error).__name__}"
    return nuevos


def actualizar_fuentes():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    estado = {}
    # Respaldo de 10 fechas comprobadas, útil si el diario bloquea robots.
    respaldo = json.loads(RESPALDO.read_text(encoding="utf-8"))
    nuevos = [e for e in respaldo["eventos"] if e["fecha"] >= hoy.isoformat()]
    nuevos.extend(leer_atir(hoy, estado))
    for fuente, indice, ruta in PRENSA:
        try:
            encontrados, leidas, fallidas = leer_prensa(fuente, indice, ruta, hoy)
            nuevos.extend(encontrados)
            estado[fuente] = f"revisada: {leidas} notas, {len(encontrados)} funciones, {fallidas} errores"
        except (requests.RequestException, ValueError, TypeError) as error:
            estado[fuente] = f"no accesible: {type(error).__name__}"
    nombre, url = CARTELERA
    try:
        nuevos_cartel = schema_local(descargar(url), nombre, url, hoy)
        nuevos.extend(nuevos_cartel)
        estado[nombre] = f"revisada: {len(nuevos_cartel)} funciones estructuradas"
    except (requests.RequestException, ValueError, TypeError) as error:
        estado[nombre] = f"no accesible: {type(error).__name__}"
    vistos = {clave(e): e for e in datos.get("eventos", []) if e["fecha"] >= hoy.isoformat()}
    agregados = 0
    for e in nuevos:
        key = clave(e)
        if key not in vistos:
            vistos[key] = e
            agregados += 1
    datos["eventos"] = sorted(vistos.values(), key=lambda e: (e["fecha"], e["hora"], e["nombre"]))
    if any("no accesible" in status for status in estado.values()):
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
