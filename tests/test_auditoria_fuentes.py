import unittest
from collections import defaultdict
from unittest.mock import Mock
from auditar_fuentes import evaluar_reglas, registrar, revisar_host


class TestAuditoria(unittest.TestCase):
    def test_respeta_bloqueo(self):
        reglas = "User-agent: *\nDisallow: /privado/\nAllow: /\n"
        res = evaluar_reglas(reglas, {"https://ejemplo.com/privado/a", "https://ejemplo.com/agenda"})
        self.assertEqual(res["estado"], "rutas_restringidas")
        self.assertEqual(res["rutas_restringidas"], ["https://ejemplo.com/privado/a"])

    def test_demora(self):
        res = evaluar_reglas("User-agent: *\nAllow: /\nCrawl-delay: 5\n", {"https://ejemplo.com/"})
        self.assertTrue(res["revisar_demora"])

    def test_no_autorizacion_ante_403(self):
        get = Mock(return_value=Mock(status_code=403))
        res = revisar_host("ejemplo.com", {"https://ejemplo.com/agenda"}, get)
        self.assertEqual(res["estado"], "revisar_respuesta_robots")
        self.assertEqual(get.call_count, 1)

    def test_descarta_http_local(self):
        urls = defaultdict(set)
        registrar(urls, "http://ejemplo.com/")
        registrar(urls, "https://ejemplo.local/")
        registrar(urls, "https://ejemplo.com/agenda")
        self.assertEqual(list(urls), ["ejemplo.com"])


if __name__ == "__main__":
    unittest.main()
