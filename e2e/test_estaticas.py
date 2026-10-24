"""Navegación real sin JavaScript y coexistencia con el calendario interactivo."""
import functools
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generar_paginas import generar, ruta_evento
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
EVENTO={'fecha':'2099-10-30','hora':'20:00','nombre':'Actividad estática de prueba','lugar':'Sala de prueba',
        'evento_url':'https://example.org/evento','precio':0}


class Estaticas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();root=Path(cls.tmp.name)
        for name in ('index.html','agenda.js','estilos.css'):shutil.copy2(ROOT/name,root/name)
        (root/'eventos.json').write_text(json.dumps({'eventos':[EVENTO]}))
        generar(root,hoy='2099-10-24')
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(SimpleHTTPRequestHandler,directory=str(root)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.p.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join(2);cls.tmp.cleanup()

    def test_sin_js_abre_ficha_y_enlace_fuente(self):
        context=self.browser.new_context(java_script_enabled=False)
        try:
            page=context.new_page();page.goto(self.url+'/')
            page.locator('#static-agenda a').first.click()
            self.assertEqual(page.locator('h1').inner_text(),EVENTO['nombre'])
            self.assertEqual(page.locator('a:has-text("Consultar fuente")').get_attribute('href'),EVENTO['evento_url'])
            self.assertIsNotNone(page.locator('script[type="application/ld+json"]').text_content())
            page.locator('a:has-text("Ver todas las actividades")').click()
            self.assertEqual(page.locator('main li').count(),1)
        finally:context.close()

    def test_js_oculta_respaldo_tras_cargar_y_lo_conserva_si_falla(self):
        for falla in (False,True):
            page=self.browser.new_page()
            try:
                if falla:page.route('**/eventos.json*',lambda r:r.fulfill(status=500,body='error'))
                page.goto(self.url+'/')
                if falla:
                    page.wait_for_function('document.querySelector("#events").textContent.includes("Error")')
                    self.assertTrue(page.locator('#static-agenda').is_visible())
                else:
                    page.locator('.event h3').wait_for()
                    self.assertTrue(page.locator('#static-agenda').is_hidden())
            finally:page.close()


if __name__=='__main__':unittest.main()
