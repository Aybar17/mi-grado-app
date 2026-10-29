"""Perfiles nuevos sin rutas personales ni modificaciones de notas existentes."""
from rutas import Path
from urllib.parse import urlsplit
import hashlib
import json
import os
import re
import unicodedata
import uuid

from configuracion import load_config
from memoria import atomic_text


def user_home():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Mi grado'


def default_profile():
    return user_home() / 'perfil' / 'config.json'


def campus_url(value):
    value = value.strip()
    if not value:
        return ''
    parts = urlsplit(value)
    if (parts.scheme not in {'https', 'http'} or not parts.hostname
            or parts.username or parts.password or any(c.isspace() for c in value)):
        raise ValueError('Introduce una dirección http(s) del campus sin credenciales.')
    return value


def identifier(name):
    slug = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')[:30]
    if not slug or not slug[0].isalpha():
        slug = 'asignatura-' + slug
    return slug + '-' + hashlib.sha256(name.encode()).hexdigest()[:6]


def note_filename(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', name).strip(' .') or 'Asignatura'
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', value, flags=re.IGNORECASE):
        value = 'Asignatura ' + value
    if len(value) > 60:
        value = value[:50].rstrip(' .') + '-' + hashlib.sha256(name.encode()).hexdigest()[:8]
    return value


def new_subject(name, relative):
    return {'id': identifier(name), 'name': name, 'short': name, 'note': relative,
            'color': '#235b45', 'level': 'Comprensión pendiente de comprobar',
            'studied': [], 'covered': [], 'evidence': [], 'stage': 0,
            'checkpoint': 'Indicar el último intento y la ayuda recibida.',
            'nextPractice': 'Elegir el enunciado y realizar un primer intento.',
            'tutorMode': 'diagnostico', 'materials': []}


def create_profile(config_path, degree, subjects, label='Mi espacio de estudio',
                   center='Otro centro', campus='', existing_notes=()):
    """Guarda config al final: nunca sustituye otra instalación ni una ficha."""
    config_path, degree = Path(config_path).resolve(), Path(degree).resolve()
    if config_path.exists():
        raise ValueError('Este perfil ya existe. Abre su configuración; no se reemplazará.')
    label = label.strip()
    if not label or len(label) > 100:
        raise ValueError('El nombre del espacio debe tener entre 1 y 100 caracteres.')
    campus = campus_url(campus)
    if center not in {'UGR', 'Otra universidad', 'FP', 'Otro centro'}:
        raise ValueError('Elige un tipo de centro válido.')
    names = [name.strip() for name in subjects if name.strip()]
    if any(len(name) > 100 for name in names) or len(names) > 100:
        raise ValueError('Máximo 100 asignaturas de hasta 100 caracteres.')
    selected = []
    for note in existing_notes:
        note = Path(note).resolve()
        if not note.is_relative_to(degree) or note.suffix.lower() != '.md' or not note.is_file():
            raise ValueError('Elige fichas Markdown dentro de tu carpeta de apuntes.')
        if any(part in {'.obsidian', '.git'} for part in note.relative_to(degree).parts):
            raise ValueError('Elige una ficha de estudio, no archivos de configuración.')
        note.read_text(encoding='utf-8-sig')  # Detectar codificación antes de crear el perfil.
        selected.append(new_subject(note.stem, note.relative_to(degree).as_posix()))
    for name in names:
        relative = f'01 Asignaturas/{note_filename(name)}/{note_filename(name)}.md'
        selected.append(new_subject(name, relative))
    if not selected or len(selected) > 100:
        raise ValueError('Escribe al menos una asignatura o elige una ficha existente.')
    if len({s['id'] for s in selected}) != len(selected) or len({s['note'] for s in selected}) != len(selected):
        raise ValueError('Hay asignaturas repetidas. Cada ficha se añade una sola vez.')
    profile_id = uuid.uuid4().hex
    hub, runtime = config_path.parent / 'Seguimiento', config_path.parent / 'technical'
    raw = {'version': 1, 'timezone': 'Europe/Madrid', 'profile_label': label,
           'storage_key': 'mi-grado-' + profile_id,
           'vaults': {'degree': str(degree), 'hub': str(hub)},
           'runtime': str(runtime), 'panel_file': str(config_path.parent / 'panel-data.json'),
           'campus': {'center': center, 'url': campus}, 'ai_chat': 'chatgpt'}
    # Validar la separación incluso cuando las carpetas aún no existen.
    if any(a.is_relative_to(b) or b.is_relative_to(a) for a, b in
           ((degree, hub), (degree, runtime), (degree, config_path.parent))):
        raise ValueError('La carpeta de apuntes y la de configuración deben estar separadas.')
    panel = {'version': 2, 'title': label, 'subtitle': 'Tus apuntes, intentos y próximo paso.',
             'weekLabel': 'Plan pendiente de preparar', 'checked': None,
             'memoryReviewedAt': None, 'subjects': selected, 'week': [], 'changes': [],
             'deadlines': [], 'pendingTasks': [], 'coverage': [], 'alerts': [],
             'priorityTitle': 'Preparar tu primera sesión',
             'priorityDetail': 'Elige una asignatura y su enunciado; conserva tu propio intento.',
             'methods': []}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # No se leen otras notas ni se presupone progreso al elegirlas.
    for subject in selected:
        note = degree / subject['note']
        if not note.exists():
            note.parent.mkdir(parents=True, exist_ok=True)
            try:
                with note.open('x', encoding='utf-8') as out:
                    out.write(f"# {subject['name']}\n\n## Materiales\n\n## Último intento\n\n"
                              "## Ayuda recibida\n\n## Siguiente comprobación\n")
            except FileExistsError:
                pass  # Una edición concurrente siempre se conserva.
    hub.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    panel_path = Path(raw['panel_file'])
    if panel_path.exists():
        raise ValueError('Hay un resumen anterior en esta carpeta. Elige un perfil nuevo.')
    with panel_path.open('x', encoding='utf-8') as out:
        json.dump(panel, out, ensure_ascii=False, indent=2)
    with config_path.open('x', encoding='utf-8') as out:
        json.dump(raw, out, ensure_ascii=False, indent=2)
    return load_config(config_path)


def add_subject(config, name, note=None):
    from persistencia_capturas import writer_lock
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError('Escribe un nombre de hasta 100 caracteres.')
    degree = config['vaults']['degree']
    path = Path(note).resolve() if note else degree / f'01 Asignaturas/{note_filename(name)}/{note_filename(name)}.md'
    if not path.is_relative_to(degree) or path.suffix.lower() != '.md':
        raise ValueError('La ficha debe estar dentro de tu carpeta de apuntes.')
    subject = new_subject(name, path.relative_to(degree).as_posix())
    with writer_lock(config['runtime'] / 'review-writer.lock'):
        before = config['panel_file'].read_bytes()
        panel = json.loads(before.decode('utf-8-sig'))
        if any(s['id'] == subject['id'] or s['note'] == subject['note'] for s in panel['subjects']):
            raise ValueError('Esta asignatura o ficha ya está añadida.')
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as out:
                out.write(f'# {name}\n\n## Último intento\n\n## Siguiente comprobación\n')
        else:
            path.read_text(encoding='utf-8-sig')
        panel['subjects'].append(subject)
        backup = config['runtime'] / 'review-backups' / (hashlib.sha256(before).hexdigest() + '.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with backup.open('xb') as out:
                out.write(before)
        def verify():
            if backup.read_bytes() != before or config['panel_file'].read_bytes() != before:
                raise ValueError('El resumen cambió. Vuelve a abrirlo antes de añadir la asignatura.')
        verify()
        atomic_text(config['panel_file'], json.dumps(panel, ensure_ascii=False, indent=2), before_replace=verify)
    return subject
