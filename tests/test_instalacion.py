import json
import tempfile
import unittest
from pathlib import Path
from instalar_fuentes_institucionales import construir, instalar, CANDIDATAS


PY_AMP = '''from fuentes_adicionales import norm

def ficha(contenido, url, fuente):
    if fuente['adaptador'] in ('gamma_comunidad', 'institucion_mec'):
        return []
    return []

def revisar(config, acceso, hoy):
    nuevos = []
    hasta = hoy
    for e in []:
        if e.get('cancelado') or not hoy.isoformat() <= e['fecha'] <= hasta.isoformat():
            continue
    return nuevos
'''
PY_SEG = '''from control_http import atomico
ROOT = None

def main():
    datos = {'eventos': []}
    atomico(ROOT / 'eventos.json', datos)
'''


class Instalacion(unittest.TestCase):
    def test_idempotencia(self):
        src = {'fuentes_ampliadas.py': PY_AMP,
               'actualizacion_segura.py': PY_SEG,
               'fuentes_ampliadas.json': json.dumps({'fuentes': []})}
        uno = construir(dict(src))
        dos = construir(dict(uno))
        self.assertEqual(uno, dos)
        self.assertEqual(len(json.loads(dos['fuentes_ampliadas.json'])['fuentes']), len(CANDIDATAS))
        self.assertTrue(all(not f['habilitada'] for f in CANDIDATAS))
        self.assertIn('if e.get(\'cancelado\') or es_formacion(e)', dos['fuentes_ampliadas.py'])
        self.assertIn("if not es_formacion(e)", dos['actualizacion_segura.py'])

    def test_falla_sin_mutar_si_no_hay_punto_inyeccion(self):
        src = {'fuentes_ampliadas.py': 'print(1)', 'actualizacion_segura.py': PY_SEG,
               'fuentes_ampliadas.json': '{"fuentes": []}'}
        with self.assertRaises(ValueError):
            construir(src)

    def test_instalar_copia_seguridad(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'fuentes_ampliadas.py').write_text(PY_AMP)
            (root/'actualizacion_segura.py').write_text(PY_SEG)
            (root/'fuentes_ampliadas.json').write_text('{"fuentes": []}')
            respaldo = instalar(root)
            self.assertTrue((respaldo/'fuentes_ampliadas.py').exists())
            self.assertTrue((root/'instituciones_nuevas.py').exists())
            self.assertTrue((root/'tests'/'test_instituciones_nuevas.py').exists())
            self.assertEqual(len(json.loads((root/'fuentes_ampliadas.json').read_text())['fuentes']), len(CANDIDATAS))
            # Una segunda instalación no duplica fuentes ni filtros.
            instalar(root)
            self.assertEqual(len(json.loads((root/'fuentes_ampliadas.json').read_text())['fuentes']), len(CANDIDATAS))


if __name__ == '__main__':
    unittest.main()
