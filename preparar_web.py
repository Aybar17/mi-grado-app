"""Empaquetar presentación estática: únicamente recursos públicos ficticios."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent


def build_site():
    from empaquetar_web import build, VERSION
    bundle = build()
    destination = ROOT/'output/web-publica'/VERSION
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle['web']) as archive:
        for name in archive.namelist():
            target = (destination/name).resolve()
            if not target.is_relative_to(destination.resolve()): raise ValueError('Ruta ajena al sitio estático.')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    return destination


if __name__ == '__main__': print(json.dumps({'folder':str(build_site()),'published':False},ensure_ascii=False))
