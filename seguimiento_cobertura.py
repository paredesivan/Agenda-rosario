"""Control persistente de fuentes y pendientes; no modifica eventos ni accesos."""
import json
from datetime import datetime, date
from pathlib import Path


def cargar(root, nombre, defecto):
    path = Path(root) / nombre
    return json.loads(path.read_text()) if path.exists() else defecto


def dias(desde, hasta):
    try:
        return max(0, (date.fromisoformat(hasta[:10]) - date.fromisoformat(desde[:10])).days)
    except (ValueError, TypeError):
        return None


def registrar_fuentes(root, fuentes, revisiones, fecha, guardar, actual):
    registro = cargar(root, '.agenda/seguimiento_fuentes.json', {})
    esperadas = cargar(root, 'fuentes_esperadas.json', {}).get('fuentes', [])
    previo = cargar(root, 'estado_agenda.json', {}).get('fuentes', [])
    nombres = set(registro) | set(esperadas) | {f['nombre'] for f in previo}
    por_nombre = {f['nombre']: f for f in fuentes}
    for nombre in sorted(nombres | set(por_nombre)):
        fila = por_nombre.get(nombre)
        r = registro.setdefault(nombre, {'primer_registro': fecha})
        presente = actual and nombre in revisiones
        if presente:
            r['ultimo_diagnostico'] = fecha
        if fila is None:
            fila = dict(nombre=nombre, estado='pendiente', eventos=0, antes=0,
                        conservados=0, caida=False, motivo='Sin diagnóstico en esta ejecución.',
                        accion='Revisar la fuente; su ausencia no demuestra que esté vacía.')
            fuentes.append(fila)
        fila['diagnostico_actual'] = bool(presente)
        fila['ultimo_diagnostico'] = r.get('ultimo_diagnostico')
        fila['dias_sin_diagnostico'] = dias(r.get('ultimo_diagnostico', r['primer_registro']), fecha)
    guardar(Path(root)/'.agenda/seguimiento_fuentes.json', registro)
    fuentes.sort(key=lambda f: f['nombre'])


def medir_pendientes(root, fecha, guardar):
    registro = cargar(root, '.agenda/seguimiento_pendientes.json', {})
    cola = cargar(root, 'cache_resolucion_candidatos.json', {}).get('cola', {})
    pendientes = []
    for key, entrada in cola.items():
        resultado = entrada.get('resultado', {})
        if resultado.get('estado') not in ('pendiente', 'reintentar', 'diferido'):
            continue
        evidencia = [fecha[:10]]
        for valor in (registro.get(key), entrada.get('intento'), entrada.get('visto')):
            if isinstance(valor, str) and dias(valor, fecha) is not None:
                evidencia.append(valor[:10])
        desde = min(evidencia)
        registro[key] = desde
        pendientes.append(dict(fuente=entrada.get('fuente', ''), desde_observado=desde,
                               dias=dias(desde, fecha)))
    # Sólo mantiene candidatos todavía pendientes; no guarda URLs en el panel.
    activos = {k: registro[k] for k, e in cola.items()
               if e.get('resultado', {}).get('estado') in ('pendiente', 'reintentar', 'diferido')}
    guardar(Path(root)/'.agenda/seguimiento_pendientes.json', activos)
    return {'cantidad': len(pendientes), 'mayores_7_dias': sum(p['dias'] >= 7 for p in pendientes),
            'antiguedad_maxima_dias': max((p['dias'] for p in pendientes), default=0),
            'criterio': 'Desde la primera evidencia registrada; puede ser anterior.',
            'por_fuente': {f: sum(p['fuente'] == f for p in pendientes)
                           for f in sorted({p['fuente'] for p in pendientes})}}


def revisar_municipal(root, panel, contexto, fecha, actual):
    revision = cargar(root, 'revision_cobertura_municipal.json', {})
    desde = contexto.get('inicio') or fecha
    vigente = actual and revision.get('revision', '') >= desde
    consultadas = revision.get('fichas_consultadas', 0) if vigente else None
    if actual and (not vigente or not consultadas):
        panel['alertas'].append(dict(tipo='cobertura', mensaje=
            'La agenda municipal no tiene fichas consultadas en este intento. '
            'Los eventos conservados no prueban una revisión nueva.'))
    return dict(diagnostico_actual=bool(vigente), fichas_consultadas=consultadas,
                consultas_fallidas=revision.get('fichas_con_error') if vigente else None)


def completar_informe(root, panel, salud, contexto, guardar):
    fecha = panel['generado']
    actual = panel['fuentes_son_del_intento_actual']
    revisiones = dict(salud.get('fuentes', {})) if actual else {}
    municipal = revisar_municipal(root, panel, contexto, fecha, actual)
    if municipal['diagnostico_actual'] and municipal['fichas_consultadas']:
        revisiones['Municipalidad de Rosario'] = 'Consulta de fichas registrada'
    registrar_fuentes(root, panel['fuentes'], revisiones, fecha, guardar, actual)
    ausentes = [f['nombre'] for f in panel['fuentes'] if not f['diagnostico_actual']]
    if actual and ausentes:
        panel['alertas'].append(dict(tipo='cobertura', mensaje=
            f'{len(ausentes)} fuentes registradas carecen de diagnóstico propio en este intento. '
            'Se mantienen visibles para revisar su cobertura.'))
    pendientes = medir_pendientes(root, fecha, guardar)
    if pendientes['mayores_7_dias']:
        panel['alertas'].append(dict(tipo='pendientes', mensaje=
            f"{pendientes['mayores_7_dias']} candidatos llevan al menos siete días pendientes."))
    try:
        duracion = max(0, (datetime.fromisoformat(fecha) - datetime.fromisoformat(contexto['inicio'])).total_seconds()/60)
    except (ValueError, TypeError, KeyError):
        duracion = None
    panel['control_cobertura'] = dict(fuentes_sin_diagnostico=ausentes,
        municipal=municipal, pendientes=pendientes,
        minutos_hasta_informe=round(duracion, 2) if duracion is not None else None,
        tiempo_intervencion_humana='No medido')
    panel['resumen']['fuentes'] = len(panel['fuentes'])
    if panel['estado'] == 'bien' and panel['alertas']:
        panel['estado'] = 'atencion'
    guardar(Path(root)/'control_cobertura.json', panel['control_cobertura'])


def texto_control(panel):
    c = panel['control_cobertura']
    return ['', '## Control de continuidad', '',
        f"Fuentes sin diagnóstico propio: {len(c['fuentes_sin_diagnostico'])}.",
        f"Candidatos pendientes: {c['pendientes']['cantidad']}; con siete días o más: {c['pendientes']['mayores_7_dias']}.",
        f"Minutos desde el inicio hasta este informe: {c['minutos_hasta_informe']}.",
        'El tiempo de intervención humana no se mide automáticamente.']
