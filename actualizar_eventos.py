"""Actualiza actividades culturales con fecha, hora y acceso verificados."""

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ARCHIVO = Path(__file__).with_name("eventos.json")
BASE = "https://www.rosario.gob.ar"
FUENTES = (f"{BASE}/inicio/cultura-y-educacion", f"{BASE}/inicio/agenda")
ORIGEN = "Municipalidad de Rosario"
ZONA = ZoneInfo("America/Argentina/Cordoba")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")
CATEGORIAS = ("cine", "teatro", "musica", "concierto", "feria", "muestra",
              "exposicion", "festival", "danza", "planetario", "arte",
              "visita guiada", "visitas guiadas", "literatura", "libro")


def texto(elemento):
    return " ".join(elemento.get_text(" ", strip=True).split()) if elemento else ""


def normalizar(valor):
    return "".join(c for c in unicodedata.normalize("NFD", valor.lower())
                   if unicodedata.category(c) != "Mn")


def url_oficial(valor):
    partes = urlsplit(urljoin(BASE, valor))
    if partes.hostname not in ("www.rosario.gob.ar", "rosario.gob.ar"):
        return ""
    ruta = partes.path.replace("/inicio/index.php/", "/inicio/").rstrip("/")
    if not ruta.startswith("/inicio/"):
        return ""
    return urlunsplit(("https", "www.rosario.gob.ar", ruta, "", ""))


def descargar(url):
    with requests.Session() as sesion:
        reintentos = Retry(total=2, backoff_factor=0.5,
                           status_forcelist=(429, 500, 502, 503, 504))
        sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
        respuesta = sesion.get(url, timeout=(10, 25),
                               headers={"User-Agent": "AgendaRosario/2.0"})
        respuesta.raise_for_status()
        respuesta.encoding = "utf-8"
        return BeautifulSoup(respuesta.text, "html.parser")


def obtener_enlaces():
    enlaces, errores = set(), []
    for fuente in FUENTES:
        try:
            html = descargar(fuente)
            tarjetas = html.select("actividad a[href]")
            if not tarjetas:
                raise ValueError("La fuente no contiene tarjetas de actividades")
            enlaces.update(url for a in tarjetas if (url := url_oficial(a["href"])))
        except (requests.RequestException, ValueError) as error:
            errores.append(f"{fuente}: {error}")
    if not enlaces:
        raise RuntimeError("No se pudo consultar la agenda oficial; se conservan los datos")
    return enlaces, errores


def es_cultural(contenido):
    etiquetas = " ".join(texto(e) for e in contenido.select(
        ".etiqueta-actividad, .etiquetas-secundarias-container"))
    descripcion = texto(contenido.select_one(".descripcion"))
    valor = normalizar(etiquetas + " " + texto(contenido.select_one("h1")) + " " + descripcion)
    return any(re.search(r"\b" + re.escape(c) + r"s?\b", valor) for c in CATEGORIAS)


def es_gratuito(bloque, contenido):
    entrada = bloque.select_one(".entrada-actividad")
    if entrada:
        return bool(re.fullmatch(
            r"gratis|gratuit[ao]s?|entrada (?:libre(?: y gratuita)?|gratuita)|sin (?:costo|cargo)",
            normalizar(texto(entrada))))
    # Una mención general no reemplaza el precio de otra función del mismo evento.
    if contenido.select_one(".entrada-actividad"):
        return False
    descripcion = normalizar(texto(contenido.select_one(".descripcion")))
    return any(frase in descripcion for frase in (
        "entrada libre y gratuita", "entrada gratuita", "actividad gratuita", "acceso gratuito"))


def hora_regla(valor):
    encontrado = re.match(r"(?:de\s+|a las\s+)?(\d{1,2})(?:[:.](\d{2}))?\b",
                          normalizar(valor))
    if not encontrado:
        return None
    hora, minuto = int(encontrado[1]), int(encontrado[2] or 0)
    return f"{hora:02d}:{minuto:02d}" if hora < 24 and minuto < 60 else None


