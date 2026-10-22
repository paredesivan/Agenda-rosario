"""Directorio ACR y fuentes primarias revisadas. No contiene eventos fijos."""
import hashlib
import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from fuentes_ampliadas import ConsultaAmpliada
from fuentes_refi_folklore import ZONA, norm, schemas, instante, misma_funcion, guardar

ROOT = Path(__file__).resolve().parent
DIRECTORIO = 'https://www.agendaculturalrosario.com.ar/espacios'
FORMACION = re.compile(r'\b(cursos?|taller(?:es)?|seminarios?|capacitacion|formacion|clases?|inscripcion(?:es)?|workshops?)\b')


def legal(contenido, url=''):
    sopa = BeautifulSoup(contenido, 'html.parser')
    for n in sopa.select('script, style, header, footer, nav'):
        n.decompose()
    return hashlib.sha256(norm((sopa.select_one('main') or sopa).get_text(' ', strip=True)).encode()).hexdigest()


def mismo_host(url, base):
    p, b = urlsplit(url), urlsplit(base)
    return p.scheme == 'https' and p.hostname == b.hostname and not p.username and not p.password


def directorio(contenido, url=DIRECTORIO):
    sopa = BeautifulSoup(contenido, 'html.parser')
    filas = {}
    for a in sopa.select('h2 a[href]'):
        enlace = urljoin(url, a['href']).split('#')[0]
        if not mismo_host(enlace, DIRECTORIO) or not re.fullmatch(r'/espacios/[a-z0-9-]+/?', urlsplit(enlace).path):
            continue
        nombre = a.get_text(' ', strip=True)
        if nombre:
            filas[enlace.rstrip('/')] = {'nombre': nombre, 'directorio': enlace.rstrip('/')}
    if not filas:
        raise ValueError('Directorio sin espacios interpretables; conservar inventario anterior')
    return list(filas.values())


def listado_aserradero(contenido, url):
    sopa = BeautifulSoup(contenido, 'html.parser')
    if 'aserradero' not in norm(sopa.title.get_text() if sopa.title else ''):
        raise ValueError('La portada no identifica El Aserradero')
    enlaces = []
    for a in sopa.select('a[href]'):
        enlace = urljoin(url, a['href']).split('#')[0]
        if mismo_host(enlace, url) and re.fullmatch(r'/event/[^/]+/?', urlsplit(enlace).path):
            enlaces.append(enlace)
    if not enlaces:
        raise ValueError('Cartelera vacía o cambió HTML; se conservan eventos anteriores')
    return list(dict.fromkeys(enlaces))


def ficha_aserradero(contenido, url):
    sopa = BeautifulSoup(contenido, 'html.parser')
    resultado = []
    for s in sopa.select('script[type="application/ld+json"]'):
        try:
            objetos = list(schemas(json.loads(s.get_text())))
        except (ValueError, TypeError):
            continue
        for e in objetos:
            oferta = e.get('offers', {})
            oferta = oferta if isinstance(oferta, dict) else {}
            propio = e.get('url') or oferta.get('url')
            if not propio or propio.rstrip('/') != url.rstrip('/'):
                continue
            if any(v in str(e.get('eventStatus', '')) for v in ('Cancelled', 'Postponed', 'Rescheduled')):
                continue
            titulo = e.get('name', '')
            if not isinstance(titulo, str) or not titulo.strip():
                continue
            # El contenido se inspecciona sólo para excluir formación; no se copia.
            if FORMACION.search(norm(titulo + ' ' + str(e.get('description', '')))):
                continue
            loc = e.get('location', {})
            if not isinstance(loc, dict) or norm(loc.get('name', '')) != 'el aserradero':
                continue
            direccion = loc.get('address', {})
            direccion = direccion if isinstance(direccion, dict) else {}
            calle = direccion.get('streetAddress', '')
            ciudad = direccion.get('addressLocality', '')
            # El HTML real publica la localidad dentro de streetAddress.
            if not isinstance(calle, str) or not re.search(r'\bmontevideo\s+1518\b', norm(calle)):
                continue
            if norm(ciudad) != 'rosario' and not re.search(r'\brosario\b', norm(calle)):
                continue
            raw = e.get('startDate', '')
            try:
                dia = date.fromisoformat(raw) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(raw)) else instante(raw).date()
                hora = 'Horario a confirmar' if len(raw) == 10 else instante(raw).strftime('%H:%M')
            except (ValueError, TypeError, OverflowError):
                continue
            evento = {'fecha': dia.isoformat(), 'hora': hora, 'nombre': titulo.strip(),
                      'lugar': 'El Aserradero', 'direccion': calle, 'descripcion': '',
                      'evento_url': url, 'entradas_url': url, 'origen': 'El Aserradero — oficial',
                      'precio': None, 'precio_etiqueta': 'Consultar precio final en la boletería oficial',
                      'fuente_verificada': True, 'horario_pendiente': hora == 'Horario a confirmar',
                      'mapa_url': 'https://www.google.com/maps/search/?api=1&query=Montevideo+1518+Rosario'}
            if e.get('endDate'):
                try:
                    fin = instante(e['endDate'])
                    if len(raw) > 10 and fin >= instante(raw):
                        evento.update(fecha_fin=fin.date().isoformat(), hora_fin=fin.strftime('%H:%M'))
                except (ValueError, TypeError, OverflowError):
                    pass
            resultado.append(evento)
    if not resultado:
        raise ValueError('Ficha sin función pública verificable: fecha, sala, localidad, formación o estado')
    return resultado


