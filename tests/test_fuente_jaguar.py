import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fuente_jaguar import extraer

class JaguarTest(unittest.TestCase):
    def test_detecta_evento_futuro_no_hardcodeado(self):
        html='<a href="https://damemiticket.com/evento-nuevo">Banda Nueva 25.10</a>'
        eventos=extraer(html,date(2026,10,18))
        self.assertEqual(len(eventos),1)
        self.assertEqual(eventos[0]['nombre'],'Banda Nueva')
        self.assertEqual(eventos[0]['fecha'],'2026-10-25')
        self.assertIsNone(eventos[0]['hora'])
    def test_no_acepta_sitios_desconocidos(self):
        self.assertEqual(extraer('<a href="https://malicioso.test/">Show 25.10</a>',date(2026,10,18)),[])
    def test_descarta_pasados(self):
        self.assertEqual(extraer('<a href="https://damemiticket.com/a">Viejo 17.10</a>',date(2026,10,18)),[])
    def test_sin_fecha_sin_publicacion(self):
        self.assertEqual(extraer('<a href="https://damemiticket.com/a">Sin fecha</a>',date(2026,10,18)),[])

if __name__=='__main__': unittest.main()