def fechas_regla(regla, hoy):
    valor = normalizar(texto(regla.select_one(".rule-fechas")))
    patron = r"del?\s+(\d{1,2})\s+de\s+(\w+)(?:\s+(\d{4}))?\s+al\s+(\d{1,2})\s+de\s+(\w+)(?:\s+(\d{4}))?"
    partes = re.fullmatch(patron, valor)
    hora = hora_regla(texto(regla.select_one(".rule-hora")))
    if not partes or not hora:
        return []
    dia1, mes1, anio1, dia2, mes2, anio2 = partes.groups()
    if mes1 not in MESES or mes2 not in MESES:
        return []
    m1, m2 = MESES.index(mes1) + 1, MESES.index(mes2) + 1
    anio = int(anio1) if anio1 else hoy.year
    if not anio1 and m2 < m1 and hoy.month <= m2:
        anio -= 1
    inicio = date(anio, m1, int(dia1))
    fin = date(int(anio2) if anio2 else anio + (m2 < m1), m2, int(dia2))
    dias = normalizar(texto(regla.select_one(".rule-dias")))
    if dias == "todos los dias":
        elegidos = set(range(7))
    else:
        elegidos = {i for i, d in enumerate(DIAS) if re.search(r"\b" + d + r"\b", dias)}
        intervalo = re.fullmatch(r"(?:de\s+)?(" + "|".join(DIAS) + r")\s+a\s+(" + "|".join(DIAS) + r")", dias)
        if intervalo:
            primero, ultimo = DIAS.index(intervalo[1]), DIAS.index(intervalo[2])
            elegidos = {(primero + i) % 7 for i in range((ultimo - primero) % 7 + 1)}
        elif re.search(r"excepto|cada|alternad", dias):
            return []
    resultados = []
    actual, limite = max(inicio, hoy), min(fin, hoy + timedelta(days=30))
    while actual <= limite:
        if actual.weekday() in elegidos:
            resultados.append((actual.isoformat(), hora))
        actual += timedelta(days=1)
    return resultados


def ubicacion(bloque):
    titulo = bloque.select_one(".title-lugar")
    nombre = " ".join(titulo.find_all(string=True, recursive=False)).strip() if titulo else ""
    direccion = texto(bloque.select_one(".direccion-lugar"))
    if not nombre:
        nombre = texto(bloque.select_one(".lugar-contenedor"))
    return nombre, (direccion or nombre) + ", Rosario, Santa Fe" if nombre else ""


def clave(evento):
    return (evento["fecha"], evento["hora"], evento.get("evento_url") or normalizar(evento["nombre"]),
            normalizar(evento.get("lugar", "")))


def extraer_eventos(html, url, hoy):
    contenido = html.select_one("main") or html
    titulo = texto(contenido.select_one("h1"))
    if not titulo or not es_cultural(contenido):
        return []
    parrafo = contenido.select_one(".descripcion p")
    resumen = " ".join(texto(parrafo).split()[:22])
    if len(texto(parrafo).split()) > 22:
        resumen = resumen.rstrip(".,:;") + "…"
    resultados = {}
    for bloque in contenido.select(".cuando-fechas"):
        if not es_gratuito(bloque, contenido):
            continue
        lugar, direccion = ubicacion(bloque)
        if not lugar:
            continue
        fechas = []
        for regla in bloque.select(".rule"):
            fechas.extend(fechas_regla(regla, hoy))
        for instante in bloque.select("time[datetime]"):
            if not instante.select_one(".hora-desde"):
                continue  # La hora de cierre no es una segunda función.
            cuando = datetime.fromisoformat(instante["datetime"])
            if cuando.tzinfo:
                cuando = cuando.astimezone(ZONA)
            if hoy <= cuando.date() <= hoy + timedelta(days=30):
                fechas.append((cuando.date().isoformat(), cuando.strftime("%H:%M")))
        for fecha, hora in fechas:
            evento = {"fecha": fecha, "hora": hora, "nombre": titulo,
                      "lugar": lugar, "direccion": direccion,
                      "descripcion": resumen or "Actividad de la agenda cultural municipal.",
                      "evento_url": url, "precio": 0, "origen": ORIGEN}
            resultados[clave(evento)] = evento
    return list(resultados.values())


