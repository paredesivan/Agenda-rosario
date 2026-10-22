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
          ('fuentes_refi_folklore.py', 12*60), ('fuentes_ampliadas.py', 8*60), ('fuentes_espacios_oficiales.py', 8*60), ('resolver_candidatos.py', 8*60), ('precios_lavarden.py', 15*60),
          ('precios_ticketek.py', 5*60), ('fuente_autodromo.py', 3*60)]


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


def _identidad_evento(e):
    """Identificación estable ante cambios de hora, sin confundir funciones."""
    fuente = e.get('origen', 'Manual')
    titulo = ' '.join(e.get('nombre', '').casefold().split())
    fecha = e.get('fecha', '')
    url = (e.get('evento_url') or '').strip().rstrip('/')
    # Incluimos fecha para evitar confundir distintas funciones
    # que comparten una misma página de la sala.
    if url:
        return (fuente, url, fecha, titulo)
    lugar = ' '.join(e.get('lugar', '').casefold().split())
    return (fuente, '', fecha, titulo, lugar)


def proteger(antes, despues, hoy):
    """Retener cada evento futuro ausente salvo baja individual documentada."""
    validar(antes)
    validar(despues)
    actuales = despues['eventos']
    vistos = {_identidad_evento(e) for e in actuales}
    # No basta un HTTP 200, una ficha revisada, un listado vacío ni
    # una revisión ACR para autorizar el borrado.
    bajas = set()
    for baja in despues.get('bajas_confirmadas', []):
        if not isinstance(baja, dict):
            continue
        if (baja.get('motivo') in ('cancelado', 'suspendido', 'retirado')
                and baja.get('evidencia_url') and baja.get('fecha')
                and baja.get('nombre') and baja.get('origen')):
            bajas.add(_identidad_evento(baja))
    conservados = Counter()
    for anterior in antes['eventos']:
        if anterior['fecha'] < hoy.isoformat():
            continue
        identidad = _identidad_evento(anterior)
        if identidad in vistos or identidad in bajas:
            continue
        actuales.append({**anterior, 'revision_pendiente': True})
        vistos.add(identidad)
        conservados[anterior.get('origen', 'Manual')] += 1
    avisos = [{'fuente': fuente, 'conservados': cantidad,
               'motivo': 'Fichas futuras no recuperadas: conservadas pendientes de verificación'}
              for fuente, cantidad in sorted(conservados.items())]
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
        # La página de espacios se genera en el aislamiento y sólo se acepta
        # tras validar la agenda de esta etapa.
        if script == 'fuentes_espacios_oficiales.py' and (destino / 'espacios.html').is_file():
            shutil.copy2(destino / 'espacios.html', root / 'espacios.html')
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
    # Aplicar después de la protección: los respaldos no reintroducen duplicados.
    from actualizar_eventos import sin_repetidos
    antes_deduplicar = len(datos['eventos'])
    datos['eventos'] = sin_repetidos(datos['eventos'])
    duplicados = antes_deduplicar - len(datos['eventos'])
    atomico(ROOT / 'eventos.json', datos)
    atomico(ROOT / 'salud_actualizacion.json', {'inicio': inicio, 'fin': datetime.now(ZoneInfo('America/Argentina/Cordoba')).isoformat(),
            'duplicados_unificados': duplicados, 'etapas': resultados,
            'estado': datos.get('estado'), 'eventos': len(datos['eventos']),
            'fuentes': json.loads((ROOT / 'fuentes_revisadas.json').read_text()).get('fuentes', {}) if (ROOT / 'fuentes_revisadas.json').exists() else {}})
    if all(r['estado'] == 'fallida' for r in resultados):
        raise SystemExit('Todas las etapas fallaron; se conserva la agenda y se avisa en Actions')


if __name__ == '__main__':
    main()

