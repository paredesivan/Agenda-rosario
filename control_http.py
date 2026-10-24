"""Transporte común: GET acotados, ritmo por host y pausas persistentes."""
import json
import os
import time
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
import requests
from requests.adapters import HTTPAdapter

ROOT = Path(__file__).resolve().parent
_LOCK = threading.RLock()


def atomico(path, datos):
    path = Path(path)
    temporal = path.with_suffix(path.suffix + '.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    os.replace(temporal, path)


class SesionControlada(requests.Session):
    def __init__(self, ruta=None, reloj=time.time, dormir=time.sleep):
        super().__init__()
        self.ruta = Path(ruta) if ruta else ROOT / 'estado_http.json'
        self.reloj, self.dormir = reloj, dormir
        self.cuentas = {}
        politica = ROOT / 'acceso_fuentes.json'
        self.politica = json.loads(politica.read_text()) if politica.exists() else {}
        config = ROOT / 'limites_consultas.json'
        self.config = json.loads(config.read_text()) if config.exists() else {}
        self.headers['User-Agent'] = 'AgendaRosario/4.0 (+https://salidasrosario.com.ar)'
        self.mount('https://', HTTPAdapter(max_retries=0))
        self.mount('http://', HTTPAdapter(max_retries=0))

    def send(self, request, **kwargs):
        if request.method not in ('GET', 'HEAD'):
            raise requests.RequestException('El recolector sólo permite GET/HEAD')
        dominio = urlsplit(request.url).hostname
        for host, revision in self.politica.get('dominios', {}).items():
            if dominio == host or (dominio or '').endswith('.' + host):
                if revision.get('consulta_automatica') is False:
                    raise requests.RequestException('Consulta automática desactivada por condiciones de uso: ' + host)
                if any(urlsplit(request.url).path.startswith(ruta) for ruta in revision.get('rutas_excluidas', [])):
                    raise requests.RequestException('Ruta excluida por robots documentado: ' + host)
        regla = {**self.config.get('general', {}), **self.config.get('hosts', {}).get(dominio, {})}
        demora = max(1.5, float(regla.get('pausa_segundos', 1.5)))
        # Una llamada y, como máximo, un reintento; redirects también pasan por send.
        with _LOCK:
            for intento in range(2):
                try:
                    estado = json.loads(self.ruta.read_text()) if self.ruta.exists() else {}
                except (ValueError, OSError) as exc:
                    raise requests.RequestException('Estado HTTP ilegible; consulta suspendida') from exc
                previo = estado.get(dominio, {})
                if previo.get('pausado_hasta', 0) > self.reloj():
                    raise requests.RequestException('Fuente en pausa por HTTP 403/429')
                if self.cuentas.get(dominio, 0) >= int(regla.get('max_consultas', 120)):
                    raise requests.RequestException('Presupuesto de consultas agotado para esta fuente')
                espera = demora - (self.reloj() - previo.get('ultima', 0))
                if espera > 0:
                    self.dormir(espera)
                self.cuentas[dominio] = self.cuentas.get(dominio, 0) + 1
                previo.update(ultima=self.reloj())
                estado[dominio] = previo
                atomico(self.ruta, estado)
                kwargs['timeout'] = (min(10, float(regla.get('conexion_segundos', 10))),
                                     min(25, float(regla.get('lectura_segundos', 25))))
                kwargs['stream'] = True
                try:
                    respuesta = super().send(request, **kwargs)
                    if respuesta.status_code in (403, 429):
                        pausa = 86400
                        valor = respuesta.headers.get('Retry-After', '')
                        if valor.isdigit():
                            pausa = max(pausa, int(valor))
                        elif valor:
                            try:
                                pausa = max(pausa, parsedate_to_datetime(valor).timestamp() - self.reloj())
                            except (ValueError, TypeError, OverflowError):
                                pass
                        previo['pausado_hasta'] = self.reloj() + pausa
                        atomico(self.ruta, estado)
                        respuesta.close()
                        respuesta.raise_for_status()
                    if respuesta.status_code in (500, 502, 503, 504) and intento == 0:
                        respuesta.close()
                        continue
                    contenido, total, inicio = [], 0, self.reloj()
                    for bloque in respuesta.iter_content(65536):
                        total += len(bloque)
                        if total > int(regla.get('max_bytes', 8_000_000)) or self.reloj() - inicio > 45:
                            respuesta.close()
                            raise requests.RequestException('Respuesta excede el tamaño o tiempo permitido')
                        contenido.append(bloque)
                    respuesta._content = b''.join(contenido)
                    respuesta._content_consumed = True
                    previo['http'] = respuesta.status_code
                    atomico(self.ruta, estado)
                    return respuesta
                except (requests.ConnectionError, requests.Timeout):
                    if intento:
                        raise
                finally:
                    previo['ultima'] = self.reloj()
                    atomico(self.ruta, estado)
        raise requests.RequestException('Consulta fallida')

