"""Fuentes públicas adicionales; sólo datos factuales, caché y acceso auditado.

No ejecuta JavaScript ni consulta APIs privadas. Cada ficha se valida por separado.
Los medios generan candidatos, nunca publicaciones automáticas.
"""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from fuentes_adicionales import norm
from fuentes_refi_folklore import (Consulta, ZONA, guardar, enlace_local, schemas,
                                  instante, misma_funcion, categorias_factuales)

ROOT = Path(__file__).resolve().parent
CONFIG = 'fuentes_ampliadas.json'
CACHE = 'cache_fuentes_ampliadas.json'


class ConsultaAmpliada(Consulta):
    def robots(self, url):
        demora = super().robots(url)
        # Algunos robots agregan comentarios al valor de Crawl-delay.
        from urllib.parse import urljoin
        reglas = self.cache.get('robots', {}).get(urljoin(url, '/robots.txt'), {}).get('reglas', '')
        valores = re.findall(r'^Crawl-delay:\s*(\d+)\s*(?:#.*)?$', reglas, re.M | re.I)
        return max([demora] + [int(v) for v in valores])


def listado(contenido, url, fuente):
    sopa = BeautifulSoup(contenido, 'html.parser')
    enlaces = []
    for a in sopa.select(fuente.get('selector', 'a[href]')):
        try:
            link = enlace_local(url, a.get('href', ''))
        except ValueError:
            continue
        if re.search(fuente['patron_ficha'], urlsplit(link).path):
            enlaces.append({'url': link, 'referencia': ''})
    enlaces = list({e['url']: e for e in enlaces}.values())
    if not enlaces:
        raise ValueError('Sin fichas interpretables: cambio de estructura o catálogo vacío; conservar anteriores')
    if len(enlaces) > 500:
        raise ValueError('Listado demasiado grande: requiere revisión')
    return enlaces


def ubicacion(sopa, evento, fuente):
    loc = evento.get('location', {})
    loc = loc if isinstance(loc, dict) else {}
    direccion = loc.get('address', {})
    direccion = direccion if isinstance(direccion, dict) else {}
    ciudad = direccion.get('addressLocality', '')
    sede, calle = loc.get('name', ''), direccion.get('streetAddress', '')
    # La agenda provincial publica la ubicación visible fuera de su JSON-LD.
    if fuente['adaptador'] == 'santafe':
        for titulo in sopa.select('h4.block__title'):
            if norm(titulo.get_text(' ', strip=True)) == '¿donde?':
                valores = [li.get_text(' ', strip=True) for li in titulo.parent.select('ul.text-list li')]
                if len(valores) >= 3:
                    sede, calle, ciudad = valores[0], valores[1], valores[2].split(',')[0].strip()
                break
    if norm(ciudad) != 'rosario' or not isinstance(sede, str) or not sede.strip():
        raise ValueError('Localidad Rosario y sede no verificables en la ficha')
    return sede.strip(), calle


