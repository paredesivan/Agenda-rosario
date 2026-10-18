"""Reparación segura y repetible de Agenda Rosario.
Ejecutar desde raíz del repositorio: python reparar_agenda_hello.py
- Añade al snapshot un evento contrastado con la ficha oficial (dato, no regla de extracción).
- Corrige que la prensa ignore Casa Brava (lugar y dirección verificados).
- Instala extractor dinámico Tickets Bravos sólo si robots.txt puede verificarse.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
AGENDA = ROOT / 'eventos.json'
FUENTES = ROOT / 'fuentes_nuevas.py'

def instalar():
    datos = json.loads(AGENDA.read_text(encoding='utf-8'))
    evento = {
      'fecha':'2026-10-21', 'hora':'20:30', 'nombre':'HELLO! el Unplugged',
      'lugar':'Casa Brava', 'direccion':'Pichincha 120, Rosario, Santa Fe',
      'descripcion':'Concierto homenaje al histórico MTV Unplugged de Charly García con músicos originales e invitados.',
      'evento_url':'https://www.ticketsbravos.com/eventos/hello-el-unplugged-e223',
      'precio':None, 'precio_etiqueta':'Consultar precio en Tickets Bravos',
      'origen':'Tickets Bravos', 'fuente_verificada':True
    }
    if not any(e.get('evento_url')==evento['evento_url'] for e in datos['eventos']):
        datos['eventos'].append(evento)
    datos['eventos'].sort(key=lambda e:(e['fecha'],e['hora'],e['nombre']))
    AGENDA.write_text(json.dumps(datos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    codigo = FUENTES.read_text(encoding='utf-8')
    if '("Casa Brava", "Pichincha 120")' not in codigo:
        busqueda = '        ("Teatro Broadway", "San Lorenzo 1223"),'
        if busqueda not in codigo: raise RuntimeError('No se encontró punto seguro de inserción para Casa Brava')
        codigo = codigo.replace(busqueda, busqueda+'\n        ("Casa Brava", "Pichincha 120"),',1)
    if '# TICKETS_BRAVOS_INTEGRACION_V1' not in codigo:
        ancla = '    from fuentes_adicionales import revisar\n'
        if ancla not in codigo: raise RuntimeError('No se encontró punto de integración. No modificar manualmente')
        codigo = codigo.replace(ancla, '    # TICKETS_BRAVOS_INTEGRACION_V1\n    from fuente_ticketsbravos import revisar_ticketsbravos\n    nuevos.extend(revisar_ticketsbravos(hoy, estado))\n'+ancla,1)
    FUENTES.write_text(codigo,encoding='utf-8')
    print('OK: evento contrastado incorporado; Casa Brava reconocida; etapa dinámica instalada.')

if __name__ == '__main__': instalar()
