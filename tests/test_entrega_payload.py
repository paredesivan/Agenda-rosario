"""La entrega autocontenida instala exactamente el código que se prueba."""
import base64
import gzip
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
import yaml
from instalar_entrega import aplicar

ROOT=Path(__file__).resolve().parents[1]


class Payload(unittest.TestCase):
    def test_paquete_integro_y_pasos_en_orden(self):
        workflow=yaml.load((ROOT/'.github/workflows/actualizar.yml').read_text(),Loader=yaml.BaseLoader)
        steps=workflow['jobs']['agenda']['steps']
        b64=''.join(re.search(r"f.write\('([A-Za-z0-9+/=]+)'\)",s['run'])[1]
                    for s in steps if s.get('name','').startswith('Preparar paquete de entrega'))
        raw=gzip.decompress(base64.b64decode(b64));payload=json.loads(raw)
        installer=next(s['run'] for s in steps if s.get('id')=='instalar')
        self.assertIn(hashlib.sha256(raw).hexdigest(),installer)
        self.assertEqual(payload['version'],'2026.10.24-cobertura-seguridad-seo-2')
        # El instalador no debe revertir cambios posteriores cuando ya se instaló.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fresh={**payload,'expected':{name:[None] for name in payload['files']}}
            self.assertTrue(aplicar(fresh,root))
            for name,content in payload['files'].items():
                self.assertEqual((root/name).read_text(),content)
            (root/'agenda.js').write_text('cambio posterior')
            self.assertFalse(aplicar(fresh,root))
            self.assertEqual((root/'agenda.js').read_text(),'cambio posterior')
        indexes={s.get('id'):i for i,s in enumerate(steps) if s.get('id')}
        self.assertLess(indexes['actualizar'],indexes['paginas'])
        self.assertLess(indexes['paginas'],indexes['navegador'])
        self.assertIn('e2e/test_estaticas.py',steps[indexes['navegador']]['run'])
        self.assertLess(indexes['avisos'],indexes['guardar'])