def combinar(anteriores, nuevos):
    """Reemplazar respaldo secundario sólo con la misma función oficial."""
    salida = list(anteriores)
    for e in nuevos:
        coincidencias = [p for p in salida if misma_funcion(e, p)]
        # No borrar por URL revisada ni por ausencias en el catálogo.
        primarios = [p for p in coincidencias if p.get('origen') not in
                     ('Agenda Cultural Rosario', 'Rosario en Cartel', 'El Aserradero — oficial')]
        if primarios:
            continue
        salida = [p for p in salida if p not in coincidencias]
        salida.append(e)
    return sorted(salida, key=lambda e: (e['fecha'], e['hora'], e['nombre']))


def tabla(filas, fecha):
    partes = ['<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
              '<title>Espacios y fuentes oficiales — Salidas Rosario</title>',
              '<style>body{font:16px system-ui;max-width:950px;margin:auto;padding:20px;background:#f4f6f8;color:#182432}article{background:white;padding:18px;margin:12px 0;border-radius:12px}a{color:#1459aa;overflow-wrap:anywhere}p{line-height:1.5}</style>',
              '<h1>Espacios y fuentes oficiales</h1>',
              '<p>Directorio de referencia: <a href="'+DIRECTORIO+'">Agenda Cultural Rosario</a>. Revisión: '+html.escape(fecha)+'. Un enlace institucional no garantiza una cartelera automática completa.</p>']
    for f in filas:
        partes.append('<article><h2>'+html.escape(f['nombre'])+'</h2><p>'+html.escape(f['estado'])+'</p>')
        for clave, etiqueta in [('sitio', 'Sitio institucional'), ('cartelera', 'Cartelera'), ('red', 'Red publicada por la institución'), ('referencia_acr', 'Referencia ACR sin corroborar')]:
            url = f.get(clave, '')
            if url.startswith('https://'):
                partes.append('<p>'+etiqueta+': <a rel="noopener noreferrer" href="'+html.escape(url, quote=True)+'">'+html.escape(url)+'</a></p>')
        partes.append('</article>')
    return ''.join(partes)+'</html>'


