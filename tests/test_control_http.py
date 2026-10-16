import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
from control_http import SesionControlada


def respuesta(status=200, contenido=b'ok', headers=None):
    r = requests.Response()
    r.status_code, r.raw, r.headers = status, io.BytesIO(contenido), headers or {}
    r.url = 'https://fuente.test/'
    return r


class Transporte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ahora = 1000000
        self.esperas = []
        def dormir(segundos):
            self.esperas.append(segundos)
            self.ahora += segundos
        self.ruta = Path(self.tmp.name) / 'http.json'
        self.sesion = SesionControlada(self.ruta, lambda: self.ahora, dormir)
        self.sesion.config = {'general': {'pausa_segundos': 5}}

    def test_timeout_y_un_solo_reintento(self):
        with patch('requests.Session.send', side_effect=[requests.Timeout(), respuesta()]) as envio:
            self.assertEqual(self.sesion.get('https://fuente.test/').text, 'ok')
            self.assertEqual(envio.call_count, 2)
            self.assertEqual(envio.call_args.kwargs['timeout'], (10, 25))
            self.assertGreaterEqual(sum(self.esperas), 5)

    def test_fallos_permanentes_no_multiplican_reintentos(self):
        with patch('requests.Session.send', side_effect=requests.Timeout()) as envio:
            with self.assertRaises(requests.Timeout):
                self.sesion.get('https://fuente.test/')
            self.assertEqual(envio.call_count, 2)

    def test_503_reintenta_404_no(self):
        with patch('requests.Session.send', side_effect=[respuesta(503), respuesta(200)]) as envio:
            self.assertEqual(self.sesion.get('https://fuente.test/').status_code, 200)
            self.assertEqual(envio.call_count, 2)
        with patch('requests.Session.send', return_value=respuesta(404)) as envio:
            self.assertEqual(self.sesion.get('https://fuente.test/otra').status_code, 404)
            self.assertEqual(envio.call_count, 1)

    def test_403_429_persisten_y_respetan_retry_after(self):
        for codigo in (403, 429):
            self.ruta.unlink(missing_ok=True)
            with self.subTest(codigo=codigo), patch('requests.Session.send', return_value=respuesta(codigo, headers={'Retry-After': '172800'})) as envio:
                with self.assertRaises(requests.HTTPError):
                    self.sesion.get('https://fuente.test/')
                otra = SesionControlada(self.ruta, lambda: self.ahora, lambda _: None)
                with self.assertRaises(requests.RequestException):
                    otra.get('https://fuente.test/nueva')
                self.assertEqual(envio.call_count, 1)
                self.ahora += 86401
                with self.assertRaises(requests.RequestException):
                    otra.get('https://fuente.test/nueva')

    def test_presupuesto_por_host_y_tamano(self):
        self.sesion.config = {'general': {'max_consultas': 1, 'max_bytes': 2}}
        with patch('requests.Session.send', return_value=respuesta(contenido=b'muy grande')) as envio:
            with self.assertRaises(requests.RequestException):
                self.sesion.get('https://fuente.test/')
            with self.assertRaises(requests.RequestException):
                self.sesion.get('https://fuente.test/otra')
            self.assertEqual(envio.call_count, 1)

    def test_pausa_entre_procesos_y_dominio_independiente(self):
        with patch('requests.Session.send', side_effect=lambda *a, **kw: respuesta()):
            self.sesion.get('https://fuente.test/')
            self.sesion.get('https://otra.test/')
            self.assertEqual(self.esperas, [])
            otra = SesionControlada(self.ruta, lambda: self.ahora, self.sesion.dormir)
            otra.config = self.sesion.config
            otra.get('https://fuente.test/segunda')
            self.assertEqual(self.esperas, [5])

class IntegracionTransporte(unittest.TestCase):
    def test_http_real_reintento_y_redireccion(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        contador = {}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                contador[self.path] = contador.get(self.path, 0) + 1
                if self.path == '/redireccion':
                    self.send_response(302)
                    self.send_header('Location', '/ok')
                    self.end_headers()
                    return
                status = 503 if self.path == '/inestable' and contador[self.path] == 1 else 200
                self.send_response(status)
                self.end_headers()
                self.wfile.write(b'contenido real')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        hilo = threading.Thread(target=server.serve_forever, daemon=True)
        hilo.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ahora = [1000000]
                def dormir(n):
                    ahora[0] += n
                session = SesionControlada(Path(tmp) / 'http.json', lambda: ahora[0], dormir)
                base = f'http://127.0.0.1:{server.server_port}'
                self.assertEqual(session.get(base + '/inestable').text, 'contenido real')
                self.assertEqual(contador['/inestable'], 2)
                self.assertEqual(session.get(base + '/redireccion').text, 'contenido real')
                self.assertEqual(contador['/ok'], 1)
                session.close()
        finally:
            server.shutdown()
            server.server_close()
            hilo.join(2)
