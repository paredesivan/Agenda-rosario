"""Aplaza fichas bloqueadas, sin alterar las pausas ni los permisos HTTP."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


def cargar(path):
    return json.loads(path.read_text()) if path.exists() else {}


def registrar(revision, path):
    path = Path(path)
    registro = cargar(path)
    observado = revision.get('revision')
    if not observado:
        return registro
    instante = datetime.fromisoformat(observado)
    for ficha in revision.get('fichas', []):
        error = ficha.get('error', '')
        url = ficha.get('url')
        if not url or not re.search(r'\b(?:403|429)\b', error) or 'pausa' in error.lower():
            continue
        previo = registro.get(url, {}).get('ultimo_bloqueo')
        if previo and datetime.fromisoformat(previo) >= instante:
            continue
        registro[url] = dict(ultimo_bloqueo=observado,
                             reintentar_desde=(instante + timedelta(days=7)).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix('.tmp')
    temporal.write_text(json.dumps(registro, ensure_ascii=False, indent=2)+'\n')
    temporal.replace(path)
    return registro


def planificar(enlaces, revision_path, registro_path, ahora):
    registro = registrar(cargar(Path(revision_path)), registro_path)
    activos, aplazados = set(), []
    for url in enlaces:
        hasta = registro.get(url, {}).get('reintentar_desde')
        if hasta and datetime.fromisoformat(hasta) > ahora:
            aplazados.append(dict(url=url, reintentar_desde=hasta))
        else:
            activos.add(url)
    return activos, sorted(aplazados, key=lambda x:x['url'])