def consultar_evento(url, hoy):
    try:
        return url, extraer_eventos(descargar(url), url, hoy), None, False
    except requests.HTTPError as error:
        eliminado = error.response is not None and error.response.status_code in (404, 410)
        return url, [], str(error), eliminado
    except (requests.RequestException, ValueError) as error:
        return url, [], str(error), False


def combinar_eventos(nuevos, anteriores, fallidos, hoy):
    resultados = {clave(e): e for e in nuevos}
    for evento in anteriores:
        if evento["fecha"] < hoy.isoformat():
            continue
        if evento.get("origen") != ORIGEN or url_oficial(evento.get("evento_url", "")) in fallidos:
            resultados.setdefault(clave(evento), evento)
    return sorted(resultados.values(), key=lambda e: (e["fecha"], e["hora"], e["nombre"]))


def actualizar():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    anteriores = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {"eventos": []}
    conocidos = anteriores.get("eventos", [])
    enlaces, errores = obtener_enlaces()
    enlaces.update(url for e in conocidos if e.get("origen") == ORIGEN
                   and e["fecha"] >= hoy.isoformat() and (url := url_oficial(e.get("evento_url", ""))))
    eventos, fallidos = [], set()
    print(f"Consultando {len(enlaces)} fichas oficiales", flush=True)
    with ThreadPoolExecutor(max_workers=4) as grupo:
        for indice, (url, nuevos, error, eliminado) in enumerate(
                grupo.map(lambda u: consultar_evento(u, hoy), sorted(enlaces)), 1):
            eventos.extend(nuevos)
            if error and not eliminado:
                errores.append(f"{url}: {error}")
                fallidos.add(url)
            if indice % 20 == 0:
                print(f"Revisadas {indice}/{len(enlaces)} fichas", flush=True)
    if not eventos:
        raise RuntimeError("No se extrajeron actividades verificables; no se reemplaza la agenda")
    datos = {"actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
             "estado": "parcial" if errores else "completo",
             "eventos": combinar_eventos(eventos, conocidos, fallidos, hoy)}
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ARCHIVO)
    print(f"Agenda actualizada: {len(datos['eventos'])} actividades, {len(errores)} consultas fallidas")
    for error in errores:
        print(f"Aviso: {error}")

# Fuentes adicionales y consultas moderadas.
from html import unescape
from time import monotonic, sleep

EXTRAS = (
    (
        "Plataforma Lavardén",
        "https://plataformalavarden.gob.ar/agenda/",
        "Mendoza 1085",
    ),
    (
        "Centro Cultural Parque de España",
        "https://ccpe.org.ar/web/agenda/",
        "Sarmiento y el río",
    ),
    (
        "Teatro Municipal La Comedia",
        "https://teatrolacomedia.gob.ar/espectaculos/programacion/",
        "Mitre 958",
    ),
)

SESION = requests.Session()
SESION.headers.update({
    "User-Agent": "AgendaRosario/3.0 (+https://paredesivan.github.io/Agenda-rosario/)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-AR,es;q=0.9",
})
SESION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=1,
    backoff_factor=1,
    status_forcelist=(500, 502, 503, 504),
    respect_retry_after_header=False,
)))

ULTIMA, BLOQUEADOS, FALLAS = {}, set(), {}


