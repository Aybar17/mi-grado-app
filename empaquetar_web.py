"""Paquete web y skill: lista cerrada, sin configuración ni notas personales."""
from pathlib import Path
import json
import hashlib
import shutil
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parent
VERSION = '0.9.0-rc.3'
SKILL_VERSION = '0.1.6'
WEB_FILES = ('index.html','core.js','storage.js','app.js','app.css','identidad.css','flujo-estudio.js','interfaz.js','materiales-ui.js','PRIMER-USO.md','sw.js','manifest.webmanifest','INSTRUCCIONES-IA.md','GUIA-IA.md')
SKILL_FILES = ('SKILL.md','LICENSE','agents/openai.yaml','references/intercambio.md','references/primer-uso.md','scripts/puente_obsidian.py','scripts/rutas.py','scripts/validar_cuaderno.py')


def archive(target, files):
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as output:
        for name, source in files: output.write(source,name)
    with zipfile.ZipFile(target) as check:
        if set(check.namelist()) != {name for name,_ in files} or check.testzip(): raise ValueError('Paquete incompleto.')


def build():
    out = ROOT/'output/web-piloto'/VERSION
    site = out/'mi-grado-web'
    app = site/'app'
    app.mkdir(parents=True,exist_ok=True)
    for name in WEB_FILES: shutil.copyfile(ROOT/name if name in ('identidad.css','flujo-estudio.js','interfaz.js','materiales-ui.js') else ROOT/'skills/mi-grado-obsidian-ia/references/primer-uso.md' if name=='PRIMER-USO.md' else ROOT/'web/app'/name,app/name)
    source = Image.open(ROOT/'assets/mi-grado.png').convert('RGBA')
    for size in (192,512): source.resize((size,size),Image.Resampling.LANCZOS).save(app/f'icon-{size}.png')
    skill = ROOT/'skills/mi-grado-obsidian-ia'
    # La skill instalable es autónoma. Sus dos utilidades son copias exactas
    # de las fuentes comunes; no se mantienen variantes del contrato o rutas.
    for name in ('rutas.py','validar_cuaderno.py'):
        if (skill/'scripts'/name).read_bytes()!=(ROOT/name).read_bytes():
            raise ValueError('Actualiza la copia distribuible de '+name+' antes de empaquetar la skill.')
    skill_zip = out/'mi-grado-obsidian-ia.zip'
    archive(skill_zip, [('mi-grado-obsidian-ia/'+name,skill/name) for name in SKILL_FILES])
    shutil.copyfile(skill_zip,app/skill_zip.name)
    plugin = {
        '$schema':'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
        'name':'mi-grado-obsidian-ia','version':SKILL_VERSION,'license':'MIT',
        'description':'Estudiar con notas seleccionadas y devolver avances revisables a Mi grado y Obsidian.',
        'author':{'name':'Mi grado'},
        'extensions':{'com.openai':{'interface':{
            'displayName':'Mi grado · Obsidian y mi IA','shortDescription':'Estudio con tus notas',
            'longDescription':'Prepara estudio con archivos elegidos. Devuelve avances JSON revisables y notas Markdown; guardado directo solo en un agente local con acceso autorizado.',
            'developerName':'Mi grado','category':'Education','capabilities':[],
            'defaultPrompt':'Retoma mi estudio con este contexto Mi grado y prepara un avance revisable.'}}}}
    manifest = out/'plugin.json'
    manifest.write_text(json.dumps(plugin,ensure_ascii=False,indent=2),encoding='utf-8')
    compatibility=out/'plugin-compatibility.json'
    compatibility.write_text(json.dumps({
        'interface':plugin['extensions']['com.openai']['interface'],
        **{key:plugin[key] for key in ('name','version','description','author','license')},
        'keywords':[],'skills':'./skills'},ensure_ascii=False,indent=2),encoding='utf-8')
    plugin_zip = out/'mi-grado-obsidian-ia-plugin.zip'
    archive(plugin_zip,[('mi-grado-obsidian-ia/plugin.json',manifest),('mi-grado-obsidian-ia/.codex-plugin/plugin.json',compatibility)]+[('mi-grado-obsidian-ia/skills/mi-grado-obsidian-ia/'+name,skill/name) for name in SKILL_FILES])
    shutil.copyfile(plugin_zip,app/plugin_zip.name)
    stamp=hashlib.sha256(b''.join((app/name).read_bytes() for name in WEB_FILES+('mi-grado-obsidian-ia.zip','mi-grado-obsidian-ia-plugin.zip'))).hexdigest()[:12]
    (app/'sw.js').write_text((app/'sw.js').read_text(encoding='utf-8').replace('mi-grado-web-v1','mi-grado-web-'+stamp),encoding='utf-8')
    # El sitio es estático. No incluye los endpoints ni perfiles de la aplicación Windows.
    shutil.copyfile(ROOT/'web/index.html',site/'index.html')
    shutil.copyfile(ROOT/'web/landing.css',site/'landing.css')
    (site/'assets').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'assets/mi-grado.svg',site/'assets/mi-grado.svg')
    shutil.copyfile(ROOT/'docs/imagenes/panel.png',site/'assets/panel.png')
    promo=('social-preview.png','social-preview-portada.png','planificar.png','registrar.png','retomar.png','demo.gif','vista-cuaderno.png')
    for name in promo:shutil.copyfile(ROOT/'docs/imagenes'/name,site/'assets'/name)
    fonts=('DMSans.ttf','Lora.ttf','OFL-DM-Sans.txt','OFL-Lora.txt')
    (site/'assets/fonts').mkdir(exist_ok=True)
    for name in fonts:shutil.copyfile(ROOT/'web/fonts'/name,site/'assets/fonts'/name)
    shutil.copyfile(ROOT/'LICENSE',site/'LICENSE')
    shutil.copyfile(ROOT/'web/vercel.json',site/'vercel.json')
    website = out/f'Mi-grado-web-{VERSION}-piloto.zip'
    files=[('index.html',site/'index.html'),('landing.css',site/'landing.css'),('LICENSE',site/'LICENSE'),('vercel.json',site/'vercel.json'),('assets/mi-grado.svg',site/'assets/mi-grado.svg'),('assets/panel.png',site/'assets/panel.png')]
    files += [('assets/'+name,site/'assets'/name) for name in promo]
    files += [('assets/fonts/'+name,site/'assets/fonts'/name) for name in fonts]
    files += [('app/'+name,app/name) for name in WEB_FILES+('icon-192.png','icon-512.png','mi-grado-obsidian-ia.zip','mi-grado-obsidian-ia-plugin.zip')]
    archive(website,files)
    return {'site':str(site),'web':str(website),'skill':str(skill_zip),'plugin':str(plugin_zip),'published':False}


if __name__=='__main__': print(json.dumps(build(),ensure_ascii=False))
