"""Diagnóstico reproducible. No confunde extracción con cobertura total del origen."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def leer(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def generar(root, inicio=None, hoy=None):
    from actualizar_eventos import eventos_duplicados
    root = Path(root)
    hoy = hoy or datetime.now(ZoneInfo('America/Argentina/Cordoba')).date().isoformat()
    datos = leer(root / 'eventos.json', {'eventos': []})
    actuales = [e for e in datos['eventos'] if e['fecha'] >= hoy]
    por_fecha = defaultdict(list)
    for e in actuales:
        por_fecha[e['fecha']].append(e)
    revision = leer(root / 'revision_cobertura_municipal.json', {})
    vigente = bool(inicio and revision.get('revision', '') >= inicio)
    consultas, ausentes = [], []
    for ficha in revision.get('fichas', []):
        if ficha.get('error'):
            estado = 'consulta_fallida'
        elif not ficha.get('funciones'):
            estado = 'sin_funciones_extraidas'
        else:
            estado = 'con_funciones_extraidas'
        consultas.append({'url': ficha['url'], 'estado': estado, 'funciones': ficha.get('funciones', 0),
                          'motivos': ficha.get('motivos', []), 'error': ficha.get('error', '')})
        for e in ficha.get('detalle_funciones', []):
            if e['fecha'] < hoy:
                continue
            coincidencias = por_fecha[e['fecha']]
            if not any((e.get('evento_url') == otro.get('evento_url') and
                        e['hora'] == otro['hora'] and e['lugar'] == otro['lugar']) or
                       eventos_duplicados(e, otro) for otro in coincidencias):
                ausentes.append(e)
    candidatos = []
    for name in ('candidatos_fuentes_adicionales.json', 'candidatos_fuentes_ampliadas.json', 'candidatos_passline.json'):
        guardado = leer(root / name, {})
        elementos = guardado if isinstance(guardado, list) else guardado.get('candidatos', [])
        for e in elementos:
            if not isinstance(e, dict):
                continue
            candidatos.append({k: e.get(k, '') for k in ('fuente', 'nombre', 'url', 'fecha', 'motivo')})
    resolucion = leer(root / 'revision_resolucion_candidatos.json', {})
    resultado = {'datos_actualizados': datos.get('actualizado'), 'fecha_corte': hoy,
                 'eventos_futuros_publicados': len(actuales), 'por_fuente': dict(Counter(e.get('origen', '') for e in actuales)),
                 'revision_municipal': revision.get('revision'), 'municipal_del_intento_actual': vigente,
                 'fichas_municipales': consultas, 'estados_municipales': dict(Counter(c['estado'] for c in consultas)),
                 'comparacion_por_funcion_disponible': any('detalle_funciones' in f for f in revision.get('fichas', [])),
                 'funciones_extraidas_ausentes': ausentes, 'candidatos': candidatos,
                 'resolucion_revision': resolucion.get('revision'), 'resolucion_candidatos': resolucion.get('resultados', []),
                 'alcance': 'Compara diagnósticos de extracción y agenda. No mide publicaciones nunca descubiertas ni garantiza cobertura completa de las fuentes.'}
    (root / 'cobertura_actual.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lineas = ['# Cobertura actual de la agenda', '', resultado['alcance'], '',
              f"Datos de la agenda: {datos.get('actualizado')}. Corte: {hoy}.",
              f"Eventos futuros: {len(actuales)}. Revisión municipal: {revision.get('revision', 'sin datos')}.",
              f"Diagnóstico municipal de este intento: {'sí' if vigente else 'no; es un corte anterior o una revisión local'}.", '',
              '| Resultado municipal | Fichas |', '|---|---:|',
              *[f'| {k} | {v} |' for k,v in resultado['estados_municipales'].items()], '',
              f"Funciones extraídas ausentes de la agenda: {len(ausentes) if resultado['comparacion_por_funcion_disponible'] else 'no medible con el informe antiguo; falta detalle por función'}.", '',
              '## Consultas fallidas y fichas sin funciones', '']
    for c in consultas:
        if c['estado'] != 'con_funciones_extraidas':
            lineas.append(f"- {c['url']} — {c['error'] or '; '.join(c['motivos']) or 'Sin explicación registrada; revisar.'}")
    lineas += ['', '## Candidatos y resolución', '',
               'Los candidatos no equivalen a eventos únicos perdidos. La resolución conserva el motivo por ficha.', '',
               *[f"- {r.get('url', '')} — {r.get('estado', '')}: {r.get('motivo', '')}" for r in resolucion.get('resultados', [])]]
    (root / 'COBERTURA_ACTUAL.md').write_text('\n'.join(lineas)+'\n', encoding='utf-8')
    return resultado


if __name__ == '__main__':
    generar(Path(__file__).resolve().parent)
