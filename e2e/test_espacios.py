"""Comprobación móvil del inventario generado, sin consultar webs externas."""
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class InventarioMovil(unittest.TestCase):
    def test_enlaces_y_lectura_en_celular(self):
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            with sync_playwright() as p:
                navegador = p.chromium.launch(headless=True)
                try:
                    page = navegador.new_page(viewport={'width': 390, 'height': 844})
                    respuesta = page.goto(f'http://127.0.0.1:{servidor.server_port}/espacios.html')
                    self.assertEqual(respuesta.status, 200)
                    self.assertEqual(page.locator('h1').inner_text(), 'Espacios y fuentes oficiales')
                    minimo = len(json.loads((ROOT/'espacios_oficiales.json').read_text())['espacios'])
                    self.assertGreaterEqual(page.locator('article').count(), minimo)
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                    self.assertTrue(all(h.startswith('https://') for h in page.locator('a').evaluate_all('(as) => as.map(a => a.href)')))
                finally:
                    navegador.close()
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
