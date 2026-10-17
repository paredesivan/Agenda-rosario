import json
import unittest
from datetime import date
from unittest.mock import patch
import requests
from bs4 import BeautifulSoup
import actualizar_eventos as agenda

BASE = 'https://teatrolacomedia.gob.ar'
URL = BASE + '/espectaculos/programacion/'
OBRA = BASE + '/espectaculo/obra-nueva/'
FUENTE = 'Teatro Municipal La Comedia'


def html(s):
    return BeautifulSoup(s, 'html.parser')


def listado(enlace=OBRA):
    return html(f'<article class="kalendo_event"><h2 class="entry-title"><a href="{enlace}">Obra nueva</a></h2></article>')


def ficha(fecha='2026-10-21T15:00:00-03:00', estado='EventScheduled', descripcion='Entrada gratuita', url=OBRA):
    dato = {'@type': 'Event', 'url': url, 'name': 'Obra nueva', 'startDate': fecha,
            'eventStatus': 'https://schema.org/' + estado}
    return html('<article class="kalendo_event"><h1>Obra nueva</h1><div class="entry-content">'
                + descripcion + '</div></article><script type="application/ld+json">'
                + json.dumps(dato) + '</script>')


class Comedia(unittest.TestCase):
    def extraer(self, detalle, pagina=None):
        with patch.object(agenda, 'descargar', return_value=detalle) as descarga:
            resultado = agenda.calendario(pagina or listado(), FUENTE, URL, 'Mitre 958', date(2026, 10, 17))
        return resultado, descarga

    def test_nuevo_formato_sin_event_schema_en_listado(self):
        (eventos, fallidos), _ = self.extraer(ficha())
        self.assertEqual(fallidos, set())
        self.assertEqual([(e['fecha'], e['hora'], e['precio']) for e in eventos], [('2026-10-21', '15:00', 0)])

    def test_hora_local_y_precio_desconocido(self):
        (eventos, _), _ = self.extraer(ficha('2026-10-22T01:00:00+00:00', descripcion='Obra teatral'))
        self.assertEqual((eventos[0]['fecha'], eventos[0]['hora']), ('2026-10-21', '22:00'))
        self.assertIsNone(eventos[0]['precio'])

    def test_cancelaciones_y_fuera_de_ventana(self):
        for detalle in (ficha(estado='EventCancelled'), ficha(estado='EventPostponed'),
                        ficha(descripcion='Función suspendida'), ficha('2026-09-01T20:00:00-03:00'),
                        ficha('2026-12-01T20:00:00-03:00')):
            with self.subTest(detalle=str(detalle)):
                (eventos, fallidos), _ = self.extraer(detalle)
                self.assertEqual((eventos, fallidos), ([], set()))

    def test_ficha_incompleta_o_fecha_invalida_se_conserva(self):
        for detalle in (html('<h1>Error</h1>'), ficha('2026-02-31T20:00:00'), ficha('2026-10-21'), ficha(url=BASE+'/otra/')):
            (eventos, fallidos), _ = self.extraer(detalle)
            self.assertEqual((eventos, fallidos), ([], {OBRA}))

    def test_no_usa_eventos_del_sidebar(self):
        detalle = ficha()
        sidebar = ficha(url=BASE+'/espectaculo/otra/').select_one('script')
        detalle.append(sidebar)
        (eventos, _), _ = self.extraer(detalle)
        self.assertEqual(len(eventos), 1)

    def test_enlaces_repetidos_y_externos(self):
        pagina = listado()
        pagina.append(listado().article)
        pagina.append(listado('https://externo.com/espectaculo/falso/').article)
        (eventos, _), descarga = self.extraer(ficha(), pagina)
        self.assertEqual(len(eventos), 1)
        descarga.assert_called_once_with(OBRA)

    def test_error_http_conserva_ficha(self):
        with patch.object(agenda, 'descargar', side_effect=requests.Timeout('timeout')):
            self.assertEqual(agenda.calendario_comedia(listado(), FUENTE, URL, 'Mitre 958', date(2026, 10, 17)), ([], {OBRA}))

    def test_formato_desconocido_es_error_explicativo(self):
        with self.assertRaisesRegex(ValueError, 'Kalendo'):
            agenda.calendario_comedia(html('<p>Error</p>'), FUENTE, URL, 'Mitre 958', date(2026, 10, 17))

    def test_paginacion(self):
        pagina = listado()
        pagina.append(html('<div class="pagination"><div class="alignleft"><a href="/espectaculos/programacion/page/2/">Anterior</a></div></div>').div)
        otro = BASE + '/espectaculo/segunda/'
        respuestas = {BASE+'/espectaculos/programacion/page/2/': listado(otro), OBRA: ficha(), otro: ficha(url=otro)}
        with patch.object(agenda, 'descargar', side_effect=respuestas.__getitem__):
            eventos, fallidos = agenda.calendario_comedia(pagina, FUENTE, URL, 'Mitre 958', date(2026, 10, 17))
        self.assertEqual(len(eventos), 2)
        self.assertFalse(fallidos)
