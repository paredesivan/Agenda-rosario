import tempfile
import unittest
from pathlib import Path
from instalar_mejoras_extraccion import CAMBIOS, transformar, instalar

class PruebasMejoras(unittest.TestCase):
    def casos(self):
        return {nombre: '\n'.join(antes for antes, despues in reglas) + '\n' for nombre, reglas in CAMBIOS.items()}

    def test_parches_compilan_y_son_idempotentes(self):
        # Stubs breves con las anclas de cada archivo: los tests del repo
        # validan la integración con los módulos completos.
        originales = self.casos()
        nuevos = transformar(originales, validar_sintaxis=False)
        self.assertEqual(nuevos, transformar(nuevos, validar_sintaxis=False))
        self.assertNotIn('not INTERES.search', nuevos['fuentes_nuevas.py'])
        self.assertIn('prioridad_pendiente', nuevos['resolver_candidatos.py'])

    def test_rollback_si_falta_una_ancla(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for archivo, texto in self.casos().items():
                (r/archivo).write_text(texto)
            (r/'resolver_candidatos.py').write_text('código diferente')
            antes=(r/'fuentes_nuevas.py').read_text()
            with self.assertRaises(ValueError):
                instalar(r)
            self.assertEqual((r/'fuentes_nuevas.py').read_text(), antes)

    def test_sin_fechas_ni_eventos_hardcodeados(self):
        texto=(Path(__file__).resolve().parents[1]/'instalar_mejoras_extraccion.py').read_text()
        self.assertNotIn('2026-10-31', texto)
        self.assertNotIn('eventos.append({', texto)

if __name__ == '__main__': unittest.main()
