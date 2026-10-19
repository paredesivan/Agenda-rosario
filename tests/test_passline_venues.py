import json
import unittest
from pathlib import Path
from datetime import date
from fuentes_ampliadas import listado, ficha, fusionar, revisar
from fuente_passline_venues import ficha_passline

URL='https://www.passline.com/eventos/ave-rapaz-homenaje-a-heroes-del-silencio-y-bunbury-en-rosario'
FUENTE={'adaptador':'passline_venue','sede':'Floyd Bar'}
HTML=(Path(__file__).parent/'fixtures/passline/floyd_factual.html').read_text()

class PasslineVenuesTests(unittest.TestCase):
    def test_html_real_datos_minimos_y_localidad_mal_etiquetada(self):
        e=ficha(HTML,URL,FUENTE)[0]
        self.assertEqual((e['fecha'],e['hora'],e['lugar']),('2026-11-21','20:30','Floyd Bar'))
        self.assertIsNone(e['precio'])
        self.assertNotIn('hora_fin',e)

    def test_rechaza_rosario_en_titulo_pero_sede_otro_lugar(self):
        h=HTML.replace('Santa Fe, ROSARIO','Córdoba, CORDOBA').replace('S2000 Rosario, Santa Fe','Córdoba, Córdoba')
        with self.assertRaisesRegex(ValueError,'Localidad'):
            ficha_passline(h,URL,FUENTE)

    def test_no_acepta_otra_provincia(self):
        with self.assertRaisesRegex(ValueError,'Provincia'):
            ficha_passline(HTML.replace('"addressRegion": ""','"addressRegion": "Cordoba"'),URL,FUENTE)

    def test_sin_horario(self):
        e=ficha_passline(HTML.replace('2026-11-21T20:30:00-03:00','2026-11-21'),URL,FUENTE)[0]
        self.assertEqual(e['hora'],'Horario a confirmar')

    def test_suspension(self):
        self.assertEqual(ficha_passline(HTML.replace('EventScheduled','EventCancelled'),URL,FUENTE),[{'cancelado':True}])

    def test_excluye_formacion(self):
        h=HTML.replace('AVE RAPAZ / HOMENAJE A HÉROES DEL SILENCIO Y BUNBURY EN ROSARIO','Taller de guitarra')
        self.assertEqual(ficha_passline(h,URL,FUENTE),[])

    def test_no_toma_recomendacion_otra_ficha(self):
        with self.assertRaisesRegex(ValueError,'correspondientes'):
            ficha_passline(HTML,URL+'-otro',FUENTE)

    def test_respeta_sede(self):
        with self.assertRaisesRegex(ValueError,'sala'):
            ficha_passline(HTML,URL,{'sede':'Otra sala'})

    def test_restricciones_de_edad(self):
        e=ficha_passline(HTML+'<h5>Evento solo para Mayores de 18 Años.</h5>',URL,FUENTE)[0]
        self.assertIn('mayores de 18 años',e['descripcion'])

    def test_sufijo_edad_del_titulo_no_descarta_la_ficha(self):
        h=HTML.replace('</h1>',' (+18)</h1>')
        self.assertEqual(len(ficha_passline(h,URL,FUENTE)),1)

    def test_html_visible_con_schema_vacio(self):
        h=f'''<meta property="og:url" content="{URL}">
        <div id="primer_contenedor"><h1 class="titulo_evento">Noche (+18)</h1>
        <li id="li_fecha_inicio">Sábado 31 de Octubre 2026 - 23:30 hrs.</li></div>
        <p><strong>Floyd Bar</strong><br>Dorrego 1362<br>Santa Fe, ROSARIO</p>
        <script type="application/ld+json"></script>'''
        e=ficha_passline(h,URL,FUENTE)[0]
        self.assertEqual((e['nombre'],e['fecha'],e['hora']),('Noche','2026-10-31','23:30'))
        with self.assertRaises(ValueError):
            ficha_passline(h,URL+'-otro',FUENTE)

    def test_schema_vacio_sin_localidad_no_importa(self):
        h=f'''<meta property="og:url" content="{URL}">
        <div id="primer_contenedor"><h1 class="titulo_evento">Rosario en concierto</h1>
        <li id="li_fecha_inicio">Sábado 31 de Octubre 2026 - 23:30 hrs.</li></div>
        <p><strong>Floyd Bar</strong><br>Santa Fe, SANTA FE</p>'''
        with self.assertRaises(ValueError):ficha_passline(h,URL,FUENTE)

    def test_listado_deduplica_movil_desktop_y_excluye_externos(self):
        h=f'<div class="card"><a href="{URL}">x</a><a href="{URL}">x</a><a href="https://externo.test/eventos/x">x</a></div>'
        f={'selector':'.card a[href]','patron_ficha':'^/eventos/[^/]+/?$'}
        self.assertEqual(len(listado(h,'https://www.passline.com/venue/floyd-bar',f)),1)

    def test_fallo_conserva_eventos(self):
        anterior={**ficha_passline(HTML,URL,FUENTE)[0],'origen':'Passline — Floyd Bar','evento_url':URL}
        self.assertEqual(fusionar([anterior],[],set(),date(2026,10,18)),[anterior])

    def test_no_duplica_funcion_ya_publicada(self):
        e={**ficha_passline(HTML,URL,FUENTE)[0],'origen':'Passline','evento_url':URL}
        self.assertEqual(len(fusionar([e],[{**e,'origen':'Passline — Floyd Bar'}],set(),date(2026,10,18))),1)

if __name__=='__main__':unittest.main()
