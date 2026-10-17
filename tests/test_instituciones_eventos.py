import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from fuentes_ampliadas import ficha, listado, revisar, actualizar
from instituciones_eventos import ficha_gamma, ficha_mec

URL = 'https://institucion.test/pacientes/charlas-a-la-comunidad/charla-nueva'
GAMMA = {'nombre':'Hospital de prueba', 'habilitada':True, 'tipo':'oficial',
         'listado':'https://institucion.test/pacientes/charlas-a-la-comunidad',
         'adaptador':'gamma_comunidad', 'patron_ficha':r'^/pacientes/charlas-a-la-comunidad/[^/]+$',
         'selector':'main a[href]', 'max_fichas_dia':4}

def charla(fecha='28 de octubre de 2026 - 18:30 a 20:00 hs.', sede='Auditorio (Calle 1234, Rosario)', extra=''):
    return f'<main><article><div><span>Charlas a la comunidad</span><h1>Actividad nueva</h1><ul><li>{fecha}</li><li>{sede}</li><li>Evento presencial</li></ul><a>Inscribirme</a></div><section class="markdown"><blockquote>ACTIVIDAD SIN CARGO | CUPOS LIMITADOS</blockquote>{extra}</section></article></main>'

MEC_URL='https://institucion.test/agenda/actividad-nueva/'
def mec(fecha='Oct 30 2026', cuerpo=None):
    cuerpo = cuerpo or 'El viernes 30 de octubre, a las 20 hs. Entrada libre y gratuita en el Centro Cultural, Calle 2345, Rosario.'
    return f'<article class="mec-single-event"><h1>Concierto nuevo</h1><div class="mec-single-event-description"><p>{cuerpo}</p></div></article><article class="mec-event-article"><span class="mec-start-date-label">{fecha}</span><h4 class="mec-event-title"><a href="{MEC_URL}">Concierto nuevo</a></h4></article>'

class Acceso:
    def __init__(self, pages):
        self.pages=pages; self.cache={}; self.calls=[]
    def leer_datos(self,url,parser,horas=24):
        self.calls.append(url)
        v=self.pages[url]
        if isinstance(v,Exception):raise v
        return parser(v,url)

class Instituciones(unittest.TestCase):
    def test_charla_completa_inscripcion_y_cupos(self):
        e=ficha(charla(),URL,GAMMA)[0]
        self.assertEqual((e['fecha'],e['hora'],e['hora_fin']),('2026-10-28','18:30','20:00'))
        self.assertEqual(e['direccion'],'Calle 1234')
        self.assertEqual(e['precio'],0)
        self.assertIn('inscripción',e['descripcion'])
        self.assertIn('Cupos limitados',e['descripcion'])
        self.assertNotIn('image',e)

    def test_ficha_dinamica_y_solo_enlaces_propios(self):
        links=f'<main><a href="{URL}">nueva</a><a href="https://otro.test/pacientes/charlas-a-la-comunidad/otra">otra</a></main>'
        self.assertEqual(listado(links,GAMMA['listado'],GAMMA),[{'url':URL,'referencia':''}])

    def test_fecha_sin_ano_hora_o_invalida_se_rechaza(self):
        for f in ['28 de octubre - 18:30 hs.','28 de octubre de 2026','31 de febrero de 2026 - 18:30 hs.','28 de octubre de 2026 - 99:30 hs.','28 de octubre de 2026 - 20:00 a 18:00 hs.']:
            with self.subTest(f=f),self.assertRaises(ValueError):ficha_gamma(charla(fecha=f),URL,GAMMA)

    def test_ciudad_no_se_infiere_del_hospital(self):
        with self.assertRaises(ValueError):ficha_gamma(charla(sede='Auditorio (Calle 1234, Santa Fe)'),URL,GAMMA)

    def test_profesionales_no_se_publican(self):
        with self.assertRaises(ValueError):ficha_gamma(charla(extra='Exclusiva para profesionales.'),URL,GAMMA)

    def test_virtual_no_se_publica_como_presencial(self):
        with self.assertRaises(ValueError):ficha_gamma(charla().replace('Evento presencial','Evento virtual'),URL,GAMMA)

    def test_cancelacion(self):
        self.assertEqual(ficha_gamma(charla(extra='Actividad suspendida.'),URL,GAMMA),[{'cancelado':True}])

    def test_mec_ano_del_evento_y_direccion_en_cuerpo(self):
        e=ficha_mec(mec(),MEC_URL,{})[0]
        self.assertEqual((e['fecha'],e['hora'],e['lugar']),('2026-10-30','20:00','Centro Cultural'))

    def test_no_inferir_ano_de_publicacion_o_recomendacion(self):
        raw=mec().replace(MEC_URL,'https://institucion.test/agenda/otro/')+'<meta property="article:published_time" content="2026-10-01">'
        with self.assertRaises(ValueError):ficha_mec(raw,MEC_URL,{})

    def test_rango_no_se_expande_ni_se_inventa_horario(self):
        for raw in [mec(fecha='Oct 20 - 24 2026'),mec().replace('a las 20 hs','por la tarde'),mec().replace('Calle 2345, Rosario','Calle 2345, Funes')]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):ficha_mec(raw,MEC_URL,{})

    def test_acceso_ambiguo_queda_candidato(self):
        cfg={'fuentes':[{**GAMMA,'adaptador':'institucion_mec','patron_ficha':r'^/agenda/[^/]+/$'}]}
        f=cfg['fuentes'][0];pages={f['listado']:f'<main><a href="{MEC_URL}">nueva</a></main>',MEC_URL:mec(cuerpo='Reunión interna a las 20 hs.')}
        nuevos,candidatos,estados,urls=revisar(cfg,Acceso(pages),date(2026,10,17))
        self.assertFalse(nuevos);self.assertTrue(candidatos);self.assertFalse(urls)

    def test_limite_diario_persiste_y_cambio_horario_se_actualiza_al_otro_dia(self):
        cfg={'fuentes':[{**GAMMA,'max_fichas_dia':1}]}
        a=Acceso({GAMMA['listado']:f'<main><a href="{URL}">nueva</a></main>',URL:charla()})
        self.assertEqual(len(revisar(cfg,a,date(2026,10,17))[0]),1)
        revisar(cfg,a,date(2026,10,17));self.assertEqual(a.calls.count(URL),1)
        a.pages[URL]=charla().replace('18:30','19:00')
        self.assertEqual(revisar(cfg,a,date(2026,10,18))[0][0]['hora'],'19:00')

    def test_actualizar_preserva_precio_condiciones_y_anteriores_si_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'fuentes_ampliadas.json').write_text(json.dumps({'fuentes':[GAMMA]}));(p/'eventos.json').write_text('{"eventos":[]}')
            a=Acceso({GAMMA['listado']:f'<main><a href="{URL}">nueva</a></main>',URL:charla()})
            actualizar(p,a,date(2026,10,17));e=json.loads((p/'eventos.json').read_text())['eventos'][0]
            self.assertEqual(e['precio'],0);self.assertIn('inscripción',e['descripcion'])
            a.pages[URL]=ValueError('red fallida')
            actualizar(p,a,date(2026,10,18));self.assertEqual(json.loads((p/'eventos.json').read_text())['eventos'],[e])

if __name__=='__main__':unittest.main()
