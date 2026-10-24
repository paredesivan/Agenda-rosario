"""Horizonte de recolección compartido por los lectores de carteleras."""
import json
from pathlib import Path


def horizonte_dias(path=None):
    archivo = Path(path) if path is not None else Path(__file__).with_name('config_recoleccion.json')
    config = json.loads(archivo.read_text(encoding='utf-8')) if archivo.exists() else {}
    dias = config.get('dias_futuros', 180)
    if isinstance(dias, bool) or not isinstance(dias, int) or not 1 <= dias <= 366:
        raise ValueError('dias_futuros debe ser un entero entre 1 y 366')
    return dias


HORIZONTE_DIAS = horizonte_dias()
