"""Windows portable con binarios oficiales de Python sin modificar su firma."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent
MODULES = ['escritorio.py','perfiles.py','configuracion.py','puente_memoria.py','generar_panel.py',
           'memoria.py','persistencia_capturas.py','conexiones.py','extension_panel.py','horario.py','gestion.py','copias.py','cuaderno_web.py','validar_cuaderno.py','intercambio_web.py','referencias.py','rutas.py']
RESOURCES = ['panel-template.html','panel-extra.js','team-ui.js','conexiones-ui.js','gestion-ui.js','intercambio-ui.js',
             'apoyo-diseno.css','identidad.css','modelos.json','flujo-estudio.js','interfaz.js','materiales-ui.js']


def build_portable(version):
    base = Path(sys.base_prefix)
    # Solo un intérprete oficial firmado; no se genera ni se autoriza un ejecutable nuevo.
    pythonw = base/'pythonw.exe'
    check_env = dict(os.environ)
    check_env['PSModulePath'] = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/Modules')
    check = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                            "Get-AuthenticodeSignature -FilePath '"+str(pythonw).replace("'","''")+"' | Select-Object -ExpandProperty Status"],
                           capture_output=True,text=True,encoding='utf-8',errors='replace',env=check_env,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
    if check.stdout.strip() != 'Valid': raise RuntimeError('Se requiere Python oficial con firma válida para este paquete.')
    output = ROOT/'output/windows'
    folder = output/('portable-'+uuid.uuid4().hex[:10]); folder.mkdir(parents=True)
    interpreter, app = folder/'Python', folder/'Aplicacion'
    interpreter.mkdir(); app.mkdir()
    tag = f'python{sys.version_info.major}{sys.version_info.minor}'
    for name in ['python.exe','pythonw.exe','python3.dll',tag+'.dll','vcruntime140.dll','vcruntime140_1.dll']:
        source = base/name
        if source.exists(): shutil.copyfile(source,interpreter/name)
    shutil.copytree(base/'DLLs',interpreter/'DLLs',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(base/'Lib',interpreter/'Lib',ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test','tests','idlelib','ensurepip'))
    shutil.copytree(base/'tcl',interpreter/'tcl')
    distribution = importlib.metadata.distribution('tzdata')
    shutil.copytree(distribution.locate_file('tzdata'),interpreter/'Lib/site-packages/tzdata',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # Aislamiento documentado por Python: no carga paquetes de otra instalación o del registro.
    (interpreter/(tag+'._pth')).write_text('.\nLib\nDLLs\nLib/site-packages\n../Aplicacion\n',encoding='ascii')
    for name in MODULES+RESOURCES: shutil.copyfile(ROOT/name,app/name)
    shutil.copytree(ROOT/'assets',app/'assets')
    shutil.copytree(ROOT/'examples/demo',app/'examples/demo')
    for name in ['README.md','ATTRIBUTION.md','CONTRIBUTING.md','LICENSE']:
        shutil.copyfile(ROOT/name,folder/name)
    for relative in ['docs/INICIO.md','docs/HOJA_DE_RUTA.md','docs/PILOTO.md',
                     'docs/imagenes/banner.svg','docs/imagenes/social-preview.png','docs/imagenes/social-preview-portada.png','docs/imagenes/planificar.png','docs/imagenes/registrar.png','docs/imagenes/retomar.png','docs/imagenes/demo.gif',
                     'docs/DESARROLLO.md',
                     'skills/mi-grado-obsidian-ia/references/primer-uso.md',
                     'docs/imagenes/panel.png','docs/imagenes/cuaderno.png','assets/mi-grado.svg']:
        target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
    shutil.copyfile(ROOT/'docs/INICIO.md',folder/'EMPEZAR.md')
    license_folder=folder/'Licencias';license_folder.mkdir()
    tcl_license = base/'tcl/tcl8.6/license.terms'
    if not tcl_license.exists():
        tcl_version = subprocess.run([sys.executable, '-c', "import tkinter;print(tkinter.Tcl().eval('info patchlevel'))"],
                                     check=True,capture_output=True,text=True).stdout.strip()
        tcl_license = ROOT/'licenses'/('tcl-'+tcl_version+'.txt')
    for name,source in [('Python.txt',base/'LICENSE.txt'),('Tcl.txt',tcl_license),('Tk.txt',base/'tcl/tk8.6/license.terms')]:
        if not source.exists(): raise RuntimeError('Falta la licencia requerida: '+name)
        shutil.copyfile(source,license_folder/name)
    tzdata_license_found = False
    for item in distribution.files or []:
        if 'licenses' in item.parts and Path(str(item)).name.lower() in {'license','license.txt','licenses.txt'}:
            shutil.copyfile(distribution.locate_file(item),license_folder/('tzdata-'+item.name))
            tzdata_license_found = True
    if not tzdata_license_found: raise RuntimeError('Falta la licencia requerida: tzdata')
    (folder/'Abrir Mi grado.cmd').write_text('@echo off\r\nsetlocal\r\nstart "" "%~dp0Python\\pythonw.exe" "%~dp0Aplicacion\\escritorio.py" %*\r\n',encoding='ascii',newline='')
    # Comprueba stdlib, datos horarios y Tcl sin mostrar una ventana ni usar Python externo.
    probe="import sys,json,ssl,tkinter;from zoneinfo import ZoneInfo;assert ZoneInfo('Europe/Madrid');print(tkinter.Tcl().eval('info patchlevel'))"
    subprocess.run([str(interpreter/'python.exe'),'-c',probe],check=True,cwd=folder,capture_output=True)
    files=sorted(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    forbidden={'config.local.json','conexiones.json','panel-data.json','equipo.local.json','.env'}
    if any(p.name in forbidden or any(part in {'runtime','.git','Notas diarias'} for part in p.relative_to(folder).parts) for p in files):
        raise RuntimeError('Se ha detectado un archivo local ajeno al paquete.')
    archive=output/('Mi-grado-Windows-'+version+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in files:zip_file.write(path,(Path('Mi grado')/path.relative_to(folder)).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'zip':str(archive),'sha256':digest,'files':len(files),'requiresPython':False,
                      'launcher':'Abrir Mi grado.cmd','officialRuntimeSignature':'Valid'},ensure_ascii=False))
    return archive
