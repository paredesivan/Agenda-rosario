import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from actualizar_eventos import sin_repetidos
from fuentes_adicionales import listado_acr, revisar, Acceso, acr_vigente

URL = 'https://www.agendaculturalrosario.com.ar/agenda'
DIA = (date.today() + timedelta(days=2)).isoformat()
def ficha(**extra):
    f = dict(title='Actividad futura de prueba', venueName='Sala de Prueba', slug='actividad-futura',
             eventDate=DIA, eventTime='20:00', status='approved', isSuspended=False, occurrences=[],
             ticketingUrl='https://rosario.gob.ar/actividad', submitterEmail='privado@example.invalid', details='NO COPIAR')
    return {**f, **extra}
def html_flight(fichas):
    payload = '14:["$","$L1",null,' + json.dumps({'initialEvents': fichas}) + ']'
    return BeautifulSoup(''.join('<script>self.__next_f.push(' + json.dumps([1, p]) + ')</script>'
                                for p in [payload[:50],payload[50:]]), 'html.parser')
class ACR(unittest.TestCase):
    def test_html_fragmentado_y_lista_blanca(self):
        salida = listado_acr(html_flight([ficha()]), URL)
        self.assertEqual(len(salida),1)
        self.assertEqual(salida[0]['fecha'],DIA)
        self.assertEqual(salida[0]['referencia'],URL.replace('/agenda','/eventos/actividad-futura'))
        for dato in ['privado','NO COPIAR','precio']:
            self.assertNotIn(dato,json.dumps(salida))
    def test_funciones_explicitas_sin_inventar_recurrencias(self):
        turnos = [{'date':DIA,'time':'18:00','status':'scheduled'},
                  {'date':DIA,'time':'21:00','status':'scheduled'},
                  {'date':DIA,'time':'22:00','status':'cancelled'},
                  {'date':'2099-02-30','time':'21:00','status':'scheduled'}]
        self.assertEqual([h['hora'] for h in listado_acr(html_flight([ficha(occurrences=turnos)]),URL)],['18:00','21:00'])
    def test_suspension_incompletos_y_cambio_formato(self):
        self.assertEqual(listado_acr(html_flight([ficha(isSuspended=True),ficha(eventTime=None)]),URL),[])
        self.assertEqual(listado_acr(html_flight([]),URL),[])
        with self.assertRaises(ValueError):listado_acr(BeautifulSoup('<main>formato nuevo</main>','html.parser'),URL)
    def test_importa_todas_sin_tope_cuarenta(self):
        fichas = [ficha(title=f'Actividad {i}',slug=f'actividad-{i}') for i in range(55)]
        self.assertEqual(len(listado_acr(html_flight(fichas),URL)),55)
    def test_integracion_publica_directa_sin_visitar_sala(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'fuentes_adicionales.json').write_text(json.dumps({'dominios_oficiales_existentes':[],
                'fuentes':[{'nombre':'Agenda Cultural Rosario','url':URL,'consulta_automatica':True}]}))
            acceso = Acceso({})
            def leer(url,parser,tipo='listado'):
                self.assertEqual(url,URL)
                return listado_acr(html_flight([ficha()]),URL)
            acceso.leer=leer
            with patch('fuentes_adicionales.ROOT',root):nuevos=revisar(date.today(),[],{},acceso)
            self.assertEqual(len(nuevos),1)
            self.assertEqual(nuevos[0]['evento_url'],URL.replace('/agenda','/eventos/actividad-futura'))
            self.assertIn('Actividad cultural:',nuevos[0]['descripcion'])
            self.assertEqual(nuevos[0]['origen'],'Agenda Cultural Rosario')
            self.assertFalse(nuevos[0]['fuente_verificada'])
            self.assertEqual(json.loads((root/'candidatos_fuentes_adicionales.json').read_text())['candidatos'],[])

    def test_suspension_en_titulo_aunque_indicador_sea_falso(self):
        for titulo in ['Actividad — FUNCIÓN SUSPENDIDA','Cancelado: concierto','Evento postergado']:
            self.assertEqual(listado_acr(html_flight([ficha(title=titulo)]),URL),[])
        f=ficha(occurrences=[{'date':DIA,'time':'20:00','status':'scheduled','note':'Función suspendida'}])
        self.assertEqual(listado_acr(html_flight([f]),URL),[])

    def test_finalizacion_y_funcion_en_curso_con_fin_publicado(self):
        from datetime import datetime
        from actualizar_eventos import ZONA
        ahora=datetime(2026,10,17,20,30,tzinfo=ZONA)
        f=ficha(eventDate='2026-10-17',eventTime='20:00')
        self.assertEqual(listado_acr(html_flight([f]),URL,ahora),[])
        f['occurrences']=[{'date':'2026-10-17','time':'20:00','endTime':'21:00','status':'scheduled'}]
        self.assertEqual(len(listado_acr(html_flight([f]),URL,ahora)),1)
        self.assertEqual(listado_acr(html_flight([f]),URL,ahora.replace(hour=21,minute=0)),[])
        f['occurrences']=[{'date':'2026-10-17','time':'23:00','endTime':'01:00','status':'scheduled'}]
        self.assertEqual(len(listado_acr(html_flight([f]),URL,ahora.replace(day=18,hour=0,minute=30))),1)

    def test_vencimiento_se_revisa_tambien_con_cache(self):
        from datetime import datetime
        from actualizar_eventos import ZONA
        self.assertFalse(acr_vigente({'fecha':'2026-10-17','hora':'20:00'},datetime(2026,10,17,21,tzinfo=ZONA)))