def descargar(url):
    host = urlsplit(url).hostname
    if host in BLOQUEADOS:
        raise requests.RequestException(
            f"Fuente pausada: {host}; se conservan sus datos"
        )

    espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))
    if espera > 0:
        sleep(espera)

    try:
        respuesta = SESION.get(url, timeout=(10, 25))
        if respuesta.status_code in (403, 429):
            BLOQUEADOS.add(host)
            raise requests.HTTPError(
                f"HTTP {respuesta.status_code}: fuente pausada hasta la próxima revisión",
                response=respuesta,
            )
        respuesta.raise_for_status()
        FALLAS[host] = 0
        respuesta.encoding = "utf-8"
        return BeautifulSoup(respuesta.text, "html.parser")
    except (requests.ConnectionError, requests.Timeout):
        FALLAS[host] = FALLAS.get(host, 0) + 1
        if FALLAS[host] >= 3:
            BLOQUEADOS.add(host)
        raise
    finally:
        ULTIMA[host] = monotonic()


def acceso(valor, venta=False):
    valor = normalizar(valor)
    patron = r"\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    importes = [
        float(n.replace(".", "").replace(",", "."))
        for n in re.findall(patron, valor)
    ]
    importes = sorted(set(n for n in importes if n > 0))

    if len(importes) == 1:
        return importes[0], ""
    if importes:
        nota = (
            f"Entradas entre ${importes[0]:,.0f} "
            f"y ${importes[-1]:,.0f}. "
        ).replace(",", ".")
        return None, nota

    if re.search(
        r"\bgratis\b|\bgratuit[ao]s?\b|entrada libre|sin (?:costo|cargo)",
        valor,
    ):
        return 0, ""

    if venta or re.search(
        r"entradas? (?:a la venta|anticipadas|en venta)|arancelad|boleteria|tickets",
        valor,
    ):
        return None, ""

    return None, None


def resumen(valor):
    palabras = valor.split()
    return " ".join(palabras[:22]) + ("…" if len(palabras) > 22 else "")


def evento_extra(fecha, hora, nombre, url, fuente, direccion,
                 descripcion, precio, nota):
    return {
        "fecha": fecha,
        "hora": hora,
        "nombre": unescape(nombre),
        "lugar": fuente,
        "direccion": (direccion if "rosario" in normalizar(direccion) else direccion + ", Rosario, Santa Fe"),
        "descripcion": nota + resumen(descripcion),
        "evento_url": url,
        "precio": precio,
        "origen": fuente,
    }


def sin_repetidos(eventos):
    resultado = []
    sedes = ("lavarden", "parque de espana", "comedia")
    for evento in eventos:
        nombre = normalizar(evento["nombre"])
        lugar = normalizar(evento["lugar"])
        sede = next((v for v in sedes if v in lugar), lugar)
        repetido = False

        for anterior in resultado:
            otro = normalizar(anterior["nombre"])
            otro_lugar = normalizar(anterior["lugar"])
            otra_sede = next(
                (v for v in sedes if v in otro_lugar), otro_lugar
            )
            mismo_turno = (
                evento["fecha"], evento["hora"], sede
            ) == (
                anterior["fecha"], anterior["hora"], otra_sede
            )
            mismo_nombre = (
                nombre == otro
                or len(nombre) >= 8 and nombre in otro
                or len(otro) >= 8 and otro in nombre
            )
            if mismo_turno and mismo_nombre:
                repetido = True
                break

        if not repetido:
            resultado.append(evento)
    return resultado


def lavarden(html, fuente, url, direccion, hoy):
    tarjetas = html.select(".jet-listing-grid__item")
    if not tarjetas:
        raise ValueError("Cambió el formato de la agenda Lavardén")

    eventos = []
    for tarjeta in tarjetas:
        enlace = tarjeta.select_one("h2 a[href]")
        valores = [
            texto(v)
            for v in tarjeta.select(".jet-listing-dynamic-field__content")
        ]
        fecha = next(
            (v for v in valores if re.search(r"\d{1,2}:\d{2}\s*hs", v)),
            "",
        )
        partes = re.search(
            r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?,\s*(\d{1,2}):(\d{2})",
            normalizar(fecha),
        )
        if not enlace or not partes or partes[2] not in MESES:
            continue

        mes = MESES.index(partes[2]) + 1
        anio = (
            int(partes[3]) if partes[3]
            else hoy.year + (hoy.month == 12 and mes == 1)
        )
        dia = date(anio, mes, int(partes[1]))
        if not hoy <= dia <= hoy + timedelta(days=30):
            continue

        venta = any(
            "entradaslavarden.com" in a["href"]
            for a in tarjeta.select("a[href]")
        )
        precio, nota = acceso(texto(tarjeta), venta)
        if nota is None:
            continue

        descripcion = texto(
            tarjeta.select_one(".elementor-widget-text-editor")
        )
        eventos.append(evento_extra(
            dia.isoformat(),
            f"{int(partes[4]):02d}:{partes[5]}",
            texto(enlace),
            enlace["href"],
            fuente,
            direccion,
            descripcion,
            precio,
            nota,
        ))
    return eventos, set()


