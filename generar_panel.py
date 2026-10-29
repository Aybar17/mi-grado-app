"""Generar el panel a partir de configuración y fuentes locales explícitas."""
from rutas import Path
from urllib.parse import quote
import argparse
import base64
import datetime as dt
import hashlib
import json

from configuracion import ROOT, add_options, load_config, initialize_demo, read_panel, subject_source
from memoria import atomic_json, atomic_text, madrid_time
from extension_panel import load_extension
from persistencia_capturas import writer_lock
from horario import load_schedule
from conexiones import read_settings
from gestion import apply_plan
from cuaderno_web import imported_topics
from referencias import local_materials


def note_url(vault, relative):
    return 'obsidian://open?vault=' + quote(vault.name) + '&file=' + quote(relative)


def title_index(config):
    """Solo títulos, rutas y fechas técnicas; no importa el contenido de otras áreas."""
    items = []
    for role, vault in config['vaults'].items():
        for file in sorted(vault.rglob('*.md')):
            if any(part in {'.obsidian', '.git', '.venv'} for part in file.parts):
                continue
            path = file.resolve()
            if not path.is_relative_to(vault):
                continue
            rel = path.relative_to(vault).as_posix()
            items.append({'id': vault.name + '/' + rel, 'title': file.stem, 'vault': vault.name,
                          'role': role, 'area': rel.split('/')[0] if '/' in rel else 'Portada y guías',
                          'path': path.as_posix(), 'relative': rel, 'url': note_url(vault, rel),
                          'fileUrl': path.as_uri(),
                          'fileModified': dt.datetime.fromtimestamp(file.stat().st_mtime).date().isoformat(),
                          'scope': 'contenido académico' if role == 'degree' else 'título y enlace'})
    return items


def build(config, now=None):
    config['runtime'].mkdir(parents=True, exist_ok=True)
    with writer_lock(config['runtime'] / 'generation-writer.lock'):
        return _build(config, now)


