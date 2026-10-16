import json
import unittest
from datetime import date
from unittest.mock import Mock

import requests
from bs4 import BeautifulSoup
from fuentes_adicionales import Acceso, hechos_schema, corroborar, listado_saleplan, listado_entradafan
from fuentes_nuevas import precio_producto_microteatro, eventos_cm25


class TestFuentesAdicionales(unittest.TestCase):
    def test_cm25_acepta_solo_fecha_hora_sede_y_titulo_futuros(self):
        html = BeautifulSoup('<main><h1>#</h1><h2>16OCT / Música en la casa</h2>'
            '<p>El viernes 16 de octubre a las 21 hs se presenta el ciclo.</p>'
            '<p>Corrientes 987 / PTA. ALTA / Rosario</p></main>', 'html.parser')
        eventos = eventos_cm25(html, 'https://www.cm25.ar/novedades.html', date(2026, 10, 15))
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]['fecha'], '2026-10-16')
        self.assertEqual(eventos[0]['hora'], '21:00')
        self.assertEqual(eventos[0]['precio'], 0)
        self.assertEqual(eventos[0]['descripcion'], '')

    def test_cm25_descarta_fecha_vencida_o_sin_sede(self):
        pasada = BeautifulSoup('<main><h2>10ABR / Actividad</h2><p>10 de abril a las 21 hs</p>'
                               '<p>Corrientes 987 Rosario</p></main>', 'html.parser')
        sin_sede = BeautifulSoup('<main><h2>Actividad</h2><p>16 de octubre a las 21 hs</p></main>',
                                 'html.parser')
        self.assertEqual(eventos_cm25(pasada, 'https://www.cm25.ar/novedades.html', date(2026, 10, 15)), [])
        self.assertEqual(eventos_cm25(sin_sede, 'https://www.cm25.ar/novedades.html', date(2026, 10, 15)), [])

    def ficha(self, localidad='Rosario', status='EventScheduled'):
        f = {'@type': 'MusicEvent', 'name': 'Concierto',
             'startDate': '2026-10-15T20:30:00', 'eventStatus': status,
             'location': {'name': 'Teatro Astengo', 'address': {
                 'addressLocality': localidad, 'addressRegion': 'Santa Fe'}},
             'offers': {'price': 99999, 'url': 'https://www.entradafan.com.ar/e/1'},
             'image': 'https://example.com/a.jpg', 'description': 'Sinopsis protegida'}
        return BeautifulSoup('<script type="application/ld+json">' + json.dumps(f) + '</script>', 'html.parser')

    def test_descarta_reventa_textos_e_imagenes(self):
        e = hechos_schema(self.ficha(), 'https://www.entradafan.com.ar')[0]
        self.assertEqual(e['fecha'], '2026-10-15')
        self.assertTrue({'precio', 'offers', 'descripcion', 'description', 'image'}.isdisjoint(e))

    def test_descarta_otra_localidad_y_cancelacion(self):
        self.assertEqual(hechos_schema(self.ficha('Córdoba'), 'https://x.com'), [])
        self.assertEqual(hechos_schema(self.ficha(status='EventCancelled'), 'https://x.com'), [])

    def test_no_infiere_anio_de_encabezado_saleplan(self):
        h = BeautifulSoup('<h1>14 octubre de 2027</h1><article class="event-card">'
                          '<h2><a href="https://saleplan.ar/santa-fe/rosario/planes/1">Evento</a>'
                          '</h2><p>Hoy 20:30</p></article>', 'html.parser')
        e = listado_saleplan(h, 'https://saleplan.ar/rosario/eventos')[0]
        self.assertNotIn('fecha', e)

    def test_verificacion_no_modifica_oficial(self):
        h = hechos_schema(self.ficha(), 'https://www.entradafan.com.ar')[0]
        oficial = {'nombre': 'Concierto', 'fecha': h['fecha'], 'hora': h['hora'],
                   'lugar': 'Teatro Astengo', 'precio': 1000, 'evento_url': 'https://teatroastengo.ar/e/1'}
        self.assertIs(corroborar(h, [oficial]), oficial)
        self.assertEqual(oficial['precio'], 1000)
        self.assertIsNone(corroborar({**h, 'hora': '21:00'}, [oficial]))

    def test_403_detiene_consultas_del_dominio(self):
        response = Mock(status_code=403, headers={})
        response.raise_for_status.side_effect = requests.HTTPError('403')
        session = Mock()
        session.get.return_value = response
        a = Acceso({}, session, reloj=lambda: 100000, dormir=Mock())
        with self.assertRaises(requests.HTTPError):
            a.leer('https://saleplan.ar/rosario/eventos', listado_saleplan)
        with self.assertRaises(ValueError):
            a.leer('https://saleplan.ar/rosario/eventos', listado_saleplan)
        self.assertEqual(session.get.call_count, 1)

    def test_cache_evitar_consultas_repetidas(self):
        url = 'https://rosariotimes.com/'
        cache = {'paginas': {url: {'consultado': 100000, 'datos': ['ref']}}}
        session = Mock()
        a = Acceso(cache, session, reloj=lambda: 100010, dormir=Mock())
        self.assertEqual(a.leer(url, lambda *args: []), ['ref'])
        session.get.assert_not_called()

    def test_robots_bloquea_ruta(self):
        cache = {'robots': {'https://x.com/robots.txt': {'consultado': 100000,
                 'reglas': 'User-agent: *\nDisallow: /privado/'}}}
        session = Mock()
        a = Acceso(cache, session, reloj=lambda: 100010, dormir=Mock())
        with self.assertRaises(ValueError):
            a.leer('https://x.com/privado/eventos', lambda *args: [])
        session.get.assert_not_called()

    def test_cuatro_notas_diarias_no_descarga_quinta(self):
        from datetime import datetime
        now = 100000
        dia = datetime.fromtimestamp(now).date().isoformat()
        cache = {'robots': {'https://x.com/robots.txt': {'consultado': now,
                 'reglas': 'User-agent: *\nAllow: /'}},
                 'notas_diarias': {'x.com:' + dia: ['a', 'b', 'c', 'd']}}
        session = Mock()
        a = Acceso(cache, session, reloj=lambda: now, dormir=Mock())
        with self.assertRaises(ValueError):
            a.leer('https://x.com/quinta', lambda *args: [], 'nota')
        session.get.assert_not_called()

    def test_304_reutiliza_hechos(self):
        url = 'https://x.com/agenda'
        cache = {'robots': {'https://x.com/robots.txt': {'consultado': 100000,
                 'reglas': 'User-agent: *\nAllow: /'}},
                 'paginas': {url: {'consultado': 1, 'etag': 'version1', 'datos': ['hecho']}}}
        response = Mock(status_code=304, headers={})
        session = Mock()
        session.get.return_value = response
        a = Acceso(cache, session, reloj=lambda: 100010, dormir=Mock())
        self.assertEqual(a.leer(url, lambda *args: []), ['hecho'])
        self.assertEqual(session.get.call_args.kwargs['headers']['If-None-Match'], 'version1')

    def test_429_respeta_retry_after_mayor(self):
        response = Mock(status_code=429, headers={'Retry-After': '172800'})
        response.raise_for_status.side_effect = requests.HTTPError('429')
        session = Mock()
        session.get.return_value = response
        cache = {}
        a = Acceso(cache, session, reloj=lambda: 100000, dormir=Mock())
        with self.assertRaises(requests.HTTPError):
            a.pedir('https://x.com/agenda')
        self.assertEqual(cache['pausas']['x.com'], 272800)

    def test_microteatro_jsonld_y_precio_visible(self):
        for markup in ('<main><span class="js-price-display">$5.750,00</span></main>',
                       '<script type="application/ld+json">{"@type":"Product","offers":'
                       '{"price":"5750.00","priceCurrency":"ARS"}}</script>'):
            self.assertEqual(precio_producto_microteatro(BeautifulSoup(markup, 'html.parser')), 5750)

    def test_microteatro_sin_precio_no_inventa(self):
        self.assertIsNone(precio_producto_microteatro(BeautifulSoup('<main><h1>Obra</h1></main>', 'html.parser')))

    def test_entradafan_filas_fechadas_sin_otras_ciudades(self):
        def fila(lugar):
            return ('<a class="event-row-link" href="/e/1"><div itemprop="startDate" '
                    'content="2026-10-15T20:30:00"></div><h3 class="event-title-with-badge">'
                    '<span class="event-title-text">Concierto</span></h3><span>' + lugar + '</span>'
                    '<p>$99999</p></a>')
        html = BeautifulSoup(fila('Teatro Astengo, Rosario') + fila('Teatro, Córdoba'), 'html.parser')
        hechos = listado_entradafan(html, 'https://www.entradafan.com.ar/entradas-rosario/c3642')
        self.assertEqual(len(hechos), 1)
        oficial = {'nombre': 'Concierto', 'fecha': '2026-10-15', 'hora': '20:30', 'lugar': 'Teatro Astengo'}
        self.assertIs(corroborar(hechos[0], [oficial]), oficial)
        self.assertNotIn('precio', hechos[0])


if __name__ == '__main__':
    unittest.main()