def eventos_schema(valor):
    if isinstance(valor, list):
        for v in valor:
            yield from eventos_schema(v)
    elif isinstance(valor, dict):
        tipos = valor.get("@type", [])
        if tipos == "Event" or isinstance(tipos, list) and "Event" in tipos:
            yield valor
        for v in valor.values():
            if isinstance(v, (list, dict)):
                yield from eventos_schema(v)


def calendario(html, fuente, url, direccion, hoy):
    fichas = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas.extend(eventos_schema(json.loads(tag.get_text())))
        except ValueError:
            continue
    if not fichas:
        raise ValueError("Cambió el formato del calendario")

    eventos, fallidos, vistos = [], set(), set()
    for ficha in fichas:
        fecha = ficha.get("startDate", "")[:10]
        enlace = (
            ficha.get("url")
            or ficha.get("offers", {}).get("url", "")
        )
        if not enlace or enlace in vistos:
            continue
        if urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            continue
        if not hoy <= date.fromisoformat(fecha) <= hoy + timedelta(days=30):
            continue

        vistos.add(enlace)
        try:
            detalle = descargar(enlace)
            cuerpo = detalle.select_one(".mec-single-event-description")
            if not cuerpo:
                raise ValueError("La ficha no tiene descripción verificable")
            descripcion = texto(cuerpo)

            if re.search(
                r"\bsuspendid[ao]\b|\bcancelad[ao]\b|\breprogramad[ao]\b",
                normalizar(descripcion),
            ):
                continue

            hora = texto(detalle.select_one(
                ".mec-single-event-time .mec-events-abbr"
            ))
            coincidencia = re.match(r"(\d{1,2}):(\d{2})", hora)
            if not coincidencia:
                continue
            hora = f"{int(coincidencia[1]):02d}:{coincidencia[2]}"

            precio, nota = acceso(descripcion)
            if nota is None:
                continue

            eventos.append(evento_extra(
                fecha, hora, ficha.get("name", ""), enlace,
                fuente, direccion, descripcion, precio, nota,
            ))
        except (requests.RequestException, ValueError) as error:
            fallidos.add(enlace)
            print(
                f"Aviso: {fuente}: {type(error).__name__}; "
                "se conserva la ficha anterior",
                flush=True,
            )
    return eventos, fallidos


