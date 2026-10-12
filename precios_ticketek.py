"""Complemento de Agenda Rosario: precios desde Ticketek vinculados por Teatro Astengo.

Se ejecuta DESPUÉS del recolector general. Sólo publica un precio cuando la
página de Ticketek de ese espectáculo lo afirma explícitamente. La consulta
se hace a través de la URL que Teatro Astengo indica como «Comprar Tickets».
No se utilizan resultados de búsqueda ni precios de funciones parecidas.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ARCHIVO = Path(__file__).with_name("eventos.json")
ZONA = ZoneInfo("America/Argentina/Cordoba")
HEADERS = {
    "User-Agent": "AgendaRosario/3.1 (+https://paredesivan.github.io/Agenda-rosario/)",
    "Accept-Language": "es-AR,es;q=0.9",
}
# Se acepta únicamente la cifra presentada explícitamente como «precios desde».
# El importe puede aparecer como «ARS $34.500», «$ 34.500» o «ARS 34500».
MINIMO = re.compile(
    r"\bprecios?\s+desde\s*(?:\:\s*)?(?:(?:ARS|AR\$)\s*)?"
    r"\$?\s*(\d{1,3}(?:[.\s]\d{3})+|\d{4,7})"
    r"(?:\s*,\s*\d{2})?(?!\d)", re.I
)


def dominio(url, host):
    p = urlsplit(url)
    return p.scheme == "https" and p.hostname in (host, "www." + host)


def enlace_ticketek(sopa, base):
    """Lee el botón de la ficha exacta. Jamás intenta adivinar la URL."""
    for enlace in sopa.select("a[href]"):
        url = urljoin(base, enlace["href"].strip())
        if not dominio(url, "ticketek.com.ar"):
            continue
        etiqueta = enlace.get_text(" ", strip=True).lower()
        clases = " ".join(enlace.get("class", []))
        if "comprar" in etiqueta or "ticket" in etiqueta or "ticket" in clases.lower():
            return url
    return None


def desde_ticketek(sopa):
    """Retorna importe sólo cuando el texto visible afirma 'Precios desde'."""
    # Eliminar JSON, scripts, comentarios, menús, contenido invisibilizado.
    copia = BeautifulSoup(str(sopa), "html.parser")
    for tag in copia.select("script, style, noscript, template"):
        tag.decompose()
    fragmentos = [x for x in copia.stripped_strings]
    # El precio puede estar en un elemento inmediatamente siguiente al rótulo.
    # Evita mezclar precios entre tarjetas: no se concatena toda la página.
    for i, fragmento in enumerate(fragmentos):
        if not re.search(r"\bprecios?\s+desde\b", fragmento, re.I):
            continue
        # Máximo 3 fragmentos contiguos, sin saltar a otra tarjeta de evento.
        siguiente = " ".join(fragmentos[i:i + 3])
        for candidato in (fragmento, siguiente):
            match = MINIMO.search(candidato)
            if match:
                n = int(re.sub(r"[.\s]", "", match.group(1)))
                if 100 <= n <= 50_000_000:
                    return n
    return None


def fetch(session, url):
    respuesta = session.get(url, timeout=(8, 15), headers=HEADERS, allow_redirects=True)
    respuesta.raise_for_status()
    # No aceptar una redirección a otro evento o dominio.
    if (not dominio(respuesta.url, "ticketek.com.ar") or
            urlsplit(respuesta.url).path.rstrip("/") != urlsplit(url).path.rstrip("/")):
        raise ValueError("El destino de Ticketek cambió; evitar precios cruzados")
    return BeautifulSoup(respuesta.text, "html.parser")


def es_astengo(evento):
    url = evento.get("evento_url", "")
    return (dominio(url, "teatroastengo.ar") and "/events/" in urlsplit(url).path
            and (evento.get("origen") == "Teatro Astengo" or
                 "astengo" in evento.get("lugar", "").lower()))


def integrar(eventos, fetcher=fetch, pausar=time.sleep):
    fichas, tickets, est = {}, {}, {"enlaces": 0, "con_precio": 0, "sin_precio": 0, "errores": 0}
    session = requests.Session()
    bloqueado = False
    try:
        for evento in eventos:
            if not es_astengo(evento):
                continue
            url = evento["evento_url"]
            if url not in fichas:
                try:
                    detalle = fetcher(session, url)
                    fichas[url] = enlace_ticketek(detalle, url)
                except (requests.RequestException, ValueError):
                    fichas[url] = None
            compra = fichas[url]
            if not compra:
                continue
            est["enlaces"] += 1
            evento["entradas_url"] = compra
            # Evita mantener o asignar precio de otra plataforma o fecha.
            evento["precio"] = None
            evento["precio_etiqueta"] = "Precio a confirmar"
            evento.pop("precio_fuente", None)
            evento.pop("precio_consultado", None)
            if compra not in tickets:
                if bloqueado:
                    tickets[compra] = None
                else:
                    try:
                        pausar(1.5)
                        tickets[compra] = desde_ticketek(fetcher(session, compra))
                    except requests.HTTPError as exc:
                        tickets[compra] = None
                        est["errores"] += 1
                        if exc.response is not None and exc.response.status_code in (403, 429):
                            bloqueado = True
                    except (requests.RequestException, ValueError):
                        tickets[compra] = None
                        est["errores"] += 1
            precio = tickets[compra]
            if precio is None:
                est["sin_precio"] += 1
                continue
            evento["precio"] = precio
            evento["precio_etiqueta"] = f"Precios desde ${precio:,}".replace(",", ".")
            evento["precio_fuente"] = "Ticketek"
            evento["precio_consultado"] = datetime.now(ZONA).strftime("%Y-%m-%d %H:%M")
            est["con_precio"] += 1
    finally:
        session.close()
    return est


def main():
    if not ARCHIVO.exists():
        raise FileNotFoundError(f"No se encontró {ARCHIVO}")
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    estado = integrar(datos.get("eventos", []))
    temporal = Path(str(ARCHIVO) + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ARCHIVO)
    print(f"Ticketek / Astengo: {estado['enlaces']} funciones con link; "
          f"{estado['con_precio']} con precio desde; "
          f"{estado['sin_precio']} sin importe verificable; "
          f"{estado['errores']} errores de consulta")


if __name__ == "__main__":
    main()