class Duplicados(unittest.TestCase):
    def test_parque_espana_variantes_y_fuente_directa(self):
        a={'fecha':DIA,'hora':'20:00','nombre':'Impresiones Sonoras - Ensamble Municipal de Vientos',
           'lugar':'Parque España','origen':'Municipalidad de Rosario','evento_url':'https://rosario.gob.ar/actividad'}
        b={**a,'nombre':'Impresiones Sonoras – Ensamble Municipal de Vientos','lugar':'Centro Cultural Parque de España',
           'origen':'Centro Cultural Parque de España','evento_url':'https://ccpe.org.ar/actividad'}
        for orden in ([a,b],[b,a]):self.assertEqual(sin_repetidos(orden),[b])
        for cambio in [{'hora':'21:00'},{'lugar':'Parque Independencia'}]:
            self.assertEqual(len(sin_repetidos([a,{**b,**cambio}])),2)
        self.assertEqual(len(sin_repetidos([{**a,'lugar':'Sala 1'},{**b,'lugar':'Sala 2'}])),2)

class AuditoriaConfiguracion(unittest.TestCase):
    def test_fuente_acr_incluida_en_auditoria_semanal(self):
        import auditar_fuentes
        self.assertIn(URL, auditar_fuentes.inventario()['www.agendaculturalrosario.com.ar'])

class RespaldoDinamicoACR(unittest.TestCase):
    def test_prioriza_oficial_y_publica_otros_sin_lista_de_eventos(self):
        from fuentes_adicionales import respaldo_acr
        oficial={'fecha':DIA,'hora':'20:00','nombre':'Una aventura futura - compañía invitada',
                 'lugar':'Teatro Fundación Imaginario','evento_url':'https://oficial.example/funcion',
                 'origen':'Sala oficial','descripcion':'Descripción oficial','precio':2500}
        ficha_acr=ficha(title='Una aventura futura',venueName='Teatro Imaginario')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'fuentes_adicionales.json').write_text(json.dumps({
                'dominios_oficiales_existentes':['oficial.example'],
                'fuentes':[{'nombre':'Agenda Cultural Rosario','url':URL,'consulta_automatica':True}]}))
            acceso=Acceso({})
            acceso.leer=lambda url,parser,tipo='listado':listado_acr(html_flight([
                ficha_acr,ficha(title='Otra actividad nueva',slug='otra-actividad-nueva')]),URL)
            with patch('fuentes_adicionales.ROOT',root):
                nuevos=revisar(date.today(),[oficial],{},acceso)
                self.assertEqual([e['nombre'] for e in nuevos],['Otra actividad nueva'])
                self.assertEqual(oficial['evento_url'],'https://oficial.example/funcion')
                self.assertEqual(oficial['precio'],2500)
                self.assertEqual(oficial['descripcion'],'Descripción oficial')
                self.assertIn('Agenda Cultural Rosario',oficial['descubrimiento_fuentes'])
                # En otra ejecución, sin respaldo disponible, ambas usan ACR.
                nuevos=revisar(date.today(),[],{},acceso)
                self.assertEqual(len(nuevos),2)
                self.assertTrue(all(e['evento_url'].startswith(URL.replace('/agenda','/eventos/')) for e in nuevos))
        hecho={'fecha':DIA,'hora':'20:00','nombre':'Una aventura futura','lugar':'Teatro Imaginario'}
        self.assertIs(respaldo_acr(hecho,[oficial]),oficial)
        self.assertIsNone(respaldo_acr({**hecho,'hora':'21:00'},[oficial]))
        self.assertIsNone(respaldo_acr({**hecho,'lugar':'Teatro Distinto'},[oficial]))
        self.assertIsNone(respaldo_acr({**hecho,'lugar':'Teatro Imaginario Sala 2'},[{**oficial,'lugar':'Teatro Imaginario Sala 1'}]))

    def test_medio_no_se_considera_fuente_oficial_por_coincidir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'fuentes_adicionales.json').write_text(json.dumps({
                'dominios_oficiales_existentes':['oficial.example'],
                'fuentes':[{'nombre':'Agenda Cultural Rosario','url':URL,'consulta_automatica':True}]}))
            acceso=Acceso({});acceso.leer=lambda *args:listado_acr(html_flight([ficha()]),URL)
            noticia={'fecha':DIA,'hora':'20:00','nombre':'Actividad futura de prueba',
                     'lugar':'Sala de Prueba','evento_url':'https://medio.example/noticia'}
            with patch('fuentes_adicionales.ROOT',root):nuevos=revisar(date.today(),[noticia],{},acceso)
            self.assertEqual(len(nuevos),1)
            self.assertEqual(nuevos[0]['origen'],'Agenda Cultural Rosario')
