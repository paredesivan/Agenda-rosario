"""Completa funciones oficiales con hechos del listado público de la boletería.

Un listado cada dos horas; robots semanal, caché condicional y pausas 403/429
mediante Acceso. No consulta compra, usuarios, imágenes ni APIs privadas.
"""
import json
import re
import requests
from control_http import SesionControlada
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from fuentes_adicionales import Acceso, guardar, host, norm, LIMITES

ROOT = Path(__file__).resolve().parent
URL = 'https://entradaslavarden.com/?categoria=ESPECT%C3%81CULOS'


class SesionLavarden(SesionControlada):
    def get(self, url, **kwargs):
        # Algunas fichas tardan más en establecer la conexión. Sin reintentos.
        kwargs['timeout'] = (30, 30)
        return super().get(url, **kwargs)


def titulo(value):
    return ' '.join(re.sub(r'[^\w\s]', ' ', norm(value)).split())


def listado(html, url):
    tarjetas = html.select('[id="boxEvent"]')
    if not tarjetas:
        raise ValueError('Cambió el formato del listado Lavardén')
    salida = []
    for card in tarjetas[:40]:
        texto = card.get_text(' ', strip=True)
        nombre = card.select_one('.card-title')
        sede = card.select_one('.address')
        compra = card.select_one('a.buy-button[href]')
        fecha = re.search(r'\b(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2})\b', texto)
        precio = re.search(r'\bDesde\s+ARS\s+([\d.,]+)\b', texto)
        if not all((nombre, sede, compra, fecha, precio)):
            continue
        if not re.search(r'\brosario\b', norm(sede.get_text(' ', strip=True))):
            continue
        if re.search(r'cancelad|suspendid|reprogramad|agotad|venta finalizada', norm(texto)):
            continue
        enlace = urljoin(url, compra['href'].strip())
        if host(enlace) != 'entradaslavarden.com' or not enlace.startswith('https://'):
            continue
        try:
            momento = datetime.strptime(fecha[0], '%d/%m/%Y, %H:%M')
            # El listado usa enteros ARS; no interpretar separadores ambiguos.
            if not precio[1].isdigit():
                continue
            importe = int(precio[1])
            if importe <= 0:
                continue
        except ValueError:
            continue
        salida.append(dict(nombre=nombre.get_text(' ', strip=True),
                           fecha=momento.date().isoformat(), hora=momento.strftime('%H:%M'),
                           precio=importe, entradas_url=enlace))
    return salida


def integrar(eventos, fichas, consultado):
    cantidad = 0
    for evento in eventos:
        if host(evento.get('evento_url', '')) != 'plataformalavarden.gob.ar':
            continue
        nombre = titulo(evento.get('nombre', ''))
        candidatos = []
        for ficha in fichas:
            otro = titulo(ficha['nombre'])
            mismo_nombre = nombre == otro or (min(len(nombre), len(otro)) >= 10 and
                                              (nombre in otro or otro in nombre))
            if mismo_nombre and (evento.get('fecha'), evento.get('hora')) == (ficha['fecha'], ficha['hora']):
                candidatos.append(ficha)
        if len(candidatos) != 1:
            continue
        ficha = candidatos[0]
        evento.update(precio=ficha['precio'],
                      precio_etiqueta=('Desde $' + f"{ficha['precio']:,}".replace(',', '.') + ' + cargo de servicio'),
                      entradas_url=ficha['entradas_url'], entrada_paga=True,
                      precio_fuente='Entradas Lavardén', precio_consultado=consultado)
        cantidad += 1
    return cantidad


def enlace_oficial(html, url):
    """Sólo enlaces directos a fichas: nunca la portada genérica."""
    enlaces = []
    for a in html.select('a[href]'):
        link = urljoin(url, a['href'].strip())
        if (urlsplit(link).scheme == 'https' and host(link) == 'entradaslavarden.com'
                and urlsplit(link).path.strip('/')
                and not urlsplit(link).query):
            if link not in enlaces:
                enlaces.append(link)
    return enlaces


