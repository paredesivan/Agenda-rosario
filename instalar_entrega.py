"""Instalador reutilizable: preflight completo, idempotencia y escritura reversible."""
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def ruta_segura(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or p.parts[0] in ('.git', '.github'):
        raise ValueError('Ruta de instalación no permitida')
    dest = root / p
    if dest.is_symlink() or not dest.resolve().is_relative_to(root.resolve()):
        raise ValueError('La instalación no puede seguir enlaces fuera del proyecto')
    return dest


def aplicar(payload, root=None):
    root = Path(root or Path.cwd())
    receipt = root / '.agenda/entrega.json'
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if previous.get('version') == payload['version']:
        print('La entrega ya está instalada. Se conservan las modificaciones posteriores.')
        return False
    files = payload['files']
    backups = {}
    for name, content in files.items():
        path = ruta_segura(root, name)
        original = path.read_bytes() if path.exists() else None
        digest = blob(original) if original is not None else None
        expected = payload.get('expected', {}).get(name, [None])
        if digest not in expected + [blob(content.encode('utf-8'))]:
            raise ValueError(f'{name} cambió desde la revisión. No se modificó ningún archivo; hay que adaptar esta entrega a la versión nueva.')
        backups[name] = original
    reports = root / 'reportes'
    reports.mkdir(exist_ok=True)
    public_backup = reports / 'respaldo_publicado.json.gz'
    if not public_backup.exists():
        publicos = {name: (root / name).read_text(encoding='utf-8')
                    for name in ('index.html', 'agenda.js', 'estilos.css', 'eventos.json', 'estado.html', 'estado_agenda.json')
                    if (root / name).exists()}
        with gzip.open(public_backup, 'wt', encoding='utf-8') as f:
            json.dump({'capturado': datetime.now(timezone.utc).isoformat(), 'archivos': publicos}, f, ensure_ascii=False)
    with gzip.open(reports / 'respaldo_instalacion.json.gz', 'wt', encoding='utf-8') as f:
        json.dump({name: data.decode('utf-8') if data is not None else None for name, data in backups.items()}, f, ensure_ascii=False)
    written = []
    try:
        for name, content in files.items():
            path = ruta_segura(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                f.write(content.encode('utf-8'))
            try:
                os.replace(f.name, path)
            finally:
                Path(f.name).unlink(missing_ok=True)
            written.append(name)
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps({'version': payload['version'], 'archivos': sorted(files),
                                      'instalada': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    except Exception:
        for name in reversed(written):
            path = root / name
            if backups[name] is None: path.unlink(missing_ok=True)
            else: path.write_bytes(backups[name])
        raise
    print(f"Entrega {payload['version']}: {len(files)} archivos preparados. Se publicarán sólo después de pasar las pruebas.")
    return True
