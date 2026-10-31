import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import actualizar_eventos as municipal


class ReintentosMunicipales(unittest.TestCase):
    def comprobar(self, cantidad):
        eventos = [dict(fecha='2026-11-20', hora='20:00', nombre=f'Actividad {i}',
                        lugar=f'Sala {i}', origen=municipal.ORIGEN,
                        evento_url=f'https://www.rosario.gob.ar/inicio/actividad-{i}')
                   for i in range(cantidad)]
        por_url = {e['evento_url']: e for e in eventos}
        def consultar(url, hoy):
            municipal.DIAGNOSTICO_MUNICIPAL[url] = dict(url=url, funciones=1)
            return url, [por_url[url]], None, False
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp)/'eventos.json'
            archivo.write_text(json.dumps({'eventos': eventos}))
            with patch.object(municipal, 'ARCHIVO', archivo), \
                 patch.object(municipal, 'EXTRAS', ()), \
                 patch.object(municipal, 'datetime') as reloj, \
                 patch.object(municipal, 'obtener_enlaces', side_effect=RuntimeError('índice caído')), \
                 patch.object(municipal, 'consultar_evento', side_effect=consultar) as fichas, \
                 patch('builtins.print'):
                reloj.now.return_value = datetime(2026, 10, 31, 10, tzinfo=municipal.ZONA)
                municipal.actualizar()
            datos = json.loads(archivo.read_text())
            diagnostico = json.loads((Path(tmp)/'revision_cobertura_municipal.json').read_text())
            self.assertEqual(fichas.call_count, min(40, cantidad))
            self.assertEqual(diagnostico['fichas_consultadas'], min(40, cantidad))
            self.assertEqual(len(datos['eventos']), cantidad)
            self.assertIn('índice caído', ' '.join(datos['avisos_fuentes']))

    def test_indice_caido_no_impide_reconsultar_ficha_conocida(self):
        self.comprobar(1)

    def test_lote_parcial_conserva_fichas_no_consultadas(self):
        self.comprobar(45)
