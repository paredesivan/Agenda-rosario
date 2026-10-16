"""Presupuesto de transferencia sin comprimir (Pages puede comprimirlo)."""
import gzip
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
LIMITES = {'eventos.json': 1_000_000, 'agenda.js': 100_000,
           'estilos.css': 80_000, 'index.html': 40_000}


def medir(root=ROOT):
    filas = []
    for nombre, limite in LIMITES.items():
        contenido = (root / nombre).read_bytes()
        filas.append({'archivo': nombre, 'bytes': len(contenido),
                      'gzip_estimado_bytes': len(gzip.compress(contenido)),
                      'limite_bytes': limite, 'cumple': len(contenido) <= limite})
    return filas


if __name__ == '__main__':
    datos = medir()
    (ROOT / 'reportes').mkdir(exist_ok=True)
    (ROOT / 'reportes/peso.json').write_text(json.dumps(datos, indent=2) + '\n')
    print(json.dumps(datos, indent=2))
    if not all(f['cumple'] for f in datos):
        raise SystemExit('Se superó el presupuesto de tamaño')
