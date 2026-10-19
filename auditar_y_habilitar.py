"""Audita fuentes candidatas de Agenda Rosario, sin inferir permisos del acceso público.

Uso: python auditar_y_habilitar.py [--activar]
--activar sólo habilita fuentes con revisión documentada en revisiones_fuentes.json,
y con verificación HTTP real; NO elude robots.txt dentro de los extractores.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests

BASE = Path(__file__).resolve().parent
CONFIG = BASE / 'fuentes_ampliadas.json'
REVISIONS = BASE / 'revisiones_fuentes.json'
REPORT = BASE / 'auditoria_acceso_resultados.json'
UA = 'AgendaRosario/3.0 (+https://paredesivan.github.io/Agenda-rosario/)'


def clasificar_robots(status, body, url):
    if status in (404, 410):
        return 'ausente'
    if status != 200 or '<html' in body.lower() or '<!doctype' in body.lower():
        return 'indeterminado'
    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return 'permitido' if rp.can_fetch(UA, url) else 'excluido'


def evaluar(fuente, revision, sesion):
    url = fuente['listado']
    parsed = urlsplit(url)
    r = {'fuente': fuente['nombre'], 'url': url, 'habilitada_antes': bool(fuente.get('habilitada'))}
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return {**r, 'estado': 'descartada', 'motivo': 'URL inválida o no HTTPS'}
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    try:
        rob = sesion.get(robots_url, timeout=(5, 12), allow_redirects=False, headers={'User-Agent': UA})
        r['robots'] = clasificar_robots(rob.status_code, rob.text[:100000], url)
        if rob.status_code in (403, 429) or r['robots'] == 'indeterminado':
            return {**r, 'estado': 'descartada', 'motivo': 'robots no verificable o acceso restringido'}
        if r['robots'] == 'excluido':
            return {**r, 'estado': 'descartada', 'motivo': 'robots excluye la ruta: requiere permiso o excepción jurídica documentada antes de automatizar'}
        response = sesion.get(url, timeout=(5, 12), allow_redirects=False, headers={'User-Agent': UA})
        r['http_listado'] = response.status_code
        r['html_publico'] = response.status_code == 200 and '<html' in response.text[:5000].lower()
    except requests.RequestException as exc:
        return {**r, 'estado': 'descartada', 'motivo': f'fallo HTTP: {type(exc).__name__}'}
    if not r['html_publico']:
        return {**r, 'estado': 'descartada', 'motivo': 'listado sin HTML público HTTP 200'}
    if r['robots'] == 'indeterminado':
        return {**r, 'estado': 'descartada', 'motivo': 'robots no interpretable; requiere inspección manual'}
    if r['robots'] == 'excluido':
        # El runtime de los extractores respeta Disallow. No crear un bypass sin
        # excepción auditada aplicada también al control de red correspondiente.
        return {**r, 'estado': 'descartada', 'motivo': 'robots excluye ruta; sin excepción de acceso integrada'}
    campos = ('acceso_publico_verificado', 'terminos_revisados',
              'sin_prohibicion_contractual_aplicable', 'sin_barrera_tecnica',
              'sin_impedimento_legal_identificado', 'fichas_y_parser_verificados')
    if not isinstance(revision, dict) or any(revision.get(c) is not True for c in campos):
        return {**r, 'estado': 'descartada', 'motivo': 'falta auditoría contractual, jurídica o de fichas'}
    if not revision.get('evidencia_url') or not revision.get('revision_fecha'):
        return {**r, 'estado': 'descartada', 'motivo': 'falta evidencia fechada'}
    return {**r, 'estado': 'aprobada', 'motivo': 'revisión documentada y acceso comprobado'}


def ejecutar(activar=False, root=BASE, sesion=None):
    root = Path(root)
    config = json.loads((root / 'fuentes_ampliadas.json').read_text(encoding='utf-8'))
    revisiones = json.loads((root / 'revisiones_fuentes.json').read_text(encoding='utf-8'))
    sesion = sesion or requests.Session()
    resultados = []
    for fuente in config['fuentes']:
        if fuente.get('nombre') not in revisiones:
            continue
        r = evaluar(fuente, revisiones[fuente['nombre']], sesion)
        resultados.append(r)
        if activar:
            fuente['habilitada'] = r['estado'] == 'aprobada'
            fuente['motivo'] = r['motivo']
    (root / 'auditoria_acceso_resultados.json').write_text(json.dumps({
        'fecha_utc': datetime.now(timezone.utc).isoformat(), 'resultados': resultados
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if activar:
        tmp = root / 'fuentes_ampliadas.json.tmp'
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(root / 'fuentes_ampliadas.json')
    return resultados


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--activar', action='store_true')
    opt = args.parse_args()
    for registro in ejecutar(opt.activar):
        print(registro['fuente'], '->', registro['estado'], '|', registro['motivo'])
