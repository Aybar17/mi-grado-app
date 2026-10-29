# Solo código y recursos ficticios seleccionados. Nunca se incluye el checkout completo.
from pathlib import Path

root = Path(SPECPATH)
resources = ['panel-template.html', 'panel-extra.js', 'team-ui.js', 'conexiones-ui.js', 'gestion-ui.js', 'intercambio-ui.js',
             'apoyo-diseno.css', 'identidad.css', 'modelos.json', 'interfaz.js', 'flujo-estudio.js','materiales-ui.js']
datas = [(str(root / name), '.') for name in resources]
datas += [(str(root / 'examples' / 'demo'), 'examples/demo')]
datas += [(str(root / 'assets'), 'assets')]
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('tzdata')

a = Analysis([str(root / 'escritorio.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=['tzdata'], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Mi grado', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon=str(root / 'assets' / 'mi-grado.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Mi grado')
