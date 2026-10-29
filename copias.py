"""Copias explícitas de un cuaderno y restauración en un perfil independiente."""
from pathlib import PurePosixPath
from rutas import Path
from urllib.parse import quote
import base64
import copy
import hashlib
import io
import json
import re
import stat
import uuid
import zipfile

from configuracion import load_config, read_panel, subject_source
from gestion import PLAN, SCHEDULE, note_path
from memoria import madrid_time
from perfiles import user_home
from persistencia_capturas import writer_lock, digest, FIELDS as CAPTURE_FIELDS
from validar_cuaderno import ident, text, stamp, FIELDS, web_topic, web_reference, rows, validate_exchange_snapshot, web_capture_id, session_details
from cuaderno_web import notebook_id
from referencias import backup_references

MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 4000


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')


def validate_web_records(files, panel):
    """Validación completa antes de crear la carpeta de restauración."""
    subjects = {s['id']:s for s in panel['subjects']}
    seen = set()
    for name, content in files.items():
        if name.startswith('web-topics/'):
            record = json.loads(content)
            expected = web_topic(record, subjects)
            key = (record['subject'], record['id'])
            if name != 'web-topics/'+expected or key in seen:
                raise ValueError('Identidad de tema web inválida o repetida.')
            seen.add(key)
            body = files.get('degree/'+record['relative'])
            if body is None: raise ValueError('Falta el texto de un tema web en la copia.')
            if record.get('canonical') is not True: text(body.decode('utf-8-sig'), 100000)
        elif name.startswith('web-results/'):
            record = json.loads(content)
            if not isinstance(record, dict) or record.get('version') != 1:
                raise ValueError('Registro de avance web no válido.')
            capture, session = record.get('capture'), record.get('session')
            if not isinstance(capture, dict) or not isinstance(session, dict):
                raise ValueError('Falta el avance original en la copia.')
            ident(record.get('bookId')); ident(session.get('id')); stamp(session.get('createdAt'))
            for field in FIELDS: text(session.get(field))
            if (not isinstance(capture.get('subject'), str) or capture['subject'] not in subjects
                    or not isinstance(capture.get('id'), str)
                    or not re.fullmatch(r'web-[a-f0-9]{48}', capture['id'])
                    or name != 'web-results/'+capture['id']+'.json'
                    or session.get('source') not in ('user', 'ai-reviewed')):
                raise ValueError('Identidad de avance web no válida.')
            selected = session.get('topicIds', [])
            if not isinstance(selected, list) or len(selected) > 200:
                raise ValueError('Selección de temas del avance no válida.')
            for topic in selected: ident(topic)
            references=session.get('referenceIds',[])
            if (not isinstance(references,list) or len(references)>200
                    or any(not isinstance(value,str) for value in references)
                    or len(set(references))!=len(references)):
                raise ValueError('Selección de material del avance no válida.')
            for reference in references:ident(reference)
            snapshot=[web_reference(value) for value in rows(session.get('referenceSnapshot',[]),200)]
            if {value['id'] for value in snapshot}!=set(references):
                raise ValueError('El material original del avance no coincide con su selección.')
            if (capture['id']!=web_capture_id(record['bookId'],session)
                    or capture.get('details')!=session_details(session).strip()):
                raise ValueError('El resumen y su material no coinciden con la captura original.')
            journal_name = 'operations/'+hashlib.sha256(capture['id'].encode()).hexdigest()[:24]+'/journal.json'
            journal = json.loads(files.get(journal_name, b'{}'))
            if any(not isinstance(capture.get(k, ''), str) for k in CAPTURE_FIELDS):
                raise ValueError('Campos de captura web no válidos.')
            normalized = {k:capture.get(k, '').strip() for k in CAPTURE_FIELDS}
            normalized['timezone'] = normalized['timezone'] or 'Europe/Madrid'
            if journal.get('state') != 'complete' or journal.get('originalCapture') != normalized:
                raise ValueError('El avance web no coincide con su guardado protegido.')


