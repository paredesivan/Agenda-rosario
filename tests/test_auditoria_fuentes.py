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


class TestAuditoriaAmpliada(unittest.TestCase):
    def test_demora_respetada(self):
        from auditar_fuentes import evaluar_reglas
        reglas = 'User-agent: *\nCrawl-delay: 60\nAllow: /\n'
        self.assertFalse(evaluar_reglas(reglas, {'https://ejemplo.com/'}, 60)['revisar_demora'])

    def test_social_solo_referencia(self):
        from auditar_fuentes import revisar_host
        get = Mock()
        r = revisar_host('www.instagram.com', {'https://www.instagram.com/ejemplo/'}, get)
        self.assertEqual(r['estado'], 'referencia_social_no_rastreada')
        get.assert_not_called()

    def test_redireccion_https_mismo_sitio(self):
        from auditar_fuentes import revisar_host
        get = Mock(side_effect=[
            Mock(status_code=301, headers={'Location': 'https://www.ejemplo.com/robots.txt'}),
            Mock(status_code=200, headers={}, text='User-agent: *\nDisallow: /privado/\n'),
        ])
        r = revisar_host('ejemplo.com', {'https://ejemplo.com/privado/a'}, get)
        self.assertEqual(r['estado'], 'rutas_restringidas')
        self.assertEqual(get.call_count, 2)

    def test_redireccion_insegura_no_se_sigue(self):
        from auditar_fuentes import revisar_host
        get = Mock(return_value=Mock(status_code=301, headers={'Location': 'http://ejemplo.com/robots.txt'}))
        r = revisar_host('ejemplo.com', {'https://ejemplo.com/'}, get)
        self.assertEqual(r['estado'], 'redireccion_robots_revisar')
        get.assert_called_once()

    def test_salas_dinamicas(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import auditar_fuentes
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            for archivo in auditar_fuentes.ARCHIVOS:
                (raiz / archivo).write_text('SALAS = (("Sala", "la-sala", "Rosario"),)\n'
                                            if archivo == 'fuentes_nuevas.py' else '', encoding='utf-8')
            with patch.object(auditar_fuentes, 'RAIZ', raiz):
                urls = auditar_fuentes.inventario()['www.teatrosatir.ar']
                self.assertIn('https://www.teatrosatir.ar/salas/la-sala/', urls)


class TestCorregirPausas(unittest.TestCase):
    def test_aplicar_es_idempotente(self):
        from corregir_pausas import actualizar_principal, actualizar_fuentes
        principal = 'ULTIMA, BLOQUEADOS, FALLAS = {}, set(), {}\nespera = 1.5 - (monotonic() - ULTIMA.get(host, 0))'
        dos_imports = 'from actualizar_eventos import SESION, BLOQUEADOS, ULTIMA, monotonic, sleep\n'
        dos_esperas = 'espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))\n'
        nuevas = dos_imports * 2 + dos_esperas * 2
        p = actualizar_principal(principal)
        f = actualizar_fuentes(nuevas)
        self.assertEqual(actualizar_principal(p), p)
        self.assertEqual(actualizar_fuentes(f), f)
        self.assertIn('"bibliotecavigil.org.ar": 60.0', p)
        self.assertEqual(f.count('PAUSAS_POR_HOST.get(host, 1.5)'), 2)

    def test_falla_si_modificaron_marcadores(self):
        from corregir_pausas import actualizar_principal
        with self.assertRaises(ValueError):
            actualizar_principal('configuracion distinta')
