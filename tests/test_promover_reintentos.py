import json
import tempfile
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
import actualizacion_segura as s


class RegistroAislado(unittest.TestCase):
    def test_promueve_solo_registro_municipal_tras_validar(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            evento=dict(nombre='Actividad temporal',fecha='2026-12-01',hora='20:00',lugar='Sala',origen='Fuente',evento_url='https://example.org/a')
            (root/'eventos.json').write_text(json.dumps({'eventos':[evento]}))
            registro={'https://www.rosario.gob.ar/inicio/a':{'ultimo_bloqueo':'2026-11-03T10:00:00-03:00','reintentar_desde':'2026-11-10T10:00:00-03:00'}}
            def ejecutar(*args,**kwargs):
                destino=kwargs['cwd'];(destino/'.agenda').mkdir()
                (destino/'.agenda/reintentos_municipales.json').write_text(json.dumps(registro))
                (destino/'.agenda/no_promover.json').write_text('{"secreto":"no copiar"}')
            r=s.ejecutar_etapa(root,'prueba.py',10,ejecutar,hoy=date(2026,11,3))
            self.assertEqual(r['estado'],'validada')
            self.assertEqual(json.loads((root/'.agenda/reintentos_municipales.json').read_text()),registro)
            self.assertFalse((root/'.agenda/no_promover.json').exists())

    def test_no_promueve_si_la_etapa_no_valida(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'eventos.json').write_text('{"eventos":[]}')
            def ejecutar(*args,**kwargs):
                destino=kwargs['cwd'];(destino/'.agenda').mkdir()
                (destino/'.agenda/reintentos_municipales.json').write_text('{}')
                (destino/'eventos.json').write_text('{"eventos":"invalido"}')
            r=s.ejecutar_etapa(root,'prueba.py',10,ejecutar,hoy=date(2026,11,3))
            self.assertEqual(r['estado'],'fallida')
            self.assertFalse((root/'.agenda/reintentos_municipales.json').exists())
