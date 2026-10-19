import unittest
from unittest.mock import Mock
from auditar_y_habilitar import clasificar_robots, evaluar

class AuditoriaTests(unittest.TestCase):
    def test_robots_disallow_no_se_ignora_sin_revision(self):
        self.assertEqual(clasificar_robots(200, 'User-agent: *\nDisallow: /agenda', 'https://ejemplo.ar/agenda'), 'excluido')
    def test_robots_404_es_ausencia_no_licencia(self):
        self.assertEqual(clasificar_robots(404, '', 'https://ejemplo.ar/agenda'), 'ausente')
    def test_sin_revision_no_habilita(self):
        s = Mock()
        s.get.side_effect = [Mock(status_code=404, text=''), Mock(status_code=200, text='<html><body>Cartelera</body></html>')]
        r = evaluar({'nombre': 'Prueba', 'listado': 'https://ejemplo.ar/agenda'}, {}, s)
        self.assertEqual(r['estado'], 'descartada')
    def test_html_protegido_no_habilita(self):
        s = Mock()
        s.get.side_effect = [Mock(status_code=404, text=''), Mock(status_code=403, text='')]
        r = evaluar({'nombre': 'Prueba', 'listado': 'https://ejemplo.ar/agenda'}, {}, s)
        self.assertEqual(r['estado'], 'descartada')
    def test_aprobada_solo_con_evidencias(self):
        s = Mock()
        s.get.side_effect = [Mock(status_code=404, text=''), Mock(status_code=200, text='<html>Agenda</html>')]
        rev = {key: True for key in ('acceso_publico_verificado', 'terminos_revisados','sin_prohibicion_contractual_aplicable', 'sin_barrera_tecnica', 'sin_impedimento_legal_identificado', 'fichas_y_parser_verificados')}
        rev.update(evidencia_url='https://ejemplo.ar/terminos', revision_fecha='2026-10-18')
        r = evaluar({'nombre': 'Prueba', 'listado': 'https://ejemplo.ar/agenda'}, rev, s)
        self.assertEqual(r['estado'], 'aprobada')