def _build(config, now=None):
    initialize_demo(config)
    at = now or madrid_time()
    stamp = dt.datetime.fromisoformat(at)
    if stamp.tzinfo is None:
        raise ValueError('La fecha debe incluir zona horaria')
    base = read_panel(config)
    notes = title_index(config)
    try:
        web_topics=list(imported_topics(config,base['subjects']))
        base['materialIssues']=[]
    except (ValueError,KeyError,OSError,TypeError) as error:
        web_topics=[]
        base['materialIssues']=['No se pudieron consultar los temas trasladados: '+str(error)]
    for subject in base['subjects']:
        source = subject_source(config, subject)
        subject.setdefault('name',source.stem)
        subject.setdefault('short',source.stem)
        subject.setdefault('color','#235b45')
        extra_sources = [item for item in subject.get('sources', []) if isinstance(item, dict) and item.get('path') != source.as_posix() and not (item.get('url') or '').startswith('obsidian://')]
        subject['sources'] = [{'title': 'Ficha de ' + subject.get('short', subject['id']),
                               'path': source.as_posix(),
                               'url': note_url(config['vaults']['degree'], source.relative_to(config['vaults']['degree']).as_posix())}] + extra_sources
        subject['canonicalSha'] = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
        subject['canonicalModifiedAt'] = dt.datetime.fromtimestamp(source.stat().st_mtime, stamp.tzinfo).isoformat(timespec='seconds') if source.exists() else None
        subject['summaryNeedsReview'] = subject.get('canonicalReviewedSha') != subject['canonicalSha'] or not source.exists()
        subject['starter'] = 'Vamos con ' + subject.get('short', subject['id']) + '. Recupera la ficha y el enunciado antes de empezar; espera mi intento.'
        try:
            subject['materials'],reference_warnings=local_materials(config,subject)
            base['materialIssues'].extend(reference_warnings)
        except (ValueError,TypeError,KeyError,OSError) as error:
            subject['materials']=[];base['materialIssues'].append('Revisa las referencias de '+subject['name']+': '+str(error))
        for record,content in web_topics:
            if record['subject']!=subject['id'] or content is None or record.get('archived') is True:continue
            subject['materials'].append({'title':record['title'],'path':record['relative'],
                'url':note_url(config['vaults']['degree'],record['relative']),'webTopicId':record['id'],
                'noteText':content,'noteSha':record['sha256'],'noteModifiedAt':record['modifiedAt']})
    days = [day['date'] for day in base.get('week', []) if day.get('date')]
    base.update(version=2, today=stamp.date().isoformat(), generatedAt=at, notes=notes,
                timezone='Europe/Madrid', demo=config['demo'],
                profileLabel=config.get('profile_label', 'Mi espacio de estudio'),
                storageKey=config.get('storage_key', 'mi-grado-local-v1'),
                planStart=min(days) if days else None, planEnd=max(days) if days else None)
    apply_plan(config, base)
    days = [day['date'] for day in base.get('week', []) if day.get('date')]
    base.update(planStart=min(days) if days else None, planEnd=max(days) if days else None)
    base['planNeedsReview'] = not days or not (base['planStart'] <= base['today'] <= base['planEnd'])
    base['memory'] = {
        'noteCount': len(notes),
        'hubCount': sum(n['role'] == 'hub' for n in notes),
        'degreeCount': sum(n['role'] == 'degree' for n in notes),
        'projectCount': sum(n['role'] == 'projects' for n in notes),
        'principles': ['Una fuente canónica por dato; los índices enlazan.',
                       'Material y ayuda recibida no acreditan autonomía.',
                       'Las capturas conservan declaraciones y fechas propias.'],
        'limits': ['El mapa lee títulos y enlaces de las carpetas configuradas.',
                   'Solo las fichas académicas y capturas se leen como contenido.',
                   'La generación técnica no acredita contraste docente ni progreso.'],
    }
    base.update(load_extension(config['runtime'], config['vaults']['hub'], config.get('goals_file')))
    base['classSchedule'] = load_schedule(config['vaults']['degree'])
    base['connections'] = read_settings(config)
    base['models']=json.loads((ROOT/'modelos.json').read_text(encoding='utf-8'))
    team_script='window.PanelDesignCSS='+json.dumps((ROOT/'apoyo-diseno.css').read_text(encoding='utf-8'),ensure_ascii=False)+';\n'+(ROOT/'team-ui.js').read_text(encoding='utf-8')
    template = (ROOT / 'panel-template.html').read_text(encoding='utf-8').replace('__TEAM_UI__',team_script).replace('__PANEL_EXTRA__',(ROOT/'panel-extra.js').read_text(encoding='utf-8')).replace('__CONNECTION_UI__',(ROOT/'conexiones-ui.js').read_text(encoding='utf-8'))
    brand = (ROOT / 'assets' / 'mi-grado.svg').read_text(encoding='utf-8')
    template = template.replace('__BRAND_SVG__', brand.replace('<svg ', '<svg aria-hidden="true" ')).replace('__FAVICON__', base64.b64encode(brand.encode()).decode()).replace('__IDENTITY_CSS__', (ROOT / 'identidad.css').read_text(encoding='utf-8'))
    template = template.replace('__MANAGEMENT_UI__', (ROOT / 'gestion-ui.js').read_text(encoding='utf-8'))
    template = template.replace('__EXCHANGE_UI__', (ROOT/'intercambio-ui.js').read_text(encoding='utf-8'))
    template = template.replace('__REFERENCES_UI__',(ROOT/'materiales-ui.js').read_text(encoding='utf-8'))
    revision_payload = {key: value for key, value in base.items() if key not in {'generatedAt', 'revision'}}
    template = template.replace('__STUDY_FLOW__', (ROOT/'flujo-estudio.js').read_text(encoding='utf-8')).replace('__STUDY_INTERFACE__', (ROOT/'interfaz.js').read_text(encoding='utf-8'))
    base['revision'] = hashlib.sha256((json.dumps(revision_payload, ensure_ascii=False, sort_keys=True) + template).encode()).hexdigest()
    data = json.dumps(base, ensure_ascii=False).replace('</', r'<\/')
    config['runtime'].mkdir(parents=True, exist_ok=True)
    atomic_json(config['runtime'] / 'contexto-index.json', base)
    atomic_text(config['runtime'] / 'panel.html', template.replace('__DATA__', data))
    return base


def main():
    parser = add_options(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--now', help='Fecha ISO con zona para pruebas')
    args = parser.parse_args()
    config = load_config(args.config, args.demo)
    panel = build(config, args.now)
    print(json.dumps({'panel': str(config['runtime'] / 'panel.html'),
                      'subjects': len(panel['subjects']), 'demo': config['demo']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
