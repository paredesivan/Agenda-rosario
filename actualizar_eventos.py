"""Valida eventos y actualiza marca de tiempo si hay cambios reales.

Para añadir eventos verificados, editá data/eventos.json o incorporá una
fuente oficial con extracción y revisión. No inventa datos ni usa búsquedas
como enlaces a eventos.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "eventos.json"


def validar(evento):
    obligatorios = ("fecha", "hora", "nombre", "lugar", "direccion", "descripcion")
    if any(not evento.get(campo) for campo in obligatorios):
        raise ValueError(f"Evento incompleto: {evento.get('nombre', '?')}")
    url = evento.get("evento_url", "")
    if url and urlparse(url).scheme != "https":
        raise ValueError(f"La URL debe ser HTTPS: {url}")
    if url and "google.com/search" in url:
        raise ValueError("No se aceptan búsquedas de Google como página oficial")


def main():
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    for evento in datos["eventos"]:
        validar(evento)
    print(f"Revisados {len(datos['eventos'])} eventos. Sin cambios automáticos.")
    print("Para descubrir eventos automáticamente hay que configurar fuentes fiables.")


if __name__ == "__main__":
    main()
