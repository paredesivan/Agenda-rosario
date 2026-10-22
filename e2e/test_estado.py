"""Panel móvil, filtros, acceso caído, datos seguros y consulta en vivo."""
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/estado.html'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.shutdown(); cls.server.server_close(); cls.thread.join(2)

    def page(self):
        ctx = self.browser.new_context(viewport={'width': 360, 'height': 800}, is_mobile=True, has_touch=True)
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.route('https://api.github.com/**', lambda r: r.fulfill(json={'workflow_runs': [{'event': 'schedule', 'status': 'completed', 'conclusion': 'success', 'html_url': 'https://github.com/paredesivan/Agenda-rosario/actions/runs/123'}]}))
        return page

    def test_panel_real_celular_y_filtros(self):
        page = self.page()
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(self.url)
        page.wait_for_function("document.querySelector('#copy').disabled === false")
        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        page.locator('#filter').select_option('all')
        self.assertGreater(page.locator('.source').count(), 0)
        page.locator('#search').fill('zzzz_no_existe')
        self.assertEqual(page.locator('.source').count(), 0)
        page.locator('#search').fill('')
        page.locator('#filter').select_option('attention')
        self.assertEqual(errors, [])
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ROOT / 'reportes/panel_movil.png'), full_page=False)

    def test_fallo_recarga_conserva_panel(self):
        page = self.page(); page.goto(self.url)
        page.wait_for_function("document.querySelector('#copy').disabled === false")
        previous = page.locator('#events').inner_text()
        page.route('**/estado_agenda.json', lambda r: r.fulfill(status=503))
        page.route('https://api.github.com/**', lambda r: r.fulfill(status=403))
        page.locator('#refresh').click()
        page.wait_for_function("document.querySelector('#feedback').textContent.includes('conserva')")
        self.assertEqual(page.locator('#events').inner_text(), previous)
        self.assertIn('No se pudo consultar GitHub',page.locator('#live').inner_text())

    def test_textos_no_se_interpretan_como_html(self):
        data = json.loads((ROOT/'estado_agenda.json').read_text())
        data['fuentes']=[{'nombre':'<img src=x onerror="window.xss=1">','estado':'pendiente','motivo':'<script>window.xss=1</script>','accion':'Verificar','eventos':0,'conservados':0}]
        page=self.page();page.route('**/estado_agenda.json',lambda r:r.fulfill(json=data));page.goto(self.url)
        page.wait_for_function("document.querySelector('#copy').disabled === false")
        self.assertEqual(page.locator('#sources img').count(),0)
        self.assertIsNone(page.evaluate('window.xss'))
        self.assertIn('<img',page.locator('.source h3').inner_text())

    def test_informe_viejo_con_ejecucion_fallida(self):
        page=self.page()
        page.route('https://api.github.com/**', lambda r:r.fulfill(json={'workflow_runs':[{'event':'schedule','status':'completed','conclusion':'failure','html_url':'https://github.com/paredesivan/Agenda-rosario/actions/runs/123'}]}))
        page.goto(self.url)
        page.wait_for_function("document.querySelector('#live').textContent.includes('falló')")
        self.assertIn('puede ser anterior',page.locator('#live').inner_text())

if __name__ == '__main__':
    unittest.main(verbosity=2)