def actualizar():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    anteriores = (
        json.loads(ARCHIVO.read_text(encoding="utf-8"))
        if ARCHIVO.exists() else {"eventos": []}
    )
    conocidos = anteriores.get("eventos", [])
    eventos, fallidos, errores, correctas = [], set(), [], set()
    BLOQUEADOS.clear()
    FALLAS.clear()

    for fuente, url, direccion in EXTRAS:
        try:
            html = descargar(url)
            parser = lavarden if fuente == "Plataforma Lavardén" else calendario
            nuevos, fallas = parser(html, fuente, url, direccion, hoy)
            eventos.extend(nuevos)
            fallidos.update(fallas)
            correctas.add(fuente)
            if fallas:
                errores.append(f"{fuente}: {len(fallas)} fichas pendientes")
            print(f"{fuente}: {len(nuevos)} actividades", flush=True)
        except (requests.RequestException, ValueError) as error:
            errores.append(
                f"{fuente}: {type(error).__name__}; "
                "se conservan datos anteriores"
            )

    try:
        enlaces, avisos = obtener_enlaces()
        errores.extend(avisos)
        enlaces.update(
            e["evento_url"] for e in conocidos
            if e.get("origen") == ORIGEN
            and e["fecha"] >= hoy.isoformat()
            and e.get("evento_url")
        )
        for indice, url in enumerate(sorted(enlaces), 1):
            _, nuevos, error, eliminado = consultar_evento(url, hoy)
            eventos.extend(nuevos)
            if error and not eliminado:
                fallidos.add(url)
            if indice % 20 == 0:
                print(
                    f"Municipalidad: {indice}/{len(enlaces)} fichas",
                    flush=True,
                )
        correctas.add(ORIGEN)
    except (requests.RequestException, ValueError, RuntimeError) as error:
        errores.append(
            f"Municipalidad: {type(error).__name__}; "
            "se conservan datos anteriores"
        )

    if fallidos:
        errores.append(f"{len(fallidos)} fichas pendientes de consulta")
    if not eventos:
        raise RuntimeError(
            "No se obtuvieron actividades; se conserva la agenda anterior"
        )

    resultados = {clave(e): e for e in eventos}
    for e in conocidos:
        conservar = (
            e.get("origen") not in correctas
            or e.get("evento_url") in fallidos
        )
        if e["fecha"] >= hoy.isoformat() and conservar:
            resultados.setdefault(clave(e), e)

    datos = {
        "actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
        "estado": "parcial" if errores else "completo",
        "eventos": sorted(
            sin_repetidos(resultados.values()),
            key=lambda e: (e["fecha"], e["hora"], e["nombre"]),
        ),
    }
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporal.replace(ARCHIVO)
    print(
        f"Agenda actualizada: {len(datos['eventos'])} actividades",
        flush=True,
    )
    for error in errores:
        print(f"Aviso: {error}", flush=True)


# Ampliación: teatros, música y bibliotecas.
EXTRAS += (
    ("Teatro Astengo", "https://teatroastengo.ar/events/", "Mitre 754"),
    ("ATIR", "https://www.teatrosatir.ar/cartelera/", ""),
    ("Teatro Broadway", "https://teatrobroadwayrosario.com/", "San Lorenzo 1223"),
    ("Distrito Siete", "https://www.d7entradas.com.ar/", "Ovidio Lagos 790"),
    ("Metropolitano", "https://www.metropolitano.ar/espectaculos/", "Junín 501"),
    ("Biblioteca Argentina Dr. Juan Álvarez", "https://biblioargentina.gob.ar/web/agenda/", "Presidente Roca 731"),
    ("Biblioteca Vigil", "https://bibliotecavigil.org.ar/inicio/eventos/", "Biblioteca Vigil"),
)
FUENTES += (f"{BASE}/inicio/agenda/buscar",)
CATEGORIAS += ("biblioteca", "lectura", "poesia", "narracion", "charla", "boxeo")
_calendario_anterior = calendario


def hora_visible(valor):
    m = re.match(r"\s*(\d{1,2})(?::|\.)(\d{2})(?:\s*([ap])\.?m\.?)?", normalizar(valor))
    if not m:
        return None
    h = int(m[1])
    if m[3]:
        h = h % 12 + (12 if m[3] == "p" else 0)
    return f"{h:02d}:{m[2]}" if h < 24 and int(m[2]) < 60 else None


