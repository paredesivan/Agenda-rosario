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


if __name__ == "__main__":
    actualizar()
