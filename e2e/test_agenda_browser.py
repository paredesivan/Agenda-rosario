"""Prueba E2E del flujo real de filtros y enlaces de la agenda."""
import json
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FECHA_FUTURA = "2099-05-15"
EVENTOS_PRUEBA = {
    "actualizado": "fixture E2E",
    "eventos": [
        {
            "fecha": FECHA_FUTURA,
            "hora": "19:00",
            "nombre": "La obra teatral de prueba",
            "lugar": "Teatro de prueba",
            "direccion": "Corrientes 100, Rosario",
            "descripcion": "",
            "evento_url": "https://example.org/teatro",
            "categorias": ["teatro"],
            "precio": 0,
            "precio_etiqueta": "Gratis",
            "origen": "Teatro de prueba",
        },
        {
            "fecha": FECHA_FUTURA,
            "hora": "20:00",
            "nombre": "Feria del barrio de prueba",
            "lugar": "Plaza de prueba",
            "direccion": "San Martín 200, Rosario",
            "descripcion": "",
            "evento_url": "https://example.org/feria",
            "categorias": ["ferias"],
            "precio": 2500,
            "precio_etiqueta": "$2.500",
            "origen": "Feria de prueba",
        },
        {
            "fecha": FECHA_FUTURA,
            "hora": "21:00",
            "nombre": "Concierto de prueba",
            "lugar": "Sala de música de prueba",
            "direccion": "Córdoba 300, Rosario",
            "descripcion": "",
            "evento_url": "https://example.org/musica",
            "categorias": ["musica"],
            "precio": 5000,
            "precio_etiqueta": "$5.000",
            "origen": "Sala de música de prueba",
        },
    ],
}


class TestAgendaEnNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/index.html"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_carga_combina_filtros_y_muestra_enlaces(self):
        page = self.browser.new_page()
        errores_js = []
        page.on("pageerror", lambda error: errores_js.append(str(error)))
        page.route(
            "**/eventos.json*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(EVENTOS_PRUEBA, ensure_ascii=False),
            ),
        )

        try:
            response = page.goto(self.url, wait_until="domcontentloaded")
            self.assertIsNotNone(response)
            self.assertEqual(response.status, 200)
            page.locator(".event h3").first.wait_for()
            self.assertEqual(page.locator(".event h3").all_text_contents(), [
                "La obra teatral de prueba",
                "Feria del barrio de prueba",
                "Concierto de prueba",
            ])

            page.locator('[data-filter="teatro"]').click()
            self.assertEqual(page.locator(".event h3").all_text_contents(), [
                "La obra teatral de prueba",
            ])

            # Las categorías seleccionadas se combinan con lógica OR.
            page.locator('[data-filter="ferias"]').click()
            self.assertEqual(page.locator(".event h3").all_text_contents(), [
                "La obra teatral de prueba",
                "Feria del barrio de prueba",
            ])

            # Gratis se agrega como condición AND a las categorías.
            page.locator('[data-filter="gratis"]').click()
            self.assertEqual(page.locator(".event h3").all_text_contents(), [
                "La obra teatral de prueba",
            ])
            self.assertEqual(
                page.locator("#day-count").inner_text(),
                "1 actividad con estos filtros",
            )
            self.assertEqual(
                page.locator("a.event-info").get_attribute("href"),
                "https://example.org/teatro",
            )
            self.assertTrue(
                page.locator(".actions a.map").get_attribute("href").startswith(
                    "https://www.google.com/maps/search/"
                )
            )
            self.assertEqual(errores_js, [])
        finally:
            page.close()

    def test_duplicado_sedes_equivalentes_y_fuente_directa(self):
        base = {**EVENTOS_PRUEBA['eventos'][0], 'nombre': 'Impresiones Sonoras - Ensamble Municipal de Vientos',
                'lugar': 'Parque España', 'direccion': 'SARMIENTO DOMINGO FAUSTINO 100, Rosario, Santa Fe',
                'origen': 'Municipalidad de Rosario', 'evento_url': 'https://rosario.gob.ar/actividad'}
        directa = {**base, 'nombre': 'Impresiones Sonoras – Ensamble Municipal de Vientos',
                   'lugar': 'Centro Cultural Parque de España', 'direccion': 'Sarmiento y el río, Rosario, Santa Fe',
                   'origen': 'Centro Cultural Parque de España', 'evento_url': 'https://ccpe.org.ar/actividad'}
        page = self.browser.new_page()
        try:
            page.route('**/eventos.json*', lambda route: route.fulfill(
                content_type='application/json', body=json.dumps({'eventos': [base, directa]})))
            page.goto(self.url)
            page.locator('.event h3').first.wait_for()
            self.assertEqual(page.locator('.event h3').count(), 1)
            self.assertEqual(page.locator('a.event-info').get_attribute('href'), directa['evento_url'])
            self.assertFalse(page.evaluate('sameLocation({lugar:"Sala 1"}, {lugar:"Sala 2"})'))
            self.assertFalse(page.evaluate('duplicateEvents(' + json.dumps(base) + ',' +
                                          json.dumps({**directa, 'hora':'21:00'}) + ')'))
        finally:
            page.close()

    def test_acr_enlace_propio_y_vencimiento_sin_refrescar_datos(self):
        page = self.browser.new_page()
        evento = {**EVENTOS_PRUEBA['eventos'][0], 'origen':'Agenda Cultural Rosario',
                  'evento_url':'https://www.agendaculturalrosario.com.ar/eventos/prueba',
                  'descripcion':'Actividad cultural publicada por Agenda Cultural Rosario.'}
        try:
            page.route('**/eventos.json*', lambda route: route.fulfill(
                content_type='application/json', body=json.dumps({'eventos':[evento]})))
            page.goto(self.url)
            page.locator('.event h3').first.wait_for()
            self.assertEqual(page.locator('a.event-info').get_attribute('href'),evento['evento_url'])
            self.assertFalse(page.evaluate('acrAvailable({origen:"Agenda Cultural Rosario",fecha:"2026-10-17",hora:"20:00"}, Date.parse("2026-10-17T20:30:00-03:00"))'))
            self.assertTrue(page.evaluate('acrAvailable({origen:"Agenda Cultural Rosario",fecha:"2026-10-17",hora:"20:00",fecha_fin:"2026-10-17",hora_fin:"21:00"}, Date.parse("2026-10-17T20:30:00-03:00"))'))
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
