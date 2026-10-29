"""Construir un ZIP Windows independiente de Python, con recursos explícitos."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.9.0-rc.3')
    parser.add_argument('--experimental-exe', action='store_true', help='Construcción PyInstaller para investigación; puede ser bloqueada por Windows.')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9._-]+', args.version): parser.error('Versión no válida')
    if sys.platform != 'win32': parser.error('Construye la aplicación Windows en Windows.')
    if not args.experimental_exe:
        from empaquetar_portable import build_portable
        build_portable(args.version)
        return
    output = ROOT / 'output' / 'windows'
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(output), '--workpath', str(ROOT / 'output' / 'packaging-build'),
                    str(ROOT / 'Mi grado.spec')], check=True, cwd=ROOT)
    folder = output / 'Mi grado'
    for name in ['README.md', 'ATTRIBUTION.md', 'CONTRIBUTING.md', 'LICENSE']:
        shutil.copyfile(ROOT / name, folder / name)
    shutil.copyfile(ROOT / 'docs' / 'PRUEBA_CON_AMIGOS.md', folder / 'EMPEZAR.md')
    for relative in ['assets/mi-grado.svg', 'docs/PRUEBA_CON_AMIGOS.md', 'docs/DESARROLLO.md', 'docs/LANZAMIENTO.md', 'docs/imagenes/panel.png', 'docs/imagenes/cuaderno.png']:
        source, destination = ROOT / relative, folder / relative
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    licenses = folder / 'Licencias'; licenses.mkdir(exist_ok=True)
    for name, source in [('Python.txt', Path(sys.base_prefix) / 'LICENSE.txt'),
                         ('Tcl.txt', Path(sys.base_prefix) / 'tcl' / 'tcl8.6' / 'license.terms'),
                         ('Tk.txt', Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms')]:
        if source.is_file(): shutil.copyfile(source, licenses / name)
    for package in ('tzdata', 'pyinstaller'):
        distribution = importlib.metadata.distribution(package)
        for item in distribution.files or []:
            if 'licenses' in item.parts and Path(str(item)).name.lower() in {'license', 'license.txt', 'copying.txt', 'licenses.txt'}:
                source = distribution.locate_file(item)
                if source.is_file(): shutil.copyfile(source, licenses / (package + '-' + source.name))
    forbidden = {'config.local.json', 'conexiones.json', 'panel-data.json', 'equipo.local.json', '.env'}
    files = sorted(path for path in folder.rglob('*') if path.is_file())
    if any(path.name in forbidden or any(part in {'runtime', '.git', 'output', 'Notas diarias'}
                                        for part in path.relative_to(folder).parts) for path in files):
        raise RuntimeError('El paquete contiene datos locales y no puede distribuirse.')
    archive = Path(shutil.make_archive(str(output / ('Mi-grado-Windows-' + args.version)), 'zip',
                                      root_dir=output, base_dir='Mi grado'))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps({'zip': str(archive), 'sha256': digest, 'files': len(files),
                      'requiresPython': False}, ensure_ascii=False))


if __name__ == '__main__': main()
