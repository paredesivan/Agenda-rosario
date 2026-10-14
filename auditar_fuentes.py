"""Auditoría no bloqueante: consulta SOLO robots.txt de dominios referenciados.

No decide por sí sola la legalidad del scraping ni cambia la agenda publicada.
"""
import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

RAIZ = Path(__file__).resolve().parent
ARCHIVOS = ("actualizar_eventos.py", "fuentes_nuevas.py", "precios_ticketek.py")
AGENTE = "AgendaRosario"
HEADERS = {"User-Agent": "AgendaRosario/3.1 (+https://github.com/paredesivan/Agenda-rosario)"}
FUENTES_DINAMICAS = (
    "https://www.rosario.gob.ar/inicio/agenda",
    "https://www.rosario.gob.ar/inicio/cultura-y-educacion",
    "https://www.teatrosatir.ar/cartelera/",
)
PATRON_URL = re.compile(r'https?://[^\s"\'<>]+', re.I)


def registrar(sitios, url):
    url = url.rstrip(".,);]}")
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or "." not in p.hostname:
        return
    host = p.hostname.lower()
    if not re.fullmatch(r"[a-z0-9.-]+", host) or host.endswith((".local", ".internal")):
        return
    sitios[host].add(url)


def inventario():
    """Enumera URLs estáticas referenciadas por Python (no prueba uso efectivo)."""
    sitios = defaultdict(set)
    for nombre in ARCHIVOS:
        ruta = RAIZ / nombre
        if not ruta.exists():
            raise FileNotFoundError(f"Falta {ruta}; ejecutar en la raíz del repositorio")
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=nombre)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                for url in PATRON_URL.findall(nodo.value):
                    registrar(sitios, url)
    for url in FUENTES_DINAMICAS:
        registrar(sitios, url)
    return dict(sorted(sitios.items()))


def evaluar_reglas(contenido, urls):
    parser = RobotFileParser()
    parser.parse(contenido.splitlines())
    bloqueadas = sorted(u for u in urls if not parser.can_fetch(AGENTE, u))
    demora = parser.crawl_delay(AGENTE)
    return {
        "estado": "rutas_restringidas" if bloqueadas else "sin_restriccion_robots_detectada",
        "rutas_restringidas": bloqueadas,
        "crawl_delay_segundos": demora,
        "revisar_demora": bool(demora is not None and demora > 1.5),
    }


def revisar_host(host, urls, obtener=requests.get):
    r = {"dominio": host, "cantidad_urls_referenciadas": len(urls),
         "urls_ejemplo": sorted(urls)[:5], "terminos_de_uso": "PENDIENTE_REVISION_MANUAL"}
    try:
        respuesta = obtener("https://" + host + "/robots.txt", headers=HEADERS,
                            timeout=(5, 9), allow_redirects=False)
        r["http_robots"] = respuesta.status_code
        if respuesta.status_code == 200:
            r.update(evaluar_reglas(respuesta.text, urls))
        elif respuesta.status_code in (404, 410):
            r["estado"] = "robots_ausente_no_implica_autorizacion"
        else:
            r["estado"] = "revisar_respuesta_robots"
    except requests.RequestException as exc:
        r["estado"] = "error_robots"
        r["error"] = type(exc).__name__
    return r


def construir_reporte(sitios):
    res = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(revisar_host, h, urls) for h, urls in sitios.items()]
        for future in as_completed(futures):
            res.append(future.result())
    res.sort(key=lambda r: r["dominio"])
    return {"generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tipo": "auditoria_tecnica_no_bloqueante",
            "advertencia": "robots.txt no otorga licencia de copyright ni sustituye términos de uso",
            "dominios": len(sitios), "resultados": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="auditoria_fuentes.json")
    args = ap.parse_args()
    resultado = construir_reporte(inventario())
    Path(args.salida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    print("Dominios:", resultado["dominios"])
    print("Estados:", dict(Counter(x["estado"] for x in resultado["resultados"])))
    for x in resultado["resultados"]:
        if x["estado"] not in ("sin_restriccion_robots_detectada",
                              "robots_ausente_no_implica_autorizacion"):
            print("REVISAR", x["dominio"], x["estado"])


if __name__ == "__main__":
    main()
