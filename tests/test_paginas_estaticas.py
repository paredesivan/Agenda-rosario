import json
import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from generar_paginas import generar, ruta_evento, estructurado, INICIO, FIN

EVENTO = {'fecha':'2099-10-30','hora':'20:00','nombre':'Obra <especial>', 'lugar':'Sala',
          'evento_url':'https://example.org/obra', 'direccion':'Calle 100', 'precio':0}


class Paginas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'index.html').write_text('<html><body>'+INICIO+FIN+'</body></html>')
        self.datos([EVENTO])

    def datos(self,eventos):
        (self.root/'eventos.json').write_text(json.dumps({'eventos':eventos}))

    def test_paginas_schema_sitemap_y_agenda_sin_js(self):
        r=generar(self.root,hoy='2099-10-24');self.assertEqual(r['funciones'],1)
        soup=BeautifulSoup((self.root/ruta_evento(EVENTO)).read_text(),'html.parser')
        self.assertEqual(soup.h1.text, EVENTO['nombre'])
        schema=json.loads(soup.select_one('script[type="application/ld+json"]').text)
        self.assertEqual(schema['startDate'],'2099-10-30T20:00:00-03:00')
        self.assertEqual(schema['location']['address']['streetAddress'],'Calle 100')
        self.assertNotIn('offers',schema)
        self.assertIn('https://salidasrosario.com.ar/'+ruta_evento(EVENTO),(self.root/'sitemap.xml').read_text())
        self.assertIn(EVENTO['nombre'],BeautifulSoup((self.root/'index.html').read_text(),'html.parser').text)

    def test_no_inventa_hora_estado_ni_precio(self):
        self.assertIsNone(estructurado({**EVENTO,'hora':'Horario a confirmar'},'https://example.org'))
        self.assertIsNone(estructurado({**EVENTO,'revision_pendiente':True},'https://example.org'))

    def test_no_copia_sinopsis_y_escape_seguro(self):
        e={**EVENTO,'nombre':'</script><script>alert(1)</script>', 'descripcion':'sinopsis que no se copia'}
        self.datos([e]);generar(self.root,hoy='2099-10-24')
        source=(self.root/ruta_evento(e)).read_text()
        soup=BeautifulSoup(source,'html.parser')
        self.assertEqual(len(soup.find_all('script')),1)
        self.assertNotIn('sinopsis que no se copia',source)
        self.assertEqual(json.loads(soup.script.text)['name'],e['nombre'])

    def test_repetible_retira_vencidas_y_respeta_archivos_ajenos(self):
        generar(self.root,hoy='2099-10-24')
        before=(self.root/ruta_evento(EVENTO)).read_bytes()
        generar(self.root,hoy='2099-10-24')
        self.assertEqual(before,(self.root/ruta_evento(EVENTO)).read_bytes())
        (self.root/'fichas/ajena.html').write_text('manual')
        generar(self.root,hoy='2099-10-31')
        self.assertFalse((self.root/ruta_evento(EVENTO)).exists())
        self.assertTrue((self.root/'fichas/ajena.html').exists())

    def test_no_sobrescribe_paginas_editadas_manualmente(self):
        generar(self.root,hoy='2099-10-24')
        path=self.root/ruta_evento(EVENTO);path.write_text('editado manualmente')
        with self.assertRaises(ValueError): generar(self.root,hoy='2099-10-24')
        self.assertEqual(path.read_text(),'editado manualmente')
