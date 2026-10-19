"""Fichas públicas de Passline descubiertas desde carteleras de salas.

Sólo hechos y enlaces. El acceso, caché y pausas pertenecen a ConsultaAmpliada.
"""
import json
import re
from datetime import date
from bs4 import BeautifulSoup
from fuentes_refi_folklore import schemas, instante, norm, categorias_factuales

FORMACION = re.compile(r'\b(curso|cursos|taller|talleres|capacitacion|formacion|seminario|masterclass|workshop|clase|clases)\b')
MESES = {m:i for i,m in enumerate(('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'),1)}


def ficha_passline(contenido, url, fuente):
    sopa = BeautifulSoup(contenido, 'html.parser')
    titulo = sopa.select_one('h1.titulo_evento')
    if not titulo:
        raise ValueError('Ficha Passline sin título principal')
    nombre = re.sub(r'\s*\(\+\d+\)\s*$', '', titulo.get_text(' ', strip=True)).strip()
    if FORMACION.search(norm(nombre)):
        return []
    # Passline usa a veces el nombre del bar en addressLocality. La localidad
    # se corrobora en el bloque visible propio de la ficha, nunca en el título.
    bloques = [p for p in sopa.select('p') if p.select_one('strong') and
               re.search(r'\bSanta Fe,\s*Rosario\s*$', p.get_text(' ', strip=True), re.I)]
    objetos = []
    for tag in sopa.select('script[type="application/ld+json"]'):
        try:
            objetos.extend(schemas(json.loads(tag.get_text())))
        except (ValueError, TypeError):
            continue
    # Algunas fichas reales tienen un script JSON-LD vacío. En ese caso se
    # admiten sólo los campos visibles propios con URL canónica coincidente.
    if not objetos:
        canonica = sopa.select_one('meta[property="og:url"]')
        fecha_visible = sopa.select_one('#primer_contenedor #li_fecha_inicio')
        m = re.search(r'\b(\d{1,2}) de (\w+) (\d{4})(?:\s*-\s*(\d{1,2}):(\d{2}))?',
                      norm(fecha_visible.get_text(' ',strip=True)) if fecha_visible else '')
        if canonica and canonica.get('content','').rstrip('/') == url.rstrip('/') and m and bloques:
            d,mes,anio,hh,mm=m.groups()
            dia=date(int(anio),MESES[mes],int(d)).isoformat()
            bloque=bloques[0]
            partes=list(bloque.stripped_strings)
            objetos=[{'name':nombre,'url':url,'startDate':dia+(f'T{int(hh):02d}:{mm}:00-03:00' if hh else ''),
                      'location':{'name':bloque.select_one('strong').get_text(' ',strip=True),
                                  'address':{'addressLocality':'Rosario','addressRegion':'Santa Fe',
                                             'streetAddress':' '.join(partes[1:-1])}}}]
    propios = []
    for e in objetos:
        oferta = e.get('offers', {})
        referencia = e.get('url') or (oferta.get('url') if isinstance(oferta, dict) else '')
        if referencia and referencia.rstrip('/') == url.rstrip('/') and norm(e.get('name')) == norm(nombre):
            propios.append(e)
    if not propios:
        raise ValueError('Sin datos estructurados correspondientes a esta ficha')
    salida = []
    for e in propios:
        if any(s in str(e.get('eventStatus', '')) for s in ('Cancelled', 'Postponed', 'Rescheduled')):
            salida.append({'cancelado': True})
            continue
        loc = e.get('location', {})
        domicilio = loc.get('address', {}) if isinstance(loc, dict) else {}
        if not isinstance(domicilio, dict):
            raise ValueError('Domicilio sin estructura')
        sede = loc.get('name', '')
        if norm(sede) != norm(fuente['sede']):
            raise ValueError('La ficha no pertenece a la sala consultada')
        region, ciudad = norm(domicilio.get('addressRegion', '')), norm(domicilio.get('addressLocality', ''))
        if region and region not in ('santa fe', 'santa fe province'):
            raise ValueError('Provincia distinta de Santa Fe')
        visible = any(norm(p.select_one('strong').get_text(' ', strip=True)) == norm(sede) for p in bloques)
        if not (ciudad == 'rosario' or visible):
            raise ValueError('Localidad Rosario no verificada')
        valor = e.get('startDate', '')
        if 'T' in valor:
            inicio = instante(valor)
            fecha, hora = inicio.date().isoformat(), inicio.strftime('%H:%M')
        else:
            fecha, hora = date.fromisoformat(valor).isoformat(), 'Horario a confirmar'
        resultado = {'cancelado': False, 'nombre': nombre, 'fecha': fecha, 'hora': hora,
                     'lugar': sede, 'direccion': domicilio.get('streetAddress', ''),
                     'precio': None, 'precio_etiqueta': 'Consultar precio actualizado en Passline',
                     'entradas_url': url,
                     'categorias': categorias_factuales(nombre, '', e.get('@type', ''))}
        # No inferir duración del endDate: Passline suele asignar finales
        # técnicos a sus fichas. Tampoco convertir lotes promocionales en gratis.
        restriccion = re.search(r'Evento solo para Mayores de\s*(\d+)\s*Años', sopa.get_text(' ', strip=True), re.I)
        if restriccion:
            resultado['descripcion'] = 'Evento para mayores de ' + restriccion.group(1) + ' años. Consultar condiciones de ingreso en Passline.'
        salida.append(resultado)
    return salida