def fechas_publicadas(valor, hoy, anio_confirmado=False):
    valor = normalizar(valor)
    patron = (r"(?:(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+)?"
              r"(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")"
              r"(?:\s+(?:de\s+)?(20\d{2}))?\s*(?:,\s*)?"
              r"(?:a las?\s+|de\s+)?(\d{1,2})(?::|\.)?(\d{2})?"
              r"(?:\s+a\s+\d{1,2}(?::\d{2})?)?\s*(?:hs?\.?|horas)\b")
    resultado = []
    for m in re.finditer(patron, valor):
        if not m[1] and not m[4] and not anio_confirmado:
            continue
        mes = MESES.index(m[3]) + 1
        anio = int(m[4]) if m[4] else hoy.year + (hoy.month == 12 and mes == 1)
        try:
            dia = date(anio, mes, int(m[2]))
        except ValueError:
            continue
        if m[1] and DIAS[dia.weekday()] != m[1]:
            continue
        hora = hora_visible(f"{m[5]}:{m[6] or '00'}")
        if hora and hoy <= dia <= hoy + timedelta(days=30):
            resultado.append((dia.isoformat(), hora))
    return list(dict.fromkeys(resultado))


def actividad_ampliada(fecha, hora, titulo, enlace, fuente, direccion,
                       descripcion, lugar=None, desde=False):
    venta = fuente in ("Teatro Broadway", "Distrito Siete", "Metropolitano")
    precio, nota = acceso(descripcion, venta)
    e = evento_extra(fecha, hora, titulo, enlace, fuente, direccion,
                     descripcion, precio, nota or "")
    e["lugar"] = lugar or fuente
    if nota is None:
        e["precio_etiqueta"] = "Precio a confirmar"
    elif nota:
        valores = re.findall(r"\$[\d.]+", nota)
        e["precio_etiqueta"] = " – ".join(v.rstrip(".") for v in valores)
    elif precio is None:
        e["entrada_paga"] = True
    elif desde and precio:
        e["precio_etiqueta"] = f"Desde ${precio:,.0f}".replace(",", ".")
    return e


def calendario_mec(html, fuente, url, direccion, hoy):
    fichas = []
    for s in html.select('script[type="application/ld+json"]'):
        try:
            contenido = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s.get_text())
            fichas.extend(eventos_schema(json.loads(contenido)))
        except ValueError:
            continue
    if not fichas:
        raise ValueError("No se encontró el calendario de la sala")

    eventos, fallidos, cache, vistos = [], set(), {}, set()
    for f in fichas:
        fecha, enlace = f.get("startDate", "")[:10], f.get("url", "")
        if not enlace or urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) or (enlace, fecha) in vistos:
            continue
        if not hoy <= date.fromisoformat(fecha) <= hoy + timedelta(days=30):
            continue
        vistos.add((enlace, fecha))
        try:
            if enlace not in cache:
                cache[enlace] = descargar(enlace)
            detalle = cache[enlace]
            cuerpo = detalle.select_one(".mec-single-event-description")
            if not cuerpo:
                raise ValueError("Ficha incompleta")
            descripcion = texto(cuerpo)
            if re.search(
                r"\bsuspendid[ao]\b|\bcancelad[ao]\b|\breprogramad[ao]\b",
                normalizar(descripcion),
            ):
                continue
            hora = hora_visible(texto(detalle.select_one(
                ".mec-single-event-time .mec-events-abbr"
            )))
            if not hora:
                continue

            loc = f.get("location", {})
            lugar = loc.get("name") or fuente
            domicilio = loc.get("address") or direccion
            if isinstance(domicilio, dict):
                domicilio = domicilio.get("streetAddress", direccion)

            if fuente == "Teatro Astengo" and not re.search(r"\d", str(domicilio)):
                domicilio = direccion

            if fuente == "Biblioteca Vigil":
                calle = re.search(r"\b(Alem|Gaboto)\s+(\d{3,4})\b", descripcion, re.I)
                if calle:
                    domicilio = calle[0]
                if "astronom" in normalizar(f.get("name", "")):
                    lugar = "Observatorio de la Biblioteca Vigil"
                elif "teatro vigil" in normalizar(f.get("name", "")):
                    lugar, domicilio = "Teatro Vigil", "Alem 3086"

            precio_visible = texto(detalle.select_one(".mec-single-event-cost"))
            eventos.append(actividad_ampliada(
                fecha, hora, f.get("name", ""), enlace, fuente, domicilio,
                precio_visible + " " + descripcion, lugar,
            ))
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos


