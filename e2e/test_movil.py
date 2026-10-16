"""E2E móvil: datos reales, presupuesto, filtros, duplicados y fallos de recarga."""
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class Movil(unittest.TestCase):
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

    def page(self):
        context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
                                          device_scale_factor=2, has_touch=True, timezone_id='America/Argentina/Cordoba')
        self.addCleanup(context.close)
        return context.new_page()

    def test_carga_real_en_4g_y_cpu_lenta(self):
        page = self.page()
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        cdp = page.context.new_cdp_session(page)
        cdp.send('Network.enable')
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 150,
                 'downloadThroughput': 200000, 'uploadThroughput': 93750})
        cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        page.goto(self.url)
        page.wait_for_function('window.agendaMetrics?.visibleMs >= 0', timeout=20000)
        metrics = page.evaluate('window.agendaMetrics')
        metrics['perfil'] = '390x844, CPU x4, 1.6 Mbps, latencia 150 ms; servidor local sin compresión'
        metrics['alcance'] = 'Simulación de navegador; no mide disponibilidad ni latencia real de GitHub Pages'
        (ROOT / 'reportes').mkdir(exist_ok=True)
        (ROOT / 'reportes/movil.json').write_text(json.dumps(metrics, indent=2))
        print(json.dumps(metrics, indent=2))
        self.assertLess(metrics['jsonBytes'], 1_000_000)
        self.assertLess(metrics['renderMs'], 1500)
        self.assertLess(metrics['navigationVisibleMs'], 10000)
        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(errors, [])
        page.locator('[data-filter="teatro"]').click()
        page.locator('[data-filter="todos"]').click()

    def test_deduplicacion_fuente_oficial_y_horarios_distintos(self):
        page = self.page()
        item = {'fecha': '2099-05-15', 'hora': '20:00', 'nombre': 'Concierto de prueba',
                'lugar': 'Sala de prueba', 'direccion': 'Mitre 100', 'precio': 2000}
        datos = {'eventos': [
            {**item, 'origen': 'Rosario3', 'evento_url': 'https://rosario3.com/nota'},
            {**item, 'origen': 'Municipalidad de Rosario', 'evento_url': 'https://www.rosario.gob.ar/inicio/prueba'},
            {**item, 'hora': '22:00', 'origen': 'Municipalidad de Rosario'}]}
        page.route('**/eventos.json*', lambda route: route.fulfill(json=datos))
        page.goto(self.url)
        page.locator('.event h3').first.wait_for()
        self.assertEqual(page.locator('.event h3').count(), 2)
        self.assertEqual(page.locator('a.event-info').first.get_attribute('href'), 'https://www.rosario.gob.ar/inicio/prueba')
        resultado = page.evaluate('''() => {
          const base = {fecha:'2099-05-15',hora:'20:00',nombre:'Concierto de prueba',lugar:'Sala A',direccion:'Mitre 100'};
          return deduplicatedEvents([base,{...base,lugar:'Sala B',direccion:'Mitre 200'}]).length;
        }''')
        self.assertEqual(resultado, 2)

    def test_recarga_rota_conserva_eventos_y_carga_inicial_muestra_error(self):
        page = self.page()
        page.goto(self.url)
        page.wait_for_function('window.agendaMetrics?.visibleMs >= 0')
        antes = page.locator('#events').inner_text()
        for modo in ('json', 'esquema', 'http'):
            page.unroute('**/eventos.json*')
            if modo == 'json':
                page.route('**/eventos.json*', lambda route: route.fulfill(body='{', content_type='application/json'))
            elif modo == 'esquema':
                page.route('**/eventos.json*', lambda route: route.fulfill(json={'eventos': 'roto'}))
            else:
                page.route('**/eventos.json*', lambda route: route.fulfill(status=503))
            self.assertTrue(page.evaluate('loadEvents().then(() => false).catch(() => true)'))
            self.assertEqual(page.locator('#events').inner_text(), antes)
        page.reload()
        page.wait_for_function("document.querySelector('#events').textContent.includes('Error cargando')")


if __name__ == '__main__':
    unittest.main(verbosity=2)
