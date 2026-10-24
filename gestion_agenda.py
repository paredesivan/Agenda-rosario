"""Coordina respaldo, actualización, diagnóstico y entrega; sin eventos fijos."""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
ZONA = ZoneInfo('America/Argentina/Cordoba')
DATOS = ('eventos.json', 'salud_actualizacion.json', 'fuentes_revisadas.json', 'estado_http.json')
PATRONES = ('cache_*.json', 'candidatos_*.json', 'revision_*.json', 'verificacion_*.json')
VIEJOS = ('auditar_fuentes.yml', 'corregir_pausas.yml', 'instalar_agenda_completa.yml',
          'instalar_fuentes_hello_jaguar.yml', 'instalar_proteccion_eventos.yml',
          'instalar_resolucion_candidatos.yml', 'instalar_deduplicacion_contenido.yml', 'pruebas.yml')
ARCHIVABLES = ('agenda15-10.js', 'instalar_agenda_completa.py', 'instalar_excepciones_robots.py',
              'instalar_fuente_aec.py', 'instalar_horarios_jaguar.py', 'reparar_agenda_hello.py')


def ahora():
    return datetime.now(ZONA).isoformat(timespec='seconds')


def leer(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def guardar(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(f.name, path)


def datos_mutables(root):
    paths = {root / name for name in DATOS if (root / name).exists()}
    for patron in PATRONES:
        paths.update(root.glob(patron))
    return sorted(paths)


def preparar(root=ROOT):
    """Se ejecuta en el checkout de trabajo, nunca sobre el sitio publicado."""
    carpeta = root / 'reportes' / 'respaldo'
    carpeta.mkdir(parents=True, exist_ok=True)
    anteriores = {}
    for path in datos_mutables(root):
        data = path.read_bytes()
        anteriores[path.name] = hashlib.sha256(data).hexdigest()
        (carpeta / path.name).write_bytes(data)
    guardar(root / 'reportes/contexto.json', {'inicio': ahora(), 'datos': anteriores})
    # Copia de la versión recibida, descargable desde el resumen de Actions.
    publicos = {}
    for name in ('index.html', 'agenda.js', 'estilos.css', 'eventos.json', 'estado.html', 'estado_agenda.json'):
        if (root / name).exists():
            publicos[name] = (root / name).read_text(encoding='utf-8')
    if not (root / 'reportes/respaldo_publicado.json.gz').exists():
        with gzip.open(root / 'reportes/respaldo_publicado.json.gz', 'wt', encoding='utf-8') as f:
            json.dump({'capturado': ahora(), 'archivos': publicos}, f, ensure_ascii=False)


def restaurar_datos(root=ROOT):
    contexto = leer(root / 'reportes/contexto.json')
    if not contexto or 'datos' not in contexto:
        raise ValueError('Falta el respaldo anterior; no se publica esta ejecución.')
    for path in datos_mutables(root):
        if path.name not in contexto['datos']:
            path.unlink()
    for name, digest in contexto['datos'].items():
        data = (root / 'reportes/respaldo' / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('El respaldo no coincide con su comprobación de integridad.')
        (root / name).write_bytes(data)


def actualizar(root=ROOT, ejecutar=subprocess.run):
    try:
        ejecutar([sys.executable, '-u', 'actualizacion_segura.py'], cwd=root, timeout=105 * 60, check=True)
        from actualizacion_segura import validar
        validar(leer(root / 'eventos.json'))
        resultado = {'estado': 'completada', 'fin': ahora(), 'datos_conservados': False}
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError) as exc:
        # La causa técnica queda en el artefacto de Actions. El panel no la replica.
        guardar(root / 'reportes/fallo_actualizacion.json', {'tipo': type(exc).__name__})
        pausas = leer(root / 'estado_http.json', {})
        restaurar_datos(root)
        # La restauración no debe borrar una pausa recibida durante este intento.
        anteriores = leer(root / 'estado_http.json', {})
        for host, valor in pausas.items():
            if isinstance(valor, dict) and valor.get('pausado_hasta', 0) > anteriores.get(host, {}).get('pausado_hasta', 0):
                anteriores[host] = valor
        if anteriores: guardar(root / 'estado_http.json', anteriores)
        resultado = {'estado': 'fallida', 'fin': ahora(), 'datos_conservados': True,
                     'mensaje': 'La actualización no terminó. Se conservó la agenda anterior.'}
    guardar(root / 'reportes/resultado_actualizacion.json', resultado)
    return resultado


def clave(e):
    # El origen no integra la identidad: cambiar a una fuente mejor no es un alta.
    from actualizar_eventos import _hora_evento, _tokens_evento
    return (e.get('fecha', ''), _hora_evento(e) or e.get('hora', ''),
            tuple(sorted(_tokens_evento(e.get('nombre')))), tuple(sorted(_tokens_evento(e.get('lugar')))))


def clasificar_estado(texto):
    """Traduce diagnósticos técnicos a motivos y acciones estables y públicos."""
    from actualizar_eventos import normalizar
    t = normalizar(str(texto))
    t = re.sub(r'\b0 (?:errores|fichas pendientes)\b', '', t)
    if re.search(r'403|429|bloquead|pausa|retry.after', t):
        return 'atencion', 'La fuente limitó el acceso.', 'Se respetan sus pausas. Revisar si se repite.'
    if any(x in t for x in ('desactivad', 'manual', 'falta permiso', 'autorizacion', 'contractual', 'terminos', 'auditoria pendiente')):
        return 'pendiente', 'Falta una revisión de acceso o de condiciones.', 'Revisar la fuente antes de habilitarla.'
    if any(x in t for x in ('timeout', 'no accesible', 'error', 'fall', 'no interpretable', 'cambio el formato')):
        return 'atencion', 'No se pudo completar la lectura.', 'Conservamos datos previos. Si persiste, revisar el extractor.'
    if any(x in t for x in ('pendiente', 'parcial', 'diferido', 'reintentar')):
        return 'pendiente', 'Hay fichas pendientes de revisión.', 'Se reintentan en las próximas actualizaciones cuando corresponda.'
    if any(x in t for x in ('sin eventos', '0 actividades', '0 funciones', 'no publica')):
        return 'sin_novedades', 'No se encontraron actividades nuevas verificables.', 'No hace falta intervenir por este resultado aislado.'
    if any(x in t for x in ('revisad', 'incorporad', 'verificad', 'respaldo', 'resolucion automatica')):
        return 'bien', 'Consulta completada.', 'Sin intervención necesaria.'
    return 'pendiente', 'La fuente no tiene un resultado concluyente.', 'Revisar el detalle en Actions si este estado se mantiene.'


def contar_futuros(eventos, hoy):
    return Counter(e.get('origen') or 'Sin fuente identificada' for e in eventos if e.get('fecha', '') >= hoy)


def informe(root=ROOT, modo='actualizar'):
    from actualizacion_segura import validar
    from actualizar_eventos import sin_repetidos, eventos_duplicados
    datos = validar(leer(root / 'eventos.json'))
    previo = leer(root / 'reportes/respaldo/eventos.json', {'eventos': []})
    resultado = leer(root / 'reportes/resultado_actualizacion.json', {})
    fallo = resultado.get('estado') == 'fallida'
    salud = leer(root / 'salud_actualizacion.json', {}) or {}
    contexto = leer(root / 'reportes/contexto.json', {})
    fecha = ahora()
    hoy = fecha[:10]
    anteriores = [e for e in previo.get('eventos', []) if e.get('fecha', '') >= hoy]
    actuales = [e for e in datos['eventos'] if e.get('fecha', '') >= hoy]
    # No atribuir a esta ejecución los diagnósticos de una ejecución anterior.
    salud_actual = salud if modo == 'actualizar' and not fallo else {}
    conteo_antes, conteo = contar_futuros(anteriores, hoy), contar_futuros(actuales, hoy)
    # Comparación por función deduplicada; evita contar reemplazos de fuente como altas/bajas.
    antes_unicos, ahora_unicos = sin_repetidos(anteriores), sin_repetidos(actuales)
    def novedades(left, right):
        indices = {}
        for e in right:
            indices.setdefault(e['fecha'], []).append(e)
        firmas = {clave(e) for e in right}
        return [e for e in left if clave(e) not in firmas and not any(
            eventos_duplicados(e, other) for other in indices.get(e['fecha'], []))]
    agregados = novedades(ahora_unicos, antes_unicos)
    ausentes = novedades(antes_unicos, ahora_unicos)
    retenidos = Counter(e.get('origen') or 'Sin fuente identificada' for e in actuales if e.get('revision_pendiente'))
    revisiones = salud.get('fuentes', {})
    if not isinstance(revisiones, dict):
        revisiones = {}
    fuentes = []
    alertas = []
    for nombre in sorted(set(conteo) | set(conteo_antes) | set(revisiones)):
        estado, motivo, accion = clasificar_estado(revisiones.get(nombre, 'Sin resultado registrado'))
        antes, despues = conteo_antes[nombre], conteo[nombre]
        caida = antes >= 5 and despues <= antes * .5
        if caida:
            alertas.append({'tipo': 'caida', 'fuente': nombre, 'mensaje': f'Pasó de {antes} a {despues} fichas futuras. Revisar duplicados y cambios de fuente antes de asumir una pérdida.'})
        fuentes.append({'nombre': nombre, 'estado': estado, 'motivo': motivo, 'accion': accion,
                        'eventos': despues, 'antes': antes, 'conservados': retenidos[nombre], 'caida': caida})
    cobertura = leer(root / 'cobertura_actual.json', {})
    if cobertura.get('municipal_del_intento_actual'):
        fallidas = cobertura.get('estados_municipales', {}).get('consulta_fallida', 0)
        if fallidas:
            alertas.append({'tipo': 'cobertura', 'mensaje': f'{fallidas} fichas municipales no se pudieron consultar. Revisar COBERTURA_ACTUAL.md.'})
        if cobertura.get('funciones_extraidas_ausentes'):
            alertas.append({'tipo': 'cobertura', 'mensaje': 'Hay funciones extraídas que no figuran en la agenda ni tienen una coincidencia detectada. Revisar COBERTURA_ACTUAL.md.'})
    for etapa in salud_actual.get('etapas', []):
        if etapa.get('estado') == 'fallida':
            alertas.append({'tipo': 'etapa', 'mensaje': f'Falló la etapa {etapa.get("etapa", "de consulta")}. Se conservaron sus datos anteriores.'})
    if fallo:
        alertas.insert(0, {'tipo': 'actualizacion', 'mensaje': resultado['mensaje']})
    avisos = any(f['estado'] in ('atencion', 'pendiente') for f in fuentes)
    estado = 'error' if fallo else ('atencion' if avisos or alertas or retenidos else 'bien')
    retiradas = leer(root / '.agenda/tareas_retiradas.json', {}) or {}
    auditoria = leer(root / 'reportes/resultado_auditoria.json', {}) or {}
    if retiradas.get('pendientes'):
        alertas.append({'tipo': 'tareas', 'mensaje': 'No se pudieron desactivar todas las tareas antiguas. Consultar el resumen de Actions.'})
        if estado == 'bien': estado = 'atencion'
    ejecucion_id = (os.environ.get('GITHUB_RUN_ID', '') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')) if os.environ.get('GITHUB_RUN_ID') else (contexto.get('inicio') or fecha)
    panel = {'version': 1, 'generado': fecha, 'ejecucion_id': ejecucion_id, 'inicio': contexto.get('inicio'), 'modo': modo,
             'estado': estado, 'datos_actualizados': datos.get('actualizado'),
             'ultima_consulta_fuentes': salud.get('fin') or salud.get('inicio'),
             'fuentes_son_del_intento_actual': bool(salud_actual),
             'resumen': {'eventos': len(actuales), 'funciones_unicas': len(ahora_unicos),
                        'nuevos': len(agregados), 'ausentes': len(ausentes),
                        'duplicados': salud_actual.get('duplicados_unificados', 0),
                        'conservados': sum(retenidos.values()), 'fuentes': len(fuentes)},
             'alertas': alertas, 'fuentes': fuentes,
             'etapas': [{'nombre': e.get('etapa', ''), 'estado': e.get('estado', 'pendiente')}
                        for e in salud_actual.get('etapas', [])],
             'auditoria': auditoria, 'tareas_retiradas': retiradas,
             'ejecucion_url': enlace_ejecucion(),
             'cambios': {'nuevos': [resumen_evento(e) for e in agregados[:40]],
                         'ausentes': [resumen_evento(e) for e in ausentes[:40]]}}
    guardar(root / 'estado_agenda.json', panel)
    historial = leer(root / 'historial_actualizaciones.json', [])
    if not isinstance(historial, list): historial = []
    entrada = {k: panel[k] for k in ('generado', 'ejecucion_id', 'modo', 'estado', 'resumen', 'ejecucion_url')}
    historial = [x for x in historial if x.get('ejecucion_id') != ejecucion_id and x.get('generado') != fecha]
    guardar(root / 'historial_actualizaciones.json', [entrada] + historial[:29])
    lineas = ['# Control de la agenda', '', f"Resultado: **{estado}** · {fecha}", '',
              '| Indicador | Cantidad |', '|---|---:|',
              *[f'| {k} | {v} |' for k, v in panel['resumen'].items()], '',
              'Los cambios comparan funciones futuras de la misma fecha de corte. Las ausencias pueden deberse a bajas confirmadas o reemplazos; no implican automáticamente pérdida.', '',
              '## Avisos', '', *['- ' + a['mensaje'] for a in alertas], '',
              '## Fuentes para revisar', '',
              *[f"- {f['nombre']}: {f['motivo']} {f['accion']}" for f in fuentes if f['estado'] in ('atencion', 'pendiente')]]
    cobertura = leer(root / 'revision_cobertura_municipal.json', {}) or {}
    if modo == 'actualizar' and not fallo and cobertura.get('revision', '') >= (contexto.get('inicio') or fecha):
        lineas += ['', '## Cobertura de la fuente municipal', '',
                   f"Horizonte de consulta: {cobertura.get('horizonte_dias')} días.", '',
                   '| Comprobación | Cantidad |', '|---|---:|',
                   *[f'| {titulo} | {cobertura.get(campo, 0)} |' for campo, titulo in
                     [('fichas_consultadas','Fichas intentadas'), ('fichas_con_error','Consultas fallidas'),
                      ('funciones_extraidas','Funciones extraídas antes de deduplicar'),
                      ('fichas_sin_funciones','Fichas sin funciones extraídas')]], '',
                   'Los motivos de exclusión de cada ficha están en revision_cobertura_municipal.json. '
                   'Cero funciones extraídas no demuestra que la fuente no tenga actividades.']
    (root / 'reportes').mkdir(exist_ok=True)
    (root / 'reportes/resumen.md').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    return panel


def resumen_evento(e):
    return {k: e.get(k, '') for k in ('fecha', 'hora', 'nombre', 'lugar', 'origen')}


def enlace_ejecucion():
    repo, run = os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_RUN_ID', '')
    return f'https://github.com/{repo}/actions/runs/{run}' if re.fullmatch(r'[\w.-]+/[\w.-]+', repo) and run.isdigit() else ''


def auditar(root=ROOT, ejecutar=subprocess.run):
    try:
        ejecutar([sys.executable, 'auditar_fuentes.py', '--salida', 'reportes/auditoria_fuentes.json'],
                 cwd=root, timeout=15*60, check=True)
        resultado = {'estado': 'completada', 'fecha': ahora(), 'mensaje': 'Auditoría de acceso terminada. No habilita fuentes automáticamente.'}
    except (subprocess.SubprocessError, OSError):
        resultado = {'estado': 'fallida', 'fecha': ahora(), 'mensaje': 'No se pudo completar la auditoría. Se mantienen las reglas de acceso.'}
    guardar(root / 'reportes/resultado_auditoria.json', resultado)
    return resultado


def archivar(root=ROOT, ejecutar=subprocess.run):
    """Deshabilitar sólo las tareas reemplazadas. No borrar workflows con el token."""
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError('Repositorio de GitHub inválido')
    completas, pendientes = [], []
    for nombre in VIEJOS:
        ruta = root / '.github/workflows' / nombre
        if not ruta.exists():
            continue
        destino = root / 'archivo/automatizaciones' / (nombre + '.txt')
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and destino.read_bytes() != ruta.read_bytes():
            pendientes.append(nombre)
            continue
        r = ejecutar(['gh', 'api', '--method', 'PUT', f'repos/{repo}/actions/workflows/{nombre}/disable'],
                     cwd=root, capture_output=True, text=True, timeout=30)
        if r.returncode:
            pendientes.append(nombre)
            continue
        shutil.copy2(ruta, destino)
        completas.append(nombre)
    movidos = []
    # Sólo retirar scripts cuando todas las tareas anteriores estén desactivadas.
    if not pendientes:
        for nombre in ARCHIVABLES:
            src = root / nombre
            dst = root / 'archivo/historico' / (nombre + '.txt')
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists() and dst.read_bytes() != src.read_bytes():
                    pendientes.append(nombre)
                    continue
                shutil.copy2(src, dst)
                src.unlink()
                movidos.append(nombre)
    resultado = {'fecha': ahora(), 'desactivadas': completas, 'archivados': movidos, 'pendientes': pendientes}
    guardar(root / '.agenda/tareas_retiradas.json', resultado)
    return resultado


def validar_publicacion(root=ROOT):
    from actualizacion_segura import validar
    datos = validar(leer(root / 'eventos.json'))
    for e in datos['eventos']:
        for field in ('evento_url', 'entradas_url', 'mapa_url'):
            url = e.get(field)
            if url and not str(url).lower().startswith(('https://', 'http://')):
                raise ValueError('Enlace no seguro en una ficha; no se publica.')
    if not datos['eventos']:
        respaldo = leer(root / 'reportes/respaldo/eventos.json', {'eventos': []})
        if any(e.get('fecha', '') >= ahora()[:10] for e in respaldo['eventos']):
            raise ValueError('La agenda quedó vacía con eventos futuros en el respaldo.')
    return datos


def avisar(root=ROOT):
    """Avisos visibles en Actions, sin credenciales ni errores de transporte crudos."""
    panel = leer(root / 'estado_agenda.json', {})
    mensajes = [a['mensaje'] for a in panel.get('alertas', [])]
    mensajes += [f"{f['nombre']}: {f['motivo']}" for f in panel.get('fuentes', [])
                 if f.get('estado') in ('atencion', 'pendiente')]
    for mensaje in list(dict.fromkeys(mensajes))[:30]:
        seguro = mensaje.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::warning title=Revisar fuente de la agenda::'+seguro)
    return len(mensajes)


def guardar_cambios(root=ROOT, ejecutar=subprocess.run):
    """Sólo fast-forward; nunca rebase ni force de resultados antiguos."""
    validar_publicacion(root)
    ejecutar(['git', 'fetch', 'origin', 'main'], cwd=root, check=True)
    def git(*args):
        return ejecutar(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    base, remoto = git('rev-parse', 'HEAD'), git('rev-parse', 'origin/main')
    if base != remoto:
        raise RuntimeError('main cambió durante la ejecución. Se descartan estos resultados; la siguiente ejecución usará la versión nueva.')
    # Enumerar archivos concretos evita que Git intente añadir el directorio
    # reportes ignorado. Incluye archivos nuevos y bajas de archivos rastreados.
    nombres = ejecutar(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                       cwd=root, check=True, capture_output=True, text=True).stdout.split('\0')
    rutas = sorted({name for name in nombres if name
                    and Path(name).parts[0] not in ('.github', 'reportes')
                    and '__pycache__' not in Path(name).parts
                    and not name.endswith(('.pyc', '.pyo'))})
    if rutas:
        ejecutar(['git', '--literal-pathspecs', 'add', '-A', '--pathspec-from-file=-', '--pathspec-file-nul'],
                 cwd=root, check=True, input='\0'.join(rutas) + '\0', text=True)
    diff = ejecutar(['git', 'diff', '--cached', '--quiet'], cwd=root)
    if diff.returncode not in (0, 1):
        raise RuntimeError('No se pudo comprobar el conjunto de cambios.')
    if diff.returncode:
        ejecutar(['git', '-c', 'user.name=agenda-bot', '-c', 'user.email=actions@users.noreply.github.com',
                  'commit', '-m', 'Actualizar agenda coordinada: datos, diagnóstico y entrega validada'], cwd=root, check=True)
        ejecutar(['git', 'push', 'origin', 'HEAD:main'], cwd=root, check=True)
    return git('rev-parse', 'HEAD')


def publicar(root=ROOT, ejecutar=subprocess.run, esperar=None):
    import time
    esperar = esperar or time.sleep
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError('Repositorio inválido')
    def cmd(args):
        return ejecutar(args, cwd=root, check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    head = cmd(['git', 'rev-parse', 'HEAD'])
    cmd(['git', 'fetch', 'origin', 'main'])
    if head != cmd(['git', 'rev-parse', 'origin/main']):
        raise RuntimeError('Hay una versión nueva en main. No se solicita publicar resultados antiguos.')
    cmd(['gh', 'api', '--method', 'POST', f'repos/{repo}/pages/builds'])
    for _ in range(24):
        build = json.loads(cmd(['gh', 'api', f'repos/{repo}/pages/builds/latest']))
        if build.get('commit') == head:
            if build.get('status') == 'built':
                guardar(root / 'reportes/publicacion.json', {'estado': 'confirmada', 'commit': head, 'fecha': ahora()})
                return
            if build.get('status') == 'errored':
                raise RuntimeError('GitHub Pages no pudo publicar. Revisar la ejecución de Pages; los archivos validados están guardados.')
        esperar(10)
    raise RuntimeError('Publicación solicitada, pero GitHub Pages no confirmó el resultado dentro del plazo. Revisar Pages antes de afirmar que está publicado.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('accion', choices=['preparar', 'actualizar', 'auditar', 'archivar', 'informe', 'validar', 'avisar', 'guardar', 'publicar'])
    parser.add_argument('--modo', default='actualizar', choices=['actualizar', 'verificar', 'auditar'])
    args = parser.parse_args()
    if args.accion == 'informe': informe(modo=args.modo)
    elif args.accion == 'validar': validar_publicacion()
    elif args.accion == 'guardar': print(guardar_cambios())
    else: globals()[args.accion]()


if __name__ == '__main__':
    main()