def calendario_paginas(html, fuente, url, direccion, hoy):
    selectores = {
        "Teatro Broadway": "a[href*='/cartelera/']",
        "Distrito Siete": "a[href^='/eventos/']",
        "Metropolitano": "a[href*='/espectaculo/']",
        "Biblioteca Argentina Dr. Juan Álvarez": "h2 a[href], h3 a[href]",
    }
    tarjetas = html.select(selectores[fuente])
    if not tarjetas:
        raise ValueError("No se encontró la programación de la fuente")

    eventos, fallidos, vistos = [], set(), set()
    for a in tarjetas:
        enlace = urljoin(url, a["href"])
        if enlace in vistos or urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        vistos.add(enlace)
        if fuente == "Distrito Siete" and "venta finalizada" in normalizar(texto(a)):
            continue
        try:
            detalle = descargar(enlace)
            if fuente == "Distrito Siete":
                titulo = texto(a.select_one("h2")) or texto(detalle.select_one("h2"))
            elif fuente == "Teatro Broadway":
                titulo = (
                    texto(a.select_one(".tbr-show-card-title"))
                    or texto(detalle.select_one("h1"))
                )
            else:
                titulo = texto(detalle.select_one("h1")) or texto(a)

            cuerpo = detalle.select_one(
                ".entry-content, .tbr-detail-text, main, #main"
            ) or detalle
            descripcion = texto(cuerpo)
            if re.search(
                r"funcion\s+(?:se encuentra\s+)?suspendida|evento cancelado|show cancelado",
                normalizar(descripcion),
            ):
                continue

            if fuente == "Distrito Siete":
                m = re.search(
                    r"(\d{1,2})\.([A-Z]{3})\.(20\d{2})\s+(\d{1,2}:\d{2})hs",
                    descripcion,
                )
                abreviaturas = (
                    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
                    "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
                )
                fechas = []
                if m and m[2] in abreviaturas:
                    dia = date(int(m[3]), abreviaturas.index(m[2]) + 1, int(m[1]))
                    if hoy <= dia <= hoy + timedelta(days=30):
                        fechas = [(dia.isoformat(), m[4])]
                precio = re.search(
                    r"Precios desde\s+ARS\s*(\$\s*[\d.,]+)", descripcion
                )
                descripcion_precio = (precio[1] if precio else "") + " " + titulo
            else:
                if fuente == "Teatro Broadway":
                    fechas_texto = " ".join(
                        texto(x) for x in detalle.select(".tbr-detail-text")
                    )
                    descripcion = texto(detalle.select_one("main")) or texto(detalle)
                else:
                    fechas_texto = descripcion
                anio_confirmado = fuente == "Metropolitano" and bool(re.search(
                    rf'(?:datePublished|dateModified)[^\n]{{0,40}}{hoy.year}-',
                    str(detalle),
                ))
                fechas = fechas_publicadas(fechas_texto, hoy, anio_confirmado)
                descripcion_precio = descripcion

            for fecha, hora in fechas:
                e = actividad_ampliada(
                    fecha, hora, titulo, enlace, fuente, direccion,
                    descripcion_precio, desde=fuente == "Distrito Siete",
                )
                if fuente == "Distrito Siete":
                    e["descripcion"] = resumen(titulo)
                eventos.append(e)
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos


def calendario(html, fuente, url, direccion, hoy):
    if fuente in ("Teatro Astengo", "ATIR", "Biblioteca Vigil"):
        return calendario_mec(html, fuente, url, direccion, hoy)
    if fuente in (
        "Teatro Broadway", "Distrito Siete", "Metropolitano",
        "Biblioteca Argentina Dr. Juan Álvarez",
    ):
        return calendario_paginas(html, fuente, url, direccion, hoy)
    return _calendario_anterior(html, fuente, url, direccion, hoy)


if __name__ == "__main__":
    actualizar()

