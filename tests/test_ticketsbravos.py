import json
import unittest
from datetime import date
from pathlib import Path
from fuente_ticketsbravos import _ficha, revisar_ticketsbravos

class TicketsBravosTests(unittest.TestCase):
    def test_extrae_ficha_oficial(self):
        html='<h2>Prueba musical</h2><p>Fecha 21.OCT.2026 20:30hs</p><p>Lugar Casa Brava Pichincha 120, Rosario, Santa Fe</p>'
        e=_ficha(html,'https://www.ticketsbravos.com/eventos/prueba-e123',date(2026,10,18))
        self.assertIsNotNone(e)
        self.assertEqual(e['fecha'],'2026-10-21')
        self.assertEqual(e['lugar'],'Casa Brava')
        self.assertEqual(e['direccion'],'Pichincha 120, Rosario, Santa Fe')
    def test_rechaza_fuera_rosario(self):
        html='<h2>Prueba musical</h2>Fecha 21.OCT.2026 20:30hs Lugar Sala Principal Córdoba, Córdoba'
        self.assertIsNone(_ficha(html,'https://www.ticketsbravos.com/eventos/prueba-e123',date(2026,10,18)))
    def test_no_consulta_si_no_hay_terminos_aprobados(self):
        import os
        anterior=os.environ.pop('TICKETS_BRAVOS_TERMS_APPROVED',None)
        try:
            estado={}
            self.assertEqual(revisar_ticketsbravos(date(2026,10,18),estado),[])
            self.assertIn('pendiente',estado['Tickets Bravos'])
        finally:
            if anterior is not None:os.environ['TICKETS_BRAVOS_TERMS_APPROVED']=anterior
    def test_evento_en_snapshot(self):
        archivo=Path(__file__).resolve().parents[1]/'eventos.json'
        if not archivo.exists(): self.skipTest('Requiere repositorio completo')
        datos=json.loads(archivo.read_text(encoding='utf-8'))
        self.assertTrue(any(e.get('evento_url')=='https://www.ticketsbravos.com/eventos/hello-el-unplugged-e223' for e in datos['eventos']))
