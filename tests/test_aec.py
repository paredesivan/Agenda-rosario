import unittest
from pathlib import Path
from fuente_aec import ficha_aec,misma_sala_aec
from fuentes_ampliadas import fusionar
from datetime import date
HTML=(Path(__file__).parent/'fixtures/aec/anuncio_factual.html').read_text()
class AECTests(unittest.TestCase):
 def test_html_real_dos_funciones(self):
  e=ficha_aec(HTML,'https://www.aecrosario.org.ar/prueba/',{});self.assertEqual([(x['fecha'],x['hora']) for x in e],[('2026-10-23','20:00'),('2026-10-24','20:00')])
 def test_beneficio_afiliado_no_gratis_general(self):
  e=ficha_aec(HTML,'',{})[0];self.assertIsNone(e['precio']);self.assertIn('afiliados',e['precio_etiqueta']);self.assertNotEqual(e['precio_etiqueta'],'Gratis')
 def test_no_horario_boleteria(self):
  e=ficha_aec(HTML.replace('desde las 20,',''),'',{})[0];self.assertEqual(e['hora'],'Horario a confirmar')
 def test_no_fecha_actual_ni_ano_inventado(self):
  with self.assertRaises(ValueError):ficha_aec(HTML.replace('2026-10-07','2026-12-07'),'',{})
 def test_curso_no_se_publica(self):
  self.assertEqual(ficha_aec(HTML.replace('Los días 23','Curso: Los días 23'),'',{}),[])
 def test_exclusivo_no_publica(self):
  self.assertEqual(ficha_aec(HTML.replace('Las entradas son sin cargo','Exclusivo para afiliados. Las entradas son sin cargo'),'',{}),[])
 def test_no_hardcode_fecha(self):
  e=ficha_aec(HTML.replace('23 y 24 de octubre','3 y 4 de noviembre'),'',{});self.assertEqual(e[0]['fecha'],'2026-11-03')
 def test_otra_seccion_no_se_publica(self):
  self.assertEqual(ficha_aec(HTML.replace('category-teatro','category-turismo'),'',{}),[])
 def test_primaria_reemplaza_acr_mismo_turno(self):
  e={**ficha_aec(HTML,'',{})[0],'origen':'Empleados de Comercio Rosario — Teatro AEC','evento_url':'https://www.aecrosario.org.ar/x/'}
  acr={**e,'nombre':'Ballroom Divah!','lugar':'Teatro AEC - Asoc. Empleados de Comercio','origen':'Agenda Cultural Rosario'}
  self.assertEqual(fusionar([acr],[e],set(),date(2026,10,18)),[e])
 def test_fallo_conserva(self):
  e=ficha_aec(HTML,'',{})[0];self.assertEqual(fusionar([e],[],set(),date(2026,10,18)),[e])