def export_backup(app):
    config = app.config
    store = app.store()
    with app.lock, writer_lock(config['runtime'] / 'review-writer.lock'), writer_lock(store.operations / 'writer.lock'):
        records, issues, pending = store.read_all()
        if issues or pending:
            raise ValueError('Hay registros pendientes o dañados. Revisa sus avisos antes de crear la copia completa.')
        for review_path in (config['runtime']/'web-reviews').glob('review-*/state.json'):
            review=json.loads(review_path.read_text(encoding='utf-8'))
            if review.get('state')=='applying':
                raise ValueError('Hay un regreso desde la web con guardado interrumpido. Reintenta ese guardado antes de crear la copia completa.')
        files, sources = {}, {}
        def include(path, name):
            path = Path(path).resolve()
            if name in files: return
            if len(files) >= MAX_FILES: raise ValueError('El cuaderno contiene demasiados archivos para esta copia.')
            data = path.read_bytes()
            if len(data) + sum(len(v) for v in files.values()) > MAX_BYTES:
                raise ValueError('La copia supera 32 MB. Esta versión guarda fichas y registros, sin adjuntos.')
            files[name] = data; sources[path] = data
        panel = read_panel(config)
        original_panel=config['panel_file'].read_bytes()
        if json.loads(original_panel.decode('utf-8-sig'))!=panel:raise ValueError('Las asignaturas cambiaron durante la copia. Vuelve a crearla.')
        for subject in panel['subjects']:
            source = subject_source(config, subject)
            if not source.is_file(): raise ValueError('Falta una ficha. Revisa tus asignaturas antes de crear la copia.')
            include(source, 'degree/'+source.relative_to(config['vaults']['degree']).as_posix())
        for relative in (PLAN, SCHEDULE):
            path = note_path(config, relative)
            if path.is_file(): include(path, 'degree/'+relative)
        subjects = {s['id']:s for s in panel['subjects']}
        for path in sorted((config['runtime']/'web-exchanges').glob('exchange-*/state.json')):
            name='web-exchanges/'+path.parent.name+'/state.json'
            include(path,name)
            validate_exchange_snapshot(json.loads(files[name]),panel['subjects'],notebook_id(config),path.parent.name)
        for path in sorted((config['runtime']/'web-topics').glob('*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(record, dict) and isinstance(record.get('subject'), str) and record['subject'] not in subjects: continue
            expected = web_topic(record, subjects)
            if path.name != expected: raise ValueError('La identidad de un tema web no coincide con su registro.')
            include(path, 'web-topics/'+expected)
            source = note_path(config, record['relative'])
            if not source.is_file(): raise ValueError('Falta una nota web importada. No se ha creado una copia incompleta.')
            include(source, 'degree/'+record['relative'])
        # Solo las capturas interpretadas y sus diarios; nunca se recorre toda la bóveda.
        for record in records:
            include(record['path'], 'degree/'+Path(record['path']).relative_to(config['vaults']['degree']).as_posix())
            if record.get('diaryPath'):
                diary = Path(record['diaryPath'])
                include(diary, 'hub/'+diary.relative_to(config['vaults']['hub']).as_posix())
            journal = store.journal_path(record['id'])
            if journal.is_file():
                include(journal, 'operations/'+journal.parent.name+'/journal.json')
                include(journal.with_name('checkpoint.json'), 'operations/'+journal.parent.name+'/checkpoint.json')
            result = config['runtime']/'web-results'/(record['id']+'.json')
            if result.is_file(): include(result, 'web-results/'+result.name)
        validate_web_records(files, panel)
        state_path = Path(store.cfg['state'])
        if state_path.exists():
            # Una configuración de memoria externa puede contener operaciones ajenas.
            state = json.loads(state_path.read_text(encoding='utf-8-sig'))
            ids = {prefix+record['id'] for record in records for prefix in ('captura.', 'diario.')}
            files['legacy-state.json'] = encode({'applied': {k:v for k,v in state.get('applied', {}).items() if k in ids}})
        portable_panel=copy.deepcopy(panel)
        portable_panel['subjects']=[backup_references(config,s) for s in panel['subjects']]
        files['panel.json'] = encode(portable_panel)
        sources[config['panel_file']] = original_panel
        connection = config['runtime'] / 'conexiones.json'
        if connection.is_file(): include(connection, 'connections.json')
        profile = {'version': 1, 'label': config.get('profile_label', panel.get('title', 'Mi grado')),
                   'notebookId':notebook_id(config),
                   'roots': {role: str(config['vaults'][role]) for role in ('degree', 'hub')},
                   'captures': config['captures'].relative_to(config['vaults']['degree']).as_posix()}
        files['profile.json'] = encode(profile)
        manifest = {'version': 1, 'createdAt': madrid_time(),
                    'files': {name: hashlib.sha256(data).hexdigest() for name,data in files.items()}}
        files['manifest.json'] = encode(manifest)
        if len(files)>MAX_FILES or sum(len(v) for v in files.values())>MAX_BYTES:
            raise ValueError('La copia completa supera 32 MB o el límite de archivos, incluidos sus recibos de traslado.')
        for path, before in sources.items():
            if not path.is_file() or path.read_bytes() != before:
                raise ValueError('Un archivo cambió durante la copia. Vuelve a crearla.')
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items(): archive.writestr(name, data)
        data=output.getvalue()
        if len(data)>MAX_BYTES:raise ValueError('El ZIP completo supera 32 MB. Conserva tus copias anteriores y revisa el tamaño del cuaderno.')
        return data


def unpack(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES: raise ValueError('Elige una copia de hasta 32 MB.')
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
                raise ValueError('La copia supera los límites de archivos o tamaño.')
            for info in infos:
                name = info.filename
                parts = PurePosixPath(name).parts
                if (not parts or name in files or '\\' in name or PurePosixPath(name).is_absolute()
                        or any(p in {'.', '..', '.git', '.obsidian'} or re.search(r'[<>:"|?*\x00-\x1f]', p)
                               or p.endswith((' ', '.')) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts)
                        or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir()):
                    raise ValueError('La copia contiene una ruta no permitida.')
                if name not in {'profile.json', 'panel.json', 'connections.json', 'legacy-state.json', 'manifest.json'}:
                    if not ((parts[0] in {'degree','hub'} and name.endswith('.md')) or
                            (len(parts) == 3 and parts[0] == 'operations' and re.fullmatch(r'[a-f0-9]{24}', parts[1])
                             and parts[2] in {'journal.json','checkpoint.json'}) or
                            (len(parts) == 2 and parts[0] == 'web-topics' and re.fullmatch(r'topic-[a-f0-9]{32}\.json', parts[1])) or
                            (len(parts) == 2 and parts[0] == 'web-results' and re.fullmatch(r'web-[a-f0-9]{48}\.json', parts[1])) or
                            (len(parts) == 3 and parts[0] == 'web-exchanges' and re.fullmatch(r'exchange-[a-f0-9]{32}',parts[1]) and parts[2]=='state.json')):
                        raise ValueError('La copia contiene archivos ajenos al cuaderno.')
                files[name] = archive.read(info)
        manifest = json.loads(files['manifest.json'])
        expected = {name: hashlib.sha256(value).hexdigest() for name,value in files.items() if name != 'manifest.json'}
        if manifest.get('version') != 1 or manifest.get('files') != expected:
            raise ValueError('La copia está incompleta o sus huellas no coinciden.')
        profile, panel = json.loads(files['profile.json']), json.loads(files['panel.json'])
        if (profile.get('version') != 1 or not isinstance(profile.get('roots'), dict)
                or set(profile['roots']) != {'degree','hub'} or not all(isinstance(v,str) and v for v in profile['roots'].values())
                or not isinstance(profile.get('label'), str) or not isinstance(panel.get('subjects'), list)
                or not panel['subjects'] or len(panel['subjects']) > 100):
            raise ValueError('El perfil de la copia no es válido.')
        return files, profile, panel
    except (zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('No es una copia completa de Mi grado.') from error


def preview_backup(data):
    files, profile, panel = unpack(data)
    return {'sha': hashlib.sha256(data).hexdigest(), 'label': profile['label'],
            'subjects': [s.get('name', '') for s in panel['subjects']], 'files': len(files),
            'size': sum(len(v) for v in files.values()),
            'notice': 'Se creará un cuaderno separado. El cuaderno actual y tus apuntes se conservan.'}


def restore_backup(data, expected_sha, destination=None):
    if hashlib.sha256(data).hexdigest() != expected_sha: raise ValueError('La copia cambió desde la vista previa.')
    files, profile, panel = unpack(data)
    root = Path(destination) if destination is not None else user_home() / 'Restauraciones' / ('Cuaderno-'+uuid.uuid4().hex[:12])
    root = Path(root).resolve()
    if root.exists(): raise ValueError('La carpeta de restauración debe ser nueva.')
    degree, hub, runtime = root/('Apuntes - '+root.name), root/('Seguimiento - '+root.name), root/'technical'
    raw = {'version': 1, 'timezone': 'Europe/Madrid', 'profile_label': profile['label'],
           'storage_key': 'mi-grado-restaurado-'+uuid.uuid4().hex,
           'vaults': {'degree': str(degree), 'hub': str(hub)}, 'runtime': str(runtime),
           'captures': profile['captures'], 'panel_file': str(root/'panel-data.json')}
    if 'notebookId' in profile:raw['web_notebook_id']=ident(profile['notebookId'])
    # Validar rutas del perfil antes de crear destinos.
    capture_rel = PurePosixPath(raw['captures'])
    if capture_rel.is_absolute() or '..' in capture_rel.parts or '\\' in raw['captures'] or ':' in raw['captures']:
        raise ValueError('Carpeta de capturas no válida.')
    known_ids = set()
    for subject in panel['subjects']:
        if not isinstance(subject, dict) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,40}', str(subject.get('id', ''))) or subject['id'] in known_ids:
            raise ValueError('Asignaturas inválidas o duplicadas en la copia.')
        known_ids.add(subject['id'])
        rel = PurePosixPath(subject.get('note', ''))
        if rel.is_absolute() or '..' in rel.parts or 'degree/'+str(rel) not in files:
            raise ValueError('Falta una ficha de asignatura o su ruta no es válida.')
    validate_web_records(files, panel)
    for name,content in files.items():
        if name.startswith('web-exchanges/'):
            validate_exchange_snapshot(json.loads(content),panel['subjects'],ident(profile.get('notebookId')),name.split('/')[1])
    old_roots = profile['roots']
    def remap_uri(value):
        for role, path in (('degree',degree), ('hub',hub)):
            old = 'obsidian://open?vault='+quote(Path(old_roots[role]).name)+'&file='
            value = value.replace(old, 'obsidian://open?vault='+quote(path.name)+'&file=')
        return value
    def destination_for(old, role):
        original, old_base = Path(old).resolve(), Path(old_roots[role]).resolve()
        if not original.is_relative_to(old_base): raise ValueError('Referencia fuera del cuaderno de origen.')
        result = (degree if role == 'degree' else hub) / original.relative_to(old_base)
        if not result.resolve().is_relative_to(degree if role == 'degree' else hub): raise ValueError('Destino no válido.')
        return str(result)
    journals = {}
    for name, content in files.items():
        if name.startswith('operations/') and name.endswith('/journal.json'):
            record = json.loads(content)
            if (record.get('version') != 2 or record.get('state') != 'complete'
                    or record.get('id') != record.get('originalCapture', {}).get('id')
                    or record.get('requestSha') != digest(record['originalCapture'])
                    or record['originalCapture'].get('subject') not in known_ids | {'general'}
                    or hashlib.sha256(record['id'].encode()).hexdigest()[:24] != name.split('/')[1]):
                raise ValueError('Registro de guardado no válido en la copia.')
            record['notePath'] = destination_for(record['notePath'], 'degree')
            record['diaryPath'] = destination_for(record['diaryPath'], 'hub')
            record['checkpointPath'] = str(runtime/'capturas-operaciones'/name.split('/')[1]/'checkpoint.json')
            if Path(record['notePath']).parent != degree / raw['captures'] or Path(record['diaryPath']).parent != hub/'Notas diarias':
                raise ValueError('Destino de registro no válido.')
            checkpoint = {'applied': {}}
            for field, destination_path in (('noteOperation',record['notePath']),('diaryOperation',record['diaryPath'])):
                operation = record[field]
                operation['path'] = destination_path
                if field == 'diaryOperation': operation['text'] = remap_uri(operation['text'])
                checkpoint['applied'][operation['id']] = hashlib.sha256(json.dumps(operation, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            journals[name] = encode(record)
            journals[name.replace('journal.json','checkpoint.json')] = encode(checkpoint)
    # El contenido aportado se escribe solo después de validar toda la estructura.
    root.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        if name.startswith(('degree/', 'hub/')):
            role, relative = name.split('/', 1)
            target = (degree if role == 'degree' else hub) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # Los enlaces al diario se ajustan; las fichas y las capturas conservan su texto.
            if role == 'hub': content = remap_uri(content.decode('utf-8-sig')).encode('utf-8')
            with target.open('xb') as stream: stream.write(content)
    runtime.mkdir(exist_ok=True)
    for name, content in journals.items():
        target = runtime/'capturas-operaciones'/name.removeprefix('operations/')
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    if 'legacy-state.json' in files: (runtime/'capture-state.json').write_bytes(files['legacy-state.json'])
    if 'connections.json' in files: (runtime/'conexiones.json').write_bytes(files['connections.json'])
    for name, content in files.items():
        if name.startswith(('web-topics/', 'web-results/', 'web-exchanges/')):
            target = runtime/name
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    # Los enlaces de fuentes se reconstruyen, y los de calendarios siguen el cuaderno recuperado.
    def links(value,field=''):
        if isinstance(value, dict): return {k: links(v,k) for k,v in value.items() if k not in {'canonicalSha','canonicalModifiedAt'}}
        if isinstance(value, list): return [links(v,field) for v in value]
        if isinstance(value,str) and field=='path':
            normalized=value.replace('\\','/')
            for role,destination in (('degree',degree),('hub',hub)):
                base=old_roots[role].replace('\\','/').rstrip('/')
                if normalized.casefold().startswith(base.casefold()+'/'):
                    return str(destination/normalized[len(base)+1:])
            if normalized.startswith('/') or re.match(r'^[A-Za-z]:',normalized) or '..' in normalized.split('/'):
                return normalized.rsplit('/',1)[-1]
        return remap_uri(value) if isinstance(value,str) else value
    (root/'panel-data.json').write_bytes(encode(links(panel)))
    (root/'config.json').write_bytes(encode(raw))
    restored = load_config(root/'config.json')
    # Falla visiblemente si el guardado recuperado no reúne sus pruebas originales.
    from puente_memoria import Application
    app = Application(restored)
    captures, issues, pending = app.store().read_all()
    if issues or pending:
        raise ValueError('Los archivos se han recuperado en '+str(root)+', pero sus registros requieren revisión. No se abrió el cuaderno.')
    return {'config': str(restored['path']), 'folder': str(root), 'subjects': len(panel['subjects']),
            'captures': len(captures), 'saved': True}