def detalle_ticket(html, url):
    """Precio visible: el JSON-LD observado declara cero y moneda None.

    El importe global se usa sólo si hay una única función publicada.
    La apertura de puertas nunca se interpreta como horario de función.
    """
    nombre = html.select_one('h1.event-title')
    if not nombre:
        raise ValueError('Ficha de boletería sin título verificable')
    precios = set()
    for p in html.select('p'):
        t = ' '.join(p.get_text(' ', strip=True).split())
        match = re.fullmatch(r'Entradas Online Desde:\s*(?:ARS\s*)?(\d+)', t)
        if match and int(match[1]) > 0:
            precios.add(int(match[1]))
    funciones = []
    for option in html.select('#idFechasEventos option'):
        t = option.get_text(' ', strip=True)
        try:
            dt = datetime.strptime(t, '%d-%m-%Y, %H:%M')
        except ValueError:
            continue
        funciones.append((dt.date().isoformat(), dt.strftime('%H:%M')))
    # Sólo inspeccionar avisos visibles, excluyendo modales legales y scripts.
    avisos = ' '.join(x.get_text(' ', strip=True) for x in
                      html.select('.alert, #div_boton_compra, #idFechasEventos'))
    bloqueada = bool(re.search(r'agotad|cancelad|suspendid|reprogramad|venta finalizada', norm(avisos)))
    return {'nombre': nombre.get_text(' ', strip=True),
            'funciones': funciones, 'entradas_url': url,
            'precio': next(iter(precios)) if len(precios) == 1 and len(funciones) == 1 and not bloqueada else None,
            'bloqueada': bloqueada}


def ampliar(eventos, acceso):
    """Cada ficha falla de forma independiente; hasta 20 fichas oficiales por ciclo."""
    from actualizar_eventos import ZONA
    LIMITES['ficha_lavarden'] = 7200
    informe = []
    urls = list(dict.fromkeys(e.get('evento_url') for e in eventos
                             if host(e.get('evento_url', '')) == 'plataformalavarden.gob.ar'
                             and e.get('precio') != 0))[:20]
    limite = time.monotonic() + 600
    for oficial in urls:
        if time.monotonic() >= limite:
            informe.append({'estado': 'Presupuesto de diez minutos alcanzado; continúa en próximo ciclo'})
            break
        fila = {'oficial': oficial, 'precios_completados': 0}
        try:
            enlaces = acceso.leer(oficial, enlace_oficial, 'ficha_lavarden')
            fila['enlaces'] = enlaces
            if len(enlaces) != 1:
                fila['estado'] = 'sin enlace directo único; requiere revisión'
                informe.append(fila)
                continue
            link = enlaces[0]
            ficha = acceso.leer(link, detalle_ticket, 'ficha_lavarden')
            consultado = datetime.fromtimestamp(acceso.cache['paginas'][link]['consultado'], ZONA).strftime('%Y-%m-%d %H:%M')
            for e in eventos:
                if e.get('evento_url') != oficial:
                    continue
                if [e.get('fecha'), e.get('hora')] not in [list(f) for f in ficha['funciones']]:
                    continue
                e['entradas_url'] = link
                if ficha['precio'] is None:
                    continue
                # El enlace oficial acredita el título aunque difiera entre sitios.
                fila['precios_completados'] += integrar([e], [{
                    'nombre': e['nombre'], 'fecha': e['fecha'], 'hora': e['hora'],
                    'precio': ficha['precio'], 'entradas_url': link}], consultado)
            fila['estado'] = ('precio verificado' if fila['precios_completados'] else
                              'enlace revisado; precio o función sin confirmar')
        except (requests.RequestException, ValueError, OSError) as error:
            fila['estado'] = 'pendiente: ' + str(error)[:180]
        informe.append(fila)
        print('Lavardén:', fila, flush=True)
    return informe


def main():
    cache_path = ROOT / 'cache_fuentes_adicionales.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    acceso = Acceso(cache, session=SesionLavarden())
    archivo = ROOT / 'eventos.json'
    datos = json.loads(archivo.read_text(encoding='utf-8'))
    try:
        try:
            fichas = acceso.leer(URL, listado)
            from actualizar_eventos import ZONA
            registro = acceso.cache['paginas'][URL]
            consultado = datetime.fromtimestamp(registro['consultado'], ZONA).strftime('%Y-%m-%d %H:%M')
            print('Listado Lavardén:', integrar(datos.get('eventos', []), fichas, consultado), flush=True)
        except (requests.RequestException, ValueError) as error:
            print('Listado pendiente; se revisan enlaces oficiales:', error, flush=True)
        informe = ampliar(datos.get('eventos', []), acceso)
        guardar(archivo, datos)
        guardar(ROOT / 'revision_precios_lavarden.json', {'funciones_revisadas': informe})
    finally:
        guardar(cache_path, acceso.cache)
        acceso.session.close()


if __name__ == '__main__':
    main()
