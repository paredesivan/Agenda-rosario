"""Ejecuta recolectores aislados. Publica sólo resultados validados."""
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from control_http import atomico

ROOT = Path(__file__).resolve().parent
ETAPAS = [('actualizar_eventos.py', 35*60), ('fuentes_nuevas.py', 45*60),
          ('fuentes_refi_folklore.py', 12*60), ('fuentes_ampliadas.py', 8*60), ('resolver_candidatos.py', 8*60), ('precios_lavarden.py', 15*60),
          ('precios_ticketek.py', 5*60)]


def validar(datos):
    if not isinstance(datos, dict) or not isinstance(datos.get('eventos'), list):
        raise ValueError('Agenda sin lista de eventos')
    for e in datos['eventos']:
        if not isinstance(e, dict):
            raise ValueError('Evento no es un objeto')
        date.fromisoformat(e['fecha'])
        # Algunos eventos tienen horario por confirmar o rangos publicados.
        if not all(isinstance(e.get(k), str) and e[k].strip() for k in ('nombre', 'hora', 'lugar')):
            raise ValueError('Evento sin campos mínimos')
    return datos


def proteger(antes, despues, hoy):
    validar(antes)
    validar(despues)
    futuros = [e for e in antes['eventos'] if e['fecha'] >= hoy.isoformat()]
    nuevos = despues['eventos']
    conteo_a = Counter(e.get('origen', 'Manual') for e in futuros)
    conteo_b = Counter(e.get('origen', 'Manual') for e in nuevos if e['fecha'] >= hoy.isoformat())
    sospechosas = {f for f, n in conteo_a.items()
                   if conteo_b[f] == 0 or (n >= 5 and conteo_b[f] < n * .5)}
    # Una lectura válida de ACR reemplaza su snapshot, incluso si queda vacío.
    # No restaurar publicaciones que ACR quitó o suspendió. El identificador
    # debe cambiar en esta etapa; uno heredado no autoriza futuras pérdidas.
    if despues.get('revision_acr_id') and despues.get('revision_acr_id') != antes.get('revision_acr_id'):
        sospechosas.discard('Agenda Cultural Rosario')
    avisos = []
    def clave(e):
        return tuple(e.get(k, '') for k in ('fecha', 'hora', 'nombre', 'lugar', 'origen'))
    vistos = {clave(e) for e in nuevos}
    revision = despues.get('revision_ampliadas', {})
    urls_revisadas = set()
    if revision.get('id') and revision.get('id') != antes.get('revision_ampliadas', {}).get('id'):
        urls_revisadas = {tuple(k) for k in revision.get('fichas_revisadas', [])}
    resolucion = despues.get('revision_resolucion', {})
    if resolucion.get('id') and resolucion.get('id') != antes.get('revision_resolucion', {}).get('id'):
        urls_revisadas.update(tuple(k) for k in resolucion.get('fichas_revisadas', []))
    for e in futuros:
        if (e.get('origen'), e.get('evento_url')) in urls_revisadas:
            continue
        if e.get('origen', 'Manual') in sospechosas and clave(e) not in vistos:
            nuevos.append({**e, 'revision_pendiente': True})
            vistos.add(clave(e))
    for fuente in sorted(sospechosas):
        avisos.append({'fuente': fuente, 'antes': conteo_a[fuente], 'obtenidos': conteo_b[fuente],
                       'motivo': 'Caída sospechosa: conservados eventos futuros anteriores'})
    if avisos:
        despues['estado'] = 'parcial'
    return despues, avisos


def ejecutar_etapa(root, script, limite, ejecutar=subprocess.run, hoy=None):
    hoy = hoy or datetime.now(ZoneInfo('America/Argentina/Cordoba')).date()
    archivo = root / 'eventos.json'
    antes = validar(json.loads(archivo.read_text(encoding='utf-8')))
    with tempfile.TemporaryDirectory(prefix='agenda-') as tmp:
        destino = Path(tmp) / 'proyecto'
        shutil.copytree(root, destino, ignore=shutil.ignore_patterns('.git', '__pycache__', '.venv', 'node_modules', 'reportes'))
        try:
            ejecutar([sys.executable, '-u', script], cwd=destino, timeout=limite, check=True)
            despues, avisos = proteger(antes, json.loads((destino / 'eventos.json').read_text(encoding='utf-8')), hoy)
            auxiliares = {}
            for p in destino.glob('*.json'):
                if p.name.startswith(('cache_', 'candidatos_', 'revision_', 'verificacion_')) or p.name in ('fuentes_revisadas.json', 'estado_http.json'):
                    auxiliares[p.name] = json.loads(p.read_text(encoding='utf-8'))
        except (subprocess.SubprocessError, ValueError, OSError, KeyError, TypeError) as error:
            # Las pausas HTTP sobreviven aunque se descarte la agenda de la etapa.
            estado_http = destino / 'estado_http.json'
            if estado_http.exists():
                try:
                    atomico(root / 'estado_http.json', json.loads(estado_http.read_text()))
                except (ValueError, OSError):
                    pass
            return {'etapa': script, 'estado': 'fallida', 'error': str(error), 'agenda_conservada': True}
        # Los archivos de caché y de estado se aceptan únicamente tras validar la etapa.
        for nombre, contenido in auxiliares.items():
            atomico(root / nombre, contenido)
        atomico(archivo, despues)
        return {'etapa': script, 'estado': 'parcial' if avisos or despues.get('estado') == 'parcial' else 'validada', 'avisos': avisos, 'avisos_fuentes': despues.get('avisos_fuentes', [])}


def main():
    inicio = datetime.now(ZoneInfo('America/Argentina/Cordoba')).isoformat()
    resultados = []
    for script, limite in ETAPAS:
        resultado = ejecutar_etapa(ROOT, script, limite)
        resultados.append(resultado)
        print(json.dumps(resultado, ensure_ascii=False), flush=True)
    datos = validar(json.loads((ROOT / 'eventos.json').read_text(encoding='utf-8')))
    if any(r['estado'] != 'validada' for r in resultados):
        datos['estado'] = 'parcial'
    atomico(ROOT / 'eventos.json', datos)
    atomico(ROOT / 'salud_actualizacion.json', {'inicio': inicio, 'etapas': resultados,
            'estado': datos.get('estado'), 'eventos': len(datos['eventos']),
            'fuentes': json.loads((ROOT / 'fuentes_revisadas.json').read_text()).get('fuentes', {}) if (ROOT / 'fuentes_revisadas.json').exists() else {}})
    if all(r['estado'] == 'fallida' for r in resultados):
        raise SystemExit('Todas las etapas fallaron; se conserva la agenda y se avisa en Actions')


if __name__ == '__main__':
    main()
