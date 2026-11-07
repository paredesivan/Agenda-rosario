"""La fuente mudada sigue las mismas reglas de extracción y conservación."""
import json
import unittest
from datetime import date
from pathlib import Path

from actualizar_eventos import EXTRAS
from fuentes_ampliadas import revisar, fusionar, ficha
from test_fuentes_ampliadas import Fake, html, DONDE

ROOT = Path(__file__).resolve().parents[1]


class MigracionLavarden(unittest.TestCase):
    def setUp(self):
        config = json.loads((ROOT / 'fuentes_ampliadas.json').read_text())
        self.fuente = next(f for f in config['fuentes'] if f['nombre'] == 'Plataforma Lavardén')
        self.config = {'fuentes': [self.fuente]}
        self.base = self.fuente['listado']
        self.url = 'https://www.santafecultura.gob.ar/evento/prueba/'
        self.schema = {'@type': 'Event', 'name': 'Concierto de prueba', 'url': self.url,
                       'startDate': '2026-11-10T21:00:00-03:00'}
        self.donde = DONDE.replace('Sala Prueba', 'Plataforma Lavardén')

    def test_fuente_unica_y_lectura_por_coordinador(self):
        self.assertFalse(any(f[0] == self.fuente['nombre'] for f in EXTRAS))
        acceso = Fake({self.base: '<a class="card-evento" href="'+self.url+'">Prueba</a>',
                       self.url: html(self.schema, self.donde)})
        nuevos, _, estados, revisadas = revisar(self.config, acceso, date(2026, 11, 7))
        self.assertEqual(acceso.llamadas, [self.base, self.url])
        self.assertEqual(len(nuevos), 1)
        self.assertEqual(nuevos[0]['origen'], 'Plataforma Lavardén')
        self.assertEqual(nuevos[0]['hora'], '21:00')
        self.assertEqual(estados['Plataforma Lavardén']['fichas_pendientes'], 0)
        self.assertIn(('Plataforma Lavardén', self.url), revisadas)

    def test_migracion_reemplaza_solo_funcion_equivalente(self):
        nuevo = dict(fecha='2026-11-10', hora='21:00', nombre='Concierto de prueba',
                     lugar='Plataforma Lavardén', origen='Plataforma Lavardén', evento_url=self.url)
        viejo = dict(nuevo, evento_url='https://plataformalavarden.gob.ar/actividades/prueba/')
        otra = dict(viejo, hora='22:00')
        salida = fusionar([viejo, otra], [nuevo], set(), date(2026, 11, 7))
        self.assertEqual(salida, [nuevo, otra])
        self.assertEqual(viejo['evento_url'], 'https://plataformalavarden.gob.ar/actividades/prueba/')
        variante = dict(viejo, nombre='Presentación: Concierto de prueba')
        self.assertEqual(fusionar([variante], [nuevo], set(), date(2026, 11, 7)), [nuevo])
        variante = dict(viejo, nombre='Taller Encuentro de canto')
        otro_titulo = dict(nuevo, nombre='Taller de coplas: Encuentro de canto')
        self.assertEqual(fusionar([variante], [otro_titulo], set(), date(2026, 11, 7)), [otro_titulo])



    def test_bloqueo_o_formato_no_borran_funciones(self):
        from requests import RequestException
        for error in (RequestException('403 fuente pausada'), ValueError('Formato desconocido')):
            with self.subTest(error=error):
                acceso = Fake({self.base: error})
                nuevos, _, estados, revisadas = revisar(self.config, acceso, date(2026, 11, 7))
                viejo = dict(fecha='2026-11-10', hora='21:00', nombre='Concierto previo')
                self.assertEqual(fusionar([viejo], nuevos, revisadas, date(2026, 11, 7)), [viejo])
                self.assertEqual(estados['Plataforma Lavardén']['estado'], 'no accesible')

    def test_precio_visible_y_cero_generico(self):
        schema = dict(self.schema, offers={'price': '0'})
        self.assertNotIn('precio', ficha(html(schema, self.donde), self.url, self.fuente)[0])
        visible = self.donde + '<div><h4 class="block__title">Precio</h4><p>Gratuito</p></div>'
        self.assertEqual(ficha(html(schema, visible), self.url, self.fuente)[0]['precio'], 0)
        pago = visible.replace('Gratuito', 'Consultar')
        self.assertNotIn('precio', ficha(html(schema, pago), self.url, self.fuente)[0])
