"""Auditoría semanal no bloqueante de robots.txt para Agenda Rosario.

Inventaría referencias estáticas y URLs ATIR construidas en el código.
No demuestra que todas se soliciten: para eso haría falta instrumentar las descargas.
No obtiene permisos de copyright ni reemplaza la revisión de términos de uso.
"""
import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
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
SOCIALES = frozenset(("instagram.com", "facebook.com"))
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


def asignacion_literal(arbol, variable, predeterminado=None):
    """Extrae estructuras literales, sin ejecutar los recolectores."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            if any(isinstance(t, ast.Name) and t.id == variable for t in objetivos):
                try:
                    return ast.literal_eval(nodo.value)
                except (ValueError, TypeError, SyntaxError, MemoryError):
                    pass
    return predeterminado


def leer_pausas():
    ruta = RAIZ / "actualizar_eventos.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=ruta.name)
    valores = asignacion_literal(arbol, "PAUSAS_POR_HOST", {})
    return valores if isinstance(valores, dict) else {}


def inventario():
    """URLs referenciadas: incluye páginas ATIR dinámicas; no prueba solicitudes."""
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
        if nombre == "fuentes_nuevas.py":
            for sala in asignacion_literal(arbol, "SALAS", ()):
                if isinstance(sala, (tuple, list)) and len(sala) >= 2:
                    slug = sala[1]
                    if isinstance(slug, str) and re.fullmatch(r"[a-z0-9-]+", slug):
                        registrar(sitios, f"https://www.teatrosatir.ar/salas/{slug}/")
    configuracion = RAIZ / "fuentes_adicionales.json"
    if configuracion.exists():
        for fuente in json.loads(configuracion.read_text(encoding="utf-8")).get("fuentes", []):
            if fuente.get("consulta_automatica") and isinstance(fuente.get("url"), str):
                registrar(sitios, fuente["url"])
    for url in FUENTES_DINAMICAS:
        registrar(sitios, url)
    return dict(sorted(sitios.items()))


def es_red_social(host):
    return host.lower().removeprefix("www.") in SOCIALES


def evaluar_reglas(contenido, urls, pausa_configurada=1.5):
    parser = RobotFileParser()
    parser.parse(contenido.splitlines())
    bloqueadas = sorted(u for u in urls if not parser.can_fetch(AGENTE, u))
    demora = parser.crawl_delay(AGENTE)
    return {
        "estado": "rutas_restringidas" if bloqueadas else "sin_restriccion_robots_detectada",
        "rutas_restringidas": bloqueadas,
        "crawl_delay_segundos": demora,
        "pausa_configurada_segundos": pausa_configurada,
        "revisar_demora": bool(demora is not None and demora > pausa_configurada),
    }


def revisar_host(host, urls, obtener=requests.get, pausa_configurada=1.5):
    r = {"dominio": host, "cantidad_urls_referenciadas": len(urls),
         "urls_ejemplo": sorted(urls)[:5], "terminos_de_uso": "PENDIENTE_REVISION_MANUAL"}
    if es_red_social(host):
        # En el código actual son referencias, no descargas de redes sociales.
        # Si se agrega un recolector social, esta excepción deberá revisarse.
        r.update(estado="referencia_social_no_rastreada", nota="Enlace de referencia; no se consulta robots.txt")
        return r
    robots = "https://" + host + "/robots.txt"
    try:
        for _ in range(4):
            respuesta = obtener(robots, headers=HEADERS, timeout=(5, 9), allow_redirects=False)
            r["http_robots"] = respuesta.status_code
            if respuesta.status_code not in (301, 302, 307, 308):
                break
            destino = urljoin(robots, respuesta.headers.get("Location", ""))
            anterior, nuevo = urlsplit(robots), urlsplit(destino)
            if (nuevo.scheme != "https" or not nuevo.hostname or
                    nuevo.hostname.removeprefix("www.") != host.removeprefix("www.") or
                    nuevo.path != "/robots.txt"):
                r.update(estado="redireccion_robots_revisar", redireccion_a=destino)
                return r
            robots = destino
        else:
            r["estado"] = "demasiadas_redirecciones_robots"
            return r
        r["robots_url_final"] = robots
        if respuesta.status_code == 200:
            r.update(evaluar_reglas(respuesta.text, urls, pausa_configurada))
        elif respuesta.status_code in (404, 410):
            r["estado"] = "robots_ausente_no_implica_autorizacion"
        else:
            r["estado"] = "revisar_respuesta_robots"
    except requests.RequestException as exc:
        r["estado"] = "error_robots"
        r["error"] = type(exc).__name__
    return r


def construir_reporte(sitios):
    pausas = leer_pausas()
    res = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(revisar_host, h, urls, requests.get,
                               max(1.5, float(pausas.get(h, 1.5)))) for h, urls in sitios.items()]
        for future in as_completed(futures):
            res.append(future.result())
    res.sort(key=lambda r: r["dominio"])
    return {"generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tipo": "auditoria_tecnica_no_bloqueante",
            "advertencia": "URLs del código, no registro de accesos. robots.txt no otorga permisos legales.",
            "dominios": len(sitios),
            "referencias_sociales_sin_rastreo": sum(es_red_social(h) for h in sitios),
            "resultados": res}


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
                              "robots_ausente_no_implica_autorizacion",
                              "referencia_social_no_rastreada") or x.get("revisar_demora"):
            print("REVISAR", x["dominio"], x["estado"],
                  "demora" if x.get("revisar_demora") else "")


if __name__ == "__main__":
    main()