def ficha(contenido, url, fuente):
    sopa = BeautifulSoup(contenido, 'html.parser')
    propios = []
    for script in sopa.select('script[type="application/ld+json"]'):
        try:
            objetos = list(schemas(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
        for e in objetos:
            # No importar recomendaciones de otras fichas ni funciones enlazadas.
            try:
                identificador = enlace_local(url, e.get('url') or url)
            except (ValueError, TypeError):
                continue
            if identificador.rstrip('/') == url.rstrip('/'):
                propios.append(e)
    if not propios:
        raise ValueError('Ficha sin eventos estructurados: pendiente de adaptación')
    resultado = []
    for e in propios:
        estado = str(e.get('eventStatus', ''))
        if any(x in estado for x in ('Cancelled', 'Postponed', 'Rescheduled')):
            resultado.append({'cancelado': True})
            continue
        inicio = instante(e.get('startDate'))
        nombre = e.get('name')
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError('Evento sin nombre')
        sede, calle = ubicacion(sopa, e, fuente)
        fin = instante(e['endDate']) if e.get('endDate') else None
        if fin is not None and (fin.replace(tzinfo=None) < inicio.replace(tzinfo=None)):
            raise ValueError('Fin anterior al inicio')
        resultado.append({'cancelado': False, 'fecha': inicio.date().isoformat(),
                          'hora': inicio.strftime('%H:%M'), 'nombre': nombre.strip(),
                          'lugar': sede, 'direccion': calle,
                          'categorias': categorias_factuales(nombre, '', e.get('@type', '')),
                          **({'fecha_fin': fin.date().isoformat(), 'hora_fin': fin.strftime('%H:%M')} if fin else {})})
    return resultado


def fusionar(anteriores, nuevos, revisadas, hoy):
    # Sólo reemplazar URLs leídas con éxito; nunca vaciar una fuente por error.
    salida = [e for e in anteriores if (e.get('origen'), e.get('evento_url')) not in revisadas]
    for e in nuevos:
        coincidencias = [p for p in salida if misma_funcion(e, p)]
        if not coincidencias:
            salida.append(e)
        elif all(p.get('origen') == 'Agenda Cultural Rosario' for p in coincidencias):
            salida = [p for p in salida if p not in coincidencias]
            salida.append(e)
    return sorted(salida, key=lambda e: (e['fecha'], e['hora'], e['nombre']))


def revisar(config, acceso, hoy):
    nuevos, candidatos, estados, revisadas = [], [], {}, set()
    hasta = hoy + timedelta(days=int(config.get('dias_futuros', 180)))
    for fuente in config['fuentes']:
        nombre = fuente['nombre']
        if not fuente.get('habilitada'):
            estados[nombre] = {'estado': 'pendiente', 'motivo': fuente['motivo'], 'publicadas': 0}
            continue
        ventana = fuente.get('ventana_utc')
        if ventana and not ventana[0] <= datetime.now(timezone.utc).hour < ventana[1]:
            estados[nombre] = {'estado': 'fuera de horario', 'motivo': 'Consulta semanal dentro de ventana UTC 03:00–12:00; respeta robots', 'publicadas': 0}
            continue
        try:
            filas = acceso.leer_datos(fuente['listado'], lambda h, u: listado(h, u, fuente),
                                     horas=fuente.get('cache_horas', 2))
            if fuente['tipo'] == 'descubrimiento':
                candidatos.extend({'fuente': nombre, 'url': e['url'],
                                   'estado': 'requiere fuente oficial y fecha completa'} for e in filas)
                estados[nombre] = {'estado': 'descubrimiento', 'candidatos': len(filas),
                                  'motivo': 'No publica artículos como eventos'}
                continue
            # Recorrer primero fichas no leídas o con caché más antigua.
            paginas = acceso.cache.get('paginas', {})
            filas.sort(key=lambda e: paginas.get(e['url'], {}).get('consultado', 0))
            pendientes, cantidad, errores = 0, 0, []
            for fila in filas[:int(config.get('max_fichas_por_fuente', 4))]:
                url = fila['url']
                try:
                    eventos = acceso.leer_datos(url, lambda h, u: ficha(h, u, fuente), horas=24)
                    revisadas.add((nombre, url))
                    for e in eventos:
                        if e.get('cancelado') or not hoy.isoformat() <= e['fecha'] <= hasta.isoformat():
                            continue
                        nuevos.append({**e, 'evento_url': url, 'origen': nombre,
                                       'descripcion': '', 'precio': None,
                                       'precio_etiqueta': 'Consultar precio en la fuente',
                                       'fuente_verificada': True})
                        cantidad += 1
                except (requests.RequestException, ValueError, TypeError, KeyError) as error:
                    pendientes += 1
                    errores.append({'url': url, 'motivo': str(error)})
            estados[nombre] = {'estado': 'parcial' if pendientes else 'revisada',
                              'publicadas': cantidad, 'fichas_en_listado': len(filas),
                              'fichas_pendientes': pendientes, 'errores': errores,
                              'diferidas_por_limite': max(0, len(filas)-int(config.get('max_fichas_por_fuente', 4)))}
        except (requests.RequestException, ValueError, TypeError, KeyError) as error:
            estados[nombre] = {'estado': 'no accesible', 'motivo': str(error), 'publicadas': 0}
    return nuevos, candidatos, estados, revisadas


def actualizar(root=ROOT, acceso=None, hoy=None):
    root = Path(root)
    ahora = datetime.now(ZONA)
    hoy = hoy or ahora.date()
    config = json.loads((root / CONFIG).read_text(encoding='utf-8'))
    cache_path = root / CACHE
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    acceso = acceso or ConsultaAmpliada(cache)
    datos = json.loads((root / 'eventos.json').read_text(encoding='utf-8'))
    nuevos, candidatos, estados, revisadas = revisar(config, acceso, hoy)
    datos['eventos'] = fusionar(datos['eventos'], nuevos, revisadas, hoy)
    datos['revision_ampliadas'] = {'id': uuid.uuid4().hex,
                                  'fichas_revisadas': [list(k) for k in sorted(revisadas)]}
    if any(e['estado'] in ('parcial', 'no accesible') for e in estados.values()):
        datos['estado'] = 'parcial'
    guardar(root / 'eventos.json', datos)
    guardar(cache_path, acceso.cache)
    guardar(root / 'candidatos_fuentes_ampliadas.json', {'revision': ahora.isoformat(), 'candidatos': candidatos})
    guardar(root / 'revision_fuentes_ampliadas.json', {'revision': ahora.isoformat(), 'fuentes': estados})
    registro_path = root / 'fuentes_revisadas.json'
    registro = json.loads(registro_path.read_text(encoding='utf-8')) if registro_path.exists() else {}
    registro.setdefault('fuentes', {}).update({n: f"{e['estado']}: {e.get('motivo', str(e.get('publicadas', 0)) + ' funciones')}" for n, e in estados.items()})
    guardar(registro_path, registro)
    for nombre, estado in estados.items():
        print(nombre, json.dumps(estado, ensure_ascii=False), flush=True)
    return estados


if __name__ == '__main__':
    actualizar()
