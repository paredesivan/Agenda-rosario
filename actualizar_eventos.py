"""Actualiza la agenda desde fuentes oficiales de Rosario."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

ARCHIVO = Path(__file__).with_name("eventos.json")
FUENTE = "https://www.rosario.gob.ar/inicio/index.php/agenda/buscar"
ZONA = ZoneInfo("America/Argentina/Cordoba")

CATEGORIAS = (
    "cine", "teatro", "música", "concierto", "feria",
    "muestra", "exposición", "festival", "danza",
    "planetario", "arte", "visita guiada", "libro"
)

GRATUIDAD = (
    "entrada libre y gratuita",
    "entrada gratuita",
    "actividad gratuita",
    "entrada libre",
    "acceso gratuito",
)


def descargar(url):
    respuesta = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "AgendaRosario/1.0"}
    )
    respuesta.raise_for_status()
    return BeautifulSoup(respuesta.text, "html.parser")


def obtener_enlaces():
    enlaces = {}

    for pagina in range(5):
        html = descargar(f"{FUENTE}?page={pagina}")

        for enlace in html.select("a[href]"):
            url = urljoin(FUENTE, enlace["href"])
            nombre = enlace.get_text(" ", strip=True)

            if "/inicio/" not in url or len(nombre) < 12:
                continue

            if re.search(r"\b\d{2}\.\d{2}\b", nombre):
                enlaces[url] = nombre

    return enlaces


def extraer_fecha(texto):
    patron = r"\b(\d{1,2})[./](\d{1,2})[./](2026|2027)\b"
    coincidencia = re.search(patron, texto)

    if not coincidencia:
        return None

    dia, mes, anio = map(int, coincidencia.groups())

    try:
        return datetime(anio, mes, dia).date()
    except ValueError:
        return None


def extraer_hora(texto):
    patrones = (
        r"\b(?:a las|desde las|hora:?)\s*(\d{1,2})[:.](\d{2})",
        r"\b(?:a las|desde las|hora:?)\s*(\d{1,2})\s*h\b",
    )

    for patron in patrones:
        resultado = re.search(patron, texto, re.IGNORECASE)

        if resultado:
            hora = int(resultado.group(1))
            minuto = int(resultado.group(2)) if resultado.lastindex == 2 else 0

            if hora < 24 and minuto < 60:
                return f"{hora:02d}:{minuto:02d}"

    return None


def construir_evento(url, nombre, hoy):
    html = descargar(url)
    contenido = html.select_one("main") or html
    texto = contenido.get_text(" ", strip=True)
    minusculas = texto.lower()

    if not any(palabra in minusculas for palabra in CATEGORIAS):
        return None

    if not any(frase in minusculas for frase in GRATUIDAD):
        return None

    fecha = extraer_fecha(texto)
    hora = extraer_hora(texto)

    if not fecha or not hora:
        return None

    if not hoy <= fecha <= hoy + timedelta(days=30):
        return None

    titulo = html.select_one("h1")
    titulo = titulo.get_text(" ", strip=True) if titulo else nombre

    return {
        "fecha": fecha.isoformat(),
        "hora": hora,
        "nombre": titulo,
        "lugar": "Consultar ubicación en el evento",
        "direccion": "Rosario, Santa Fe",
        "descripcion": "Actividad cultural publicada por la Municipalidad.",
        "evento_url": url,
        "precio": 0,
        "origen": "Municipalidad de Rosario"
    }


def actualizar():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    enlaces = obtener_enlaces()
    eventos = []

    for url, nombre in enlaces.items():
        try:
            evento = construir_evento(url, nombre, hoy)
            if evento:
                eventos.append(evento)
        except (requests.RequestException, ValueError):
            continue

    eventos.sort(key=lambda e: (e["fecha"], e["hora"]))
    anteriores = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    conocidos = anteriores.get("eventos", [])

    for evento in conocidos:
        if evento["fecha"] >= hoy.isoformat():
            if evento["evento_url"] not in {e["evento_url"] for e in eventos}:
                eventos.append(evento)

    datos = {
        "actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
        "eventos": sorted(eventos, key=lambda e: (e["fecha"], e["hora"]))
    }

    ARCHIVO.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(f"Agenda revisada: {len(eventos)} actividades")


if __name__ == "__main__":
    actualizar()
