"""Comprueba ambas vistas sobre los mismos eventos y estado de navegación."""
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DATOS = {'eventos': [
    {'fecha': '2099-05-15', 'hora': hora, 'nombre': nombre, 'lugar': 'Sala cultural',
     'categorias': [cat], 'precio': precio, 'evento_url': 'https://example.org/evento',
     'direccion': 'Mitre 100, Rosario'}
    for hora, nombre, cat, precio in [
        ('21:00', 'Concierto nocturno', 'musica', 2000),
        ('19:00', 'Teatro de prueba', 'teatro', 0),
        ('A confirmar', 'Concierto sin horario', 'musica', 0)]
] + [{'fecha': '2099-05-16', 'hora': '20:00', 'nombre': 'Concierto del sábado',
      'lugar': 'Otra sala', 'categorias': ['musica'], 'precio': 0}]}


class Vistas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/index.html'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def page(self, width=390):
        context = self.browser.new_context(viewport={'width': width, 'height': 844})
        self.addCleanup(context.close)
        page = context.new_page()
        page.route('**/eventos.json*', lambda route: route.fulfill(json=DATOS))
        return page

    def ready(self, page):
        page.goto(self.url)
        page.locator('.event').first.wait_for()

    def test_preferencia_recarga_y_visitantes_independientes(self):
        page = self.page()
        self.ready(page)
        self.assertEqual(page.locator('html').get_attribute('data-agenda-view'), 'cuaderno')
        page.locator('button[data-agenda-view=calendario]').click()
        self.assertTrue(page.locator('#week-strip').is_visible())
        page.reload()
        page.locator('.event').first.wait_for()
        self.assertEqual(page.locator('button[data-agenda-view=calendario]').get_attribute('aria-pressed'), 'true')
        page.locator('button[data-agenda-view=cuaderno]').click()
        self.assertFalse(page.locator('#week-strip').is_visible())
        other = self.page()
        self.ready(other)
        self.assertEqual(other.locator('html').get_attribute('data-agenda-view'), 'cuaderno')

    def test_conserva_busqueda_filtros_dia_y_enlaces(self):
        page = self.page()
        self.ready(page)
        page.locator('#event-search').fill('Concierto')
        page.locator('#event-search-form button[type=submit]').click()
        page.locator('[data-filter=musica]').click()
        page.locator('[data-filter=gratis]').click()
        for view in ('calendario', 'cuaderno', 'calendario'):
            page.locator(f'button[data-agenda-view={view}]').click()
            self.assertEqual(page.locator('.event h3').all_text_contents(), ['Concierto sin horario'])
            self.assertEqual(page.locator('#event-search').input_value(), 'Concierto')
            self.assertEqual(page.locator('[data-filter=gratis]').get_attribute('aria-pressed'), 'true')
            self.assertEqual(page.locator('a.event-info').get_attribute('href'), 'https://example.org/evento')
            self.assertIn('google.com/maps/search/', page.locator('.actions a.map').get_attribute('href'))
        page.locator('#week-strip [data-date="2099-05-16"]').click()
        before = page.locator('#selected').inner_text()
        page.locator('button[data-agenda-view=cuaderno]').click()
        self.assertEqual(page.locator('#selected').inner_text(), before)
        self.assertEqual(page.locator('.event h3').all_text_contents(), ['Concierto del sábado'])

    def test_fallo_inicial_y_recuperacion_conservan_respaldo(self):
        page = self.page()
        page.unroute('**/eventos.json*')
        page.route('**/eventos.json*', lambda route: route.fulfill(status=503))
        page.goto(self.url)
        page.wait_for_function("document.querySelector('#events').textContent.includes('Error')")
        self.assertTrue(page.locator('#static-agenda').is_visible())
        page.locator('button[data-agenda-view=calendario]').click()
        self.assertTrue(page.locator('#static-agenda').is_visible())
        page.unroute('**/eventos.json*')
        page.route('**/eventos.json*', lambda route: route.fulfill(json=DATOS))
        page.evaluate('loadEvents()')
        self.assertTrue(page.locator('#static-agenda').is_hidden())
        self.assertEqual(page.locator('.event').count(), 3)

    def test_orden_horarios_y_acceso_a_fecha(self):
        page = self.page()
        self.ready(page)
        self.assertEqual(page.locator('.event h3').all_text_contents(), [
            'Teatro de prueba', 'Concierto nocturno', 'Concierto sin horario'])
        page.locator('button[data-agenda-view=calendario]').click()
        self.assertEqual(page.locator('.timeline-time').all_text_contents(), ['19:00', '21:00', 'A confirmar'])
        page.locator('.month-picker summary').click()
        self.assertTrue(page.locator('#days').is_visible())
        page.locator('#next-day').click()
        self.assertEqual(page.locator('.event h3').all_text_contents(), ['Concierto del sábado'])

    def test_movil_teclado_y_almacenamiento_bloqueado(self):
        for width in (320, 390, 768, 1280):
            with self.subTest(width=width):
                page = self.page(width)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script("Storage.prototype.getItem = Storage.prototype.setItem = () => { throw Error('bloqueado'); }")
                self.ready(page)
                for view in ('calendario', 'cuaderno'):
                    button = page.locator(f'button[data-agenda-view={view}]')
                    button.focus()
                    page.keyboard.press('Enter')
                    self.assertEqual(button.get_attribute('aria-pressed'), 'true')
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
