"""Instala reglas de horarios pendientes y publicación de Jaguar sin sobrescribir otras funciones."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
js=ROOT/'agenda.js'; txt=js.read_text(encoding='utf8')
if 'function horaPendiente(' not in txt:
    anchor='function horarioEvento(item) {'
    assert txt.count(anchor)==1, 'No se encontró función horarioEvento única'
    txt=txt.replace(anchor,'''function horaPendiente(item) {
  return !/^\\d{1,2}:\\d{2}/.test(String(item.hora || "").trim());
}

'''+anchor)
    txt=txt.replace('  const inicio = String(item.hora || "").trim();\n  const finDirecto', '  const inicio = String(item.hora || "").trim();\n  if (horaPendiente(item)) return "Horario a confirmar";\n  const finDirecto',1)
    txt=txt.replace('    .sort((a, b) => a.hora.localeCompare(b.hora));', '    .sort((a, b) => Number(horaPendiente(b)) - Number(horaPendiente(a)) || a.hora.localeCompare(b.hora));',1)
    txt=txt.replace('  const ended = item.fecha_fin && item.hora_fin;', '  if (horaPendiente(item)) return item.fecha >= todayKey();\n  const ended = item.fecha_fin && item.hora_fin;',1)
    js.write_text(txt,encoding='utf8')
py=ROOT/'fuentes_nuevas.py';txt=py.read_text(encoding='utf8')
mark='# Publicación de Jaguar Haüs con horario a confirmar'
if mark not in txt:
    anchor='    nombre, url = CARTELERA\n'
    assert txt.count(anchor)==1, 'No se encontró integración de cartelera única'
    insertion='''    '''+mark+'''
    try:
        from fuente_jaguar import ejecutar as consultar_jaguar, CANDIDATOS as archivo_jaguar
        reporte_jaguar = consultar_jaguar(hoy=hoy)
        pendientes_jaguar = []
        if archivo_jaguar.exists():
            pendientes_jaguar = json.loads(archivo_jaguar.read_text(encoding='utf-8')).get('candidatos', [])
        for candidato in pendientes_jaguar:
            if candidato.get('fecha', '') < hoy.isoformat():
                continue
            if not candidato.get('nombre') or not candidato.get('evento_url'):
                continue
            nuevos.append({
                'fecha': candidato['fecha'], 'hora': 'Horario a confirmar',
                'nombre': candidato['nombre'], 'lugar': 'Jaguar Haüs',
                'direccion': 'Rodríguez 198 bis, Rosario, Santa Fe',
                'descripcion': 'Evento anunciado por Jaguar Haüs; horario todavía no publicado.',
                'evento_url': candidato['evento_url'], 'precio': None,
                'precio_etiqueta': 'Consultar precio en el enlace oficial',
                'origen': 'Jaguar Haüs', 'horario_pendiente': True,
            })
        estado['Jaguar Haüs'] = reporte_jaguar['estado'] + ': ' + str(len(pendientes_jaguar)) + ' anuncios'
    except (OSError, ValueError, requests.RequestException) as error:
        estado['Jaguar Haüs'] = 'pendiente: ' + type(error).__name__
'''
    txt=txt.replace(anchor,insertion+anchor)
    py.write_text(txt,encoding='utf8')
print('Reglas de horario pendiente y Jaguar instaladas. Ejecutar actualización segura.')
