import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fuentes_adicionales import Acceso

class ExcepcionesRobotsTest(unittest.TestCase):
    def test_por_defecto_no_se_ignora_robots(self):
        a = Acceso({}, Mock(), reloj=lambda: 10000, dormir=Mock())
        self.assertFalse(a.excepcion_robots_auditada('https://ejemplo.org/eventos/1'))

    def test_revision_incompleta_no_habilita(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'excepciones_robots.json').write_text(json.dumps({
                'excepciones': [{'dominio': 'ejemplo.org', 'rutas_publicas': ['/eventos'],
                    'acceso_publico_verificado': True, 'terminos_revisados': True,
                    'sin_prohibicion_contractual_aplicable': True,
                    'sin_barrera_tecnica': False,
                    'revision_legal': 'sin_impedimento_identificado',
                    'evidencia': 'Comprobación documentada de acceso público'}]}))
            with patch('fuentes_adicionales.ROOT', Path(tmp)):
                a = Acceso({}, Mock(), reloj=lambda: 10000, dormir=Mock())
                self.assertFalse(a.excepcion_robots_auditada('https://ejemplo.org/eventos/1'))

    def test_excepcion_acotada_a_dominio_y_ruta(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'excepciones_robots.json').write_text(json.dumps({
                'excepciones': [{'dominio': 'ejemplo.org', 'rutas_publicas': ['/eventos'],
                    'acceso_publico_verificado': True, 'terminos_revisados': True,
                    'sin_prohibicion_contractual_aplicable': True,
                    'sin_barrera_tecnica': True,
                    'revision_legal': 'sin_impedimento_identificado',
                    'evidencia': 'Auditoría documental con fecha y fuentes verificadas.'}]}))
            with patch('fuentes_adicionales.ROOT', Path(tmp)):
                a = Acceso({}, Mock(), reloj=lambda: 10000, dormir=Mock())
                self.assertTrue(a.excepcion_robots_auditada('https://ejemplo.org/eventos/1'))
                self.assertFalse(a.excepcion_robots_auditada('https://ejemplo.org/privado/1'))
                self.assertFalse(a.excepcion_robots_auditada('https://otro.org/eventos/1'))
                self.assertFalse(a.excepcion_robots_auditada('http://ejemplo.org/eventos/1'))

if __name__ == '__main__':
    unittest.main()
