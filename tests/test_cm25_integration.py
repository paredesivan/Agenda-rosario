"""Pruebas de integración del registro y consulta de la fuente CM25."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

import fuentes_nuevas
from fuentes_nuevas import CM25_NOVEDADES, FUENTES_CSV, leer_cm25


class TestIntegracionCM25(unittest.TestCase):
    def test_fuente_oficial_esta_registrada_con_prioridad_alta(self):
        fuente = next(
            item for item in FUENTES_CSV
            if item[0] == "Centro Cultural 25 de Mayo"
        )
        self.assertEqual(fuente[2], CM25_NOVEDADES)
        self.assertEqual(fuente[3], "alta")

    def test_consulta_url_parsea_evento_y_guarda_cache(self):
        html = BeautifulSoup(
            "<main><h2>16OCT / Música en la casa</h2>"
            "<p>El viernes 16 de octubre a las 21 hs se presenta el ciclo.</p>"
            "<p>Corrientes 987 / Planta alta / Rosario</p></main>",
            "html.parser",
        )
        recibido = {}

        class AccesoFalso:
            def __init__(self, cache):
                self.cache = cache

            def leer(self, url, parser, tipo):
                recibido.update(url=url, tipo=tipo)
                self.cache["prueba"] = {"consultado": 1}
                return parser(html, url)

        with tempfile.TemporaryDirectory() as temporal:
            ruta_cache = Path(temporal) / "cache_cm25.json"
            estado = {}
            with patch.object(fuentes_nuevas, "CM25_CACHE", ruta_cache), patch(
                "fuentes_adicionales.Acceso", AccesoFalso
            ):
                eventos = leer_cm25(date(2026, 10, 15), estado)

            self.assertEqual(recibido, {"url": CM25_NOVEDADES, "tipo": "listado"})
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0]["fecha"], "2026-10-16")
            self.assertEqual(eventos[0]["hora"], "21:00")
            self.assertIn(
                "1 eventos verificables",
                estado["Centro Cultural 25 de Mayo"],
            )
            self.assertTrue(ruta_cache.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