def actualizar(root=ROOT, acceso=None, hoy=None):
    root = Path(root)
    hoy = hoy or datetime.now(ZONA).date()
    config = json.loads((root / 'espacios_oficiales.json').read_text(encoding='utf-8'))
    cache_path = root / 'cache_espacios_oficiales.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    acceso = acceso or ConsultaAmpliada(cache)
    cache = acceso.cache
    filas = [dict(f) for f in config['espacios']]
    avisos = []
    try:
        digest = acceso.leer_datos(config['directorio_terminos'], legal, horas=24)
        if digest != config['directorio_terminos_sha256']:
            raise ValueError('Cambió el texto de condiciones del directorio; requiere revisión')
        descubiertas = acceso.leer_datos(DIRECTORIO, directorio, horas=24)
        conocidas = {f['directorio'].rstrip('/') for f in filas}
        for f in descubiertas:
            if f['directorio'] not in conocidas:
                filas.append({**f, 'estado': 'Espacio nuevo: sitio oficial pendiente de corroboración; consulta externa no activada.'})
        # No eliminar espacios por fallos, truncamiento o bajas del directorio.
        prev = root / 'revision_espacios_oficiales.json'
        if prev.exists():
            ya = {f['directorio'].rstrip('/') for f in filas}
            filas.extend(f for f in json.loads(prev.read_text()).get('espacios', []) if f['directorio'].rstrip('/') not in ya)
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        avisos.append('Directorio: '+str(exc)[:220])
        prev = root / 'revision_espacios_oficiales.json'
        if prev.exists():
            ya = {f['directorio'].rstrip('/') for f in filas}
            filas.extend(f for f in json.loads(prev.read_text()).get('espacios', []) if f['directorio'].rstrip('/') not in ya)
    nuevos = []
    fuente = config['aserradero']
    nombre = 'El Aserradero — oficial'
    estado = 'pendiente'
    try:
        digest = acceso.leer_datos(fuente['terminos'], legal, horas=24)
        if digest != fuente['terminos_sha256']:
            raise ValueError('Cambió el texto de condiciones; revisión pendiente')
        enlaces = acceso.leer_datos(fuente['listado'], listado_aserradero, horas=2)
        # Rotación persistente: nunca quedarse para siempre en las primeras fichas.
        paginas = cache.setdefault('paginas', {})
        enlaces.sort(key=lambda u: (paginas.get(u, {}).get('consultado', 0), u))
        errores = []
        cuotas = cache.setdefault('cuotas_aserradero', {})
        cuotas = {k:v for k,v in cuotas.items() if k == hoy.isoformat()}
        cache['cuotas_aserradero'] = cuotas
        usadas = cuotas.setdefault(hoy.isoformat(), [])
        for url in enlaces:
            previa = paginas.get(url, {})
            vigente = acceso.reloj() - previa.get('consultado', 0) < 86400
            if not vigente:
                if url in usadas or len(usadas) >= 8:
                    continue
                usadas.append(url)
            try:
                eventos = acceso.leer_datos(url, ficha_aserradero, horas=24)
                nuevos.extend(e for e in eventos if hoy.isoformat() <= e['fecha'] <= (hoy+timedelta(days=180)).isoformat())
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                errores.append({'url': url, 'motivo': str(exc)[:200]})
        estado = f'revisada: {len(nuevos)} funciones oficiales; {len(errores)} fichas pendientes'
        if errores:
            avisos.extend(e['motivo'] for e in errores)
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        estado = 'no accesible: '+str(exc)[:200]
        avisos.append(estado)
    for fila in filas:
        if fila.get('cartelera') == fuente['listado']:
            fila['estado'] = estado + '. Precio final en boletería oficial.'
    datos_path = root / 'eventos.json'
    datos = json.loads(datos_path.read_text(encoding='utf-8'))
    datos['eventos'] = combinar(datos['eventos'], nuevos)
    guardar(datos_path, datos)
    registro_path = root / 'fuentes_revisadas.json'
    registro = json.loads(registro_path.read_text()) if registro_path.exists() else {}
    registro.setdefault('fuentes', {})[nombre] = estado
    registro['fuentes']['Directorio de espacios — fuentes oficiales'] = f'{len(filas)} espacios registrados; {len(avisos)} avisos. Ver espacios.html.'
    guardar(registro_path, registro)
    guardar(cache_path, cache)
    guardar(root / 'revision_espacios_oficiales.json', {'revision': datetime.now(ZONA).isoformat(), 'espacios': filas, 'aserradero': estado, 'avisos': avisos})
    (root / 'espacios.html').write_text(tabla(filas, hoy.isoformat()), encoding='utf-8')
    print(estado, flush=True)
    return {'espacios': filas, 'nuevos': nuevos, 'avisos': avisos}


if __name__ == '__main__':
    actualizar()
