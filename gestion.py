"""Gestión local y planes Markdown con control de ediciones concurrentes."""
from rutas import Path
from datetime import date
import copy
import hashlib
import json
import re
import uuid

from configuracion import read_panel, subject_source
from memoria import atomic_text
from persistencia_capturas import writer_lock
from perfiles import new_subject, note_filename
from horario import DAYS, load_schedule

PLAN = '00 Dashboard/Plan de Mi grado.md'
SCHEDULE = '00 Dashboard/Horario de clase.md'
START, END = '<!-- mi-grado:plan -->', '<!-- /mi-grado:plan -->'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def note_path(config, relative):
    path = (config['vaults']['degree'] / relative).resolve()
    if not path.is_relative_to(config['vaults']['degree']) or any(p in {'.git', '.obsidian', '.venv'} for p in Path(relative).parts):
        raise ValueError('La nota debe estar dentro de tus apuntes.')
    return path


def text(value, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum or '\x00' in value:
        raise ValueError('Texto no válido o demasiado largo.')
    value = value.strip()
    if required and (not value or '\n' in value or '\r' in value):
        raise ValueError('Escribe un nombre o título en una sola línea.')
    return value


def write_checked(config, path, before, content):
    """Copia y comprueba el contenido leído justo antes del reemplazo atómico."""
    if before is not None:
        backup = config['runtime'] / 'edit-backups' / (sha(str(path).encode()+before) + '.bak')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with backup.open('xb') as stream: stream.write(before)
        if backup.read_bytes() != before: raise ValueError('No se pudo verificar la copia anterior.')
    def verify():
        current = path.read_bytes() if path.exists() else None
        if current != before:
            raise ValueError('La fuente cambió mientras editabas. Recarga y vuelve a revisar.')
    verify()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, content, before_replace=verify)


def read_plan(config):
    path = note_path(config, PLAN)
    before = path.read_bytes() if path.exists() else None
    body = before.decode('utf-8-sig') if before is not None else '# Mi plan de estudio\n\nLas tareas son declaraciones propias, no evidencia de dominio ni entrega oficial.\n'
    match = re.search(re.escape(START)+r'\s*```json\s*([\s\S]*?)```\s*'+re.escape(END), body)
    if (START in body or END in body) and (not match or body.count(START) != 1 or body.count(END) != 1):
        raise ValueError('El bloque del plan necesita revisión en tus apuntes; no se reemplazará.')
    value = json.loads(match[1]) if match else {'version': 1, 'tasks': []}
    if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('tasks'), list):
        raise ValueError('El plan no tiene un formato válido.')
    validate_tasks(config, value['tasks'])
    return path, before, body, match, value


def validate_tasks(config, tasks):
    ids = {s['id'] for s in read_panel(config)['subjects']}
    seen = set()
    if len(tasks) > 1000: raise ValueError('Máximo 1000 tareas por cuaderno.')
    for item in tasks:
        if not isinstance(item, dict) or not {'id', 'subject', 'title', 'date', 'minutes', 'detail', 'status'} <= set(item) or set(item)-{'id','subject','title','date','minutes','detail','status','kind','dateStatus','proposedDay'}:
            raise ValueError('Tarea incompleta o con campos desconocidos.')
        if not re.fullmatch(r'task-[a-f0-9]{32}', str(item['id'])) or item['id'] in seen:
            raise ValueError('Identificador de tarea no válido o repetido.')
        seen.add(item['id'])
        if not isinstance(item['subject'], str) or item['subject'] not in ids: raise ValueError('La asignatura de una tarea no existe.')
        if item.get('kind','task') not in ('task','exam') or item.get('dateStatus','declared') not in ('declared','confirmed'):raise ValueError('Tipo o fecha de tarea no válido.')
        proposed=item.get('proposedDay','')
        if not isinstance(proposed,str):raise ValueError('Fecha propuesta no válida.')
        if proposed:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',proposed):raise ValueError('Fecha propuesta no válida.')
            date.fromisoformat(proposed)
        text(item['title'], 300, True); text(item['detail'], 2000)
        if not isinstance(item['date'], str): raise ValueError('Fecha no válida.')
        if item['date']:
            if not isinstance(item['date'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['date']):
                raise ValueError('Fecha no válida.')
            date.fromisoformat(item['date'])
        if type(item['minutes']) is not int or not (item['minutes']==0 or 5 <= item['minutes'] <= 480):
            raise ValueError('Duración entre 5 y 480 minutos, o cero si aún no se ha indicado.')
        if not isinstance(item['status'], str) or item['status'] not in {'pendiente', 'realizada', 'archivada'}:
            raise ValueError('Estado de tarea no válido.')


def management_state(config):
    before = config['panel_file'].read_bytes()
    panel = json.loads(before.decode('utf-8-sig'))
    plan_issue = ''
    try: path, plan_before, _, _, plan = read_plan(config)
    except (ValueError, TypeError, KeyError) as error:
        path = note_path(config, PLAN)
        plan_before = path.read_bytes() if path.exists() else None
        plan = {'tasks': []}; plan_issue = str(error)
    schedule_path = note_path(config, SCHEDULE)
    schedule_before = schedule_path.read_bytes() if schedule_path.exists() else None
    from referencias import collect_references
    references={s['id']:collect_references(config,s)[0] for s in panel['subjects']}
    return {'panelSha': sha(before),'references':references, 'subjects': [{k: s.get(k, '') for k in
            ('id', 'name', 'short', 'note', 'checkpoint', 'nextPractice', 'archived')} for s in panel['subjects']],
            'planSha': sha(plan_before) if plan_before is not None else None, 'tasks': plan['tasks'], 'planIssue': plan_issue,
            'scheduleSha': sha(schedule_before) if schedule_before is not None else None,
            'schedule': load_schedule(config['vaults']['degree'])}


def save_reference(config,raw):
    from validar_cuaderno import web_reference
    if not isinstance(raw,dict) or set(raw)!={'panelSha','subject','reference'}:raise ValueError('Revisa la asignatura y el material.')
    reference=web_reference(raw['reference'])
    with writer_lock(config['runtime']/'review-writer.lock'):
        before=config['panel_file'].read_bytes()
        if sha(before)!=raw['panelSha']:raise ValueError('Las referencias cambiaron. Reabre el editor antes de guardar.')
        panel=json.loads(before.decode('utf-8-sig'));subject=next((s for s in panel['subjects'] if s['id']==raw['subject']),None)
        if subject is None:raise ValueError('La asignatura ya no existe.')
        rows=subject.setdefault('webReferences',[])
        rows[:]=[r for r in rows if r['id']!=reference['id']]+[reference]
        from referencias import collect_references
        collect_references(config,subject)
        write_checked(config,config['panel_file'],before,json.dumps(panel,ensure_ascii=False,indent=2))
    return management_state(config)


def save_subject(config, raw):
    if not isinstance(raw, dict) or set(raw) != {'action', 'panelSha', 'subject'} or not isinstance(raw['subject'], dict):
        raise ValueError('Revisa los datos de la asignatura.')
    action, fields = raw['action'], raw['subject']
    if action not in {'add', 'edit'}: raise ValueError('Acción no válida.')
    expected = {'name', 'note'} if action == 'add' else {'id', 'name', 'checkpoint', 'nextPractice', 'archived'}
    if set(fields) != expected: raise ValueError('Campos de asignatura no válidos.')
    name = text(fields['name'], 120, True)
    with writer_lock(config['runtime'] / 'review-writer.lock'):
        before = config['panel_file'].read_bytes()
        if sha(before) != raw['panelSha']: raise ValueError('Las asignaturas cambiaron. Recarga antes de guardar.')
        panel = json.loads(before.decode('utf-8-sig'))
        if any(s.get('name', '').casefold() == name.casefold() and s['id'] != fields.get('id') for s in panel['subjects']):
            raise ValueError('Ya hay una asignatura con ese nombre. Usa uno distinto.')
        if action == 'add':
            if len(panel['subjects']) >= 100: raise ValueError('Máximo 100 asignaturas.')
            relative = text(fields['note'], 400) or f'01 Asignaturas/{note_filename(name)}/{note_filename(name)}.md'
            path = subject_source(config, {'note': relative})
            note_path(config, relative)
            item = new_subject(name, path.relative_to(config['vaults']['degree']).as_posix())
            if any(s['id'] == item['id'] or s['note'] == item['note'] for s in panel['subjects']):
                raise ValueError('Esta asignatura o ficha ya existe.')
            if fields['note'] and not path.is_file(): raise ValueError('No existe esa ficha Markdown. Deja la ruta vacía para crearla.')
            if path.exists(): path.read_text(encoding='utf-8-sig')
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('x', encoding='utf-8') as stream:
                    stream.write(f'# {name}\n\n## Último intento\n\n## Ayuda recibida\n\n## Siguiente comprobación\n')
            panel['subjects'].append(item)
        else:
            item = next((s for s in panel['subjects'] if s['id'] == fields['id']), None)
            if item is None: raise ValueError('La asignatura ya no existe.')
            if type(fields['archived']) is not bool: raise ValueError('Estado de archivo no válido.')
            if fields['archived'] and not item.get('archived') and sum(not s.get('archived') for s in panel['subjects']) <= 1:
                raise ValueError('Conserva al menos una asignatura activa.')
            item.update(name=name, short=name, checkpoint=text(fields['checkpoint'], 2000),
                        nextPractice=text(fields['nextPractice'], 2000), archived=fields['archived'])
        write_checked(config, config['panel_file'], before, json.dumps(panel, ensure_ascii=False, indent=2))
    return management_state(config)


def save_task(config, raw):
    if not isinstance(raw, dict) or set(raw) != {'planSha', 'task'} or not isinstance(raw['task'], dict):
        raise ValueError('Revisa los datos de la tarea.')
    with writer_lock(config['runtime'] / 'review-writer.lock'):
        path, before, body, match, value = read_plan(config)
        if (sha(before) if before is not None else None) != raw['planSha']:
            raise ValueError('El plan cambió. Recarga antes de guardar.')
        item = copy.deepcopy(raw['task'])
        if not item.get('id'): item['id'] = 'task-' + uuid.uuid4().hex
        else:
            if not any(t['id'] == item['id'] for t in value['tasks']): raise ValueError('La tarea ya no existe.')
        previous=next((t for t in value['tasks'] if t['id']==item['id']),{})
        for key in ('kind','dateStatus','proposedDay'):
            if key not in item and key in previous:item[key]=previous[key]
        validate_tasks(config, [item])
        if item['status'] == 'pendiente' and any(s['id'] == item['subject'] and s.get('archived') for s in read_panel(config)['subjects']):
            raise ValueError('Reactiva la asignatura o elige una activa antes de planificar trabajo pendiente.')
        value['tasks'] = [t for t in value['tasks'] if t['id'] != item['id']] + [item]
        validate_tasks(config, value['tasks'])
        block = START+'\n```json\n'+json.dumps(value, ensure_ascii=False, indent=2)+'\n```\n'+END
        body = body[:match.start()] + block + body[match.end():] if match else body.rstrip()+'\n\n'+block+'\n'
        write_checked(config, path, before, body)
    return management_state(config)


def save_schedule(config, raw):
    if not isinstance(raw, dict) or set(raw) != {'scheduleSha', 'classes', 'group', 'period'} or not isinstance(raw['classes'], list):
        raise ValueError('Revisa las clases del horario.')
    if len(raw['classes']) > 500: raise ValueError('Máximo 500 clases.')
    group, period = text(raw['group'], 100), text(raw['period'], 100)
    if any('\n' in v or '\r' in v for v in (group, period)): raise ValueError('Grupo y periodo deben ocupar una línea.')
    rows = []
    for item in raw['classes']:
        if not isinstance(item, dict) or set(item) != {'day', 'start', 'end', 'subject', 'kind', 'room'}:
            raise ValueError('Clase incompleta.')
        if item['day'] not in DAYS or not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(item[k])) for k in ('start','end')) or item['start'] >= item['end']:
            raise ValueError('Revisa el día y las horas de inicio y fin.')
        for k in ('subject', 'kind', 'room'):
            value = text(item[k], 150, k=='subject')
            if '|' in value or '\n' in value or '\r' in value: raise ValueError('No uses barras verticales ni saltos de línea en el horario.')
        rows.append('| '+' | '.join(item[k] for k in ('day','start','end','subject','kind','room'))+' |')
    with writer_lock(config['runtime'] / 'review-writer.lock'):
        path = note_path(config, SCHEDULE)
        before = path.read_bytes() if path.exists() else None
        if (sha(before) if before is not None else None) != raw['scheduleSha']:
            raise ValueError('El horario cambió. Recarga antes de guardar.')
        body = before.decode('utf-8-sig') if before is not None else '# Horario de clase\n\n'
        if load_schedule(config['vaults']['degree'])['issues']:
            raise ValueError('Hay filas no interpretadas en la nota. Revísalas en Obsidian antes de usar este editor.')
        lines = body.splitlines()
        starts = [i for i, line in enumerate(lines) if re.fullmatch(r'\|\s*Día\s*\|\s*Inicio\s*\|\s*Fin\s*\|\s*Asignatura\s*\|\s*Tipo\s*\|\s*Aula\s*\|?', line.strip())]
        if len(starts) > 1: raise ValueError('Hay varias tablas de horario. Conserva una sola antes de editar.')
        table = ['| Día | Inicio | Fin | Asignatura | Tipo | Aula |', '| --- | --- | --- | --- | --- | --- |'] + rows
        if starts:
            first, last = starts[0], starts[0]+1
            while last < len(lines) and lines[last].strip().startswith('|'): last += 1
            lines[first:last] = table
        else: lines += ['', '## Clases', ''] + table
        for key, value in (('Grupo', group), ('Periodo', period)):
            found = [i for i, line in enumerate(lines) if line.startswith(key+':')]
            if len(found) > 1: raise ValueError('Metadatos de horario repetidos; revísalos en Obsidian.')
            if found:
                if value: lines[found[0]] = key+': '+value
                else: lines.pop(found[0])
            elif value: lines.insert(2, key+': '+value)
        # Cambiar el horario invalida un contraste docente anterior.
        lines = [line for line in lines if not line.startswith('Contraste:')]
        write_checked(config, path, before, '\n'.join(lines)+'\n')
    return management_state(config)


def apply_plan(config, base):
    """El plan canónico añade sesiones sin retirar tareas de otras fuentes."""
    try:
        _, _, _, _, value = read_plan(config)
    except (ValueError, TypeError, KeyError) as error:
        value = {'tasks': []}
        base['planningIssues'] = ['El plan necesita revisión: '+str(error)]
    base['managedTasks'] = value['tasks']
    active = {s['id'] for s in base['subjects'] if not s.get('archived')}
    base['subjects'] = [s for s in base['subjects'] if not s.get('archived')]
    base['pendingTasks'] = [t for t in base.get('pendingTasks', []) if t.get('subject') in active]
    week = {day['date']: {**copy.deepcopy(day), 'slots': [t for t in day.get('slots', []) if t.get('subject') in active]}
            for day in base.get('week', []) if day.get('date')}
    base['deadlines'] = [d for d in base.get('deadlines', []) if d.get('subject') in active or not d.get('subject')]
    for item in value['tasks']:
        if item['status'] != 'pendiente' or item['subject'] not in active: continue
        slot = {**item, 'duration': f"{item['minutes']} min" if item['minutes'] else 'Duración por indicar', 'outcome': item['detail'], 'managed': True}
        if item['date'] and item['date'] >= base['today']:
            week.setdefault(item['date'], {'date': item['date'], 'slots': []})['slots'].append(slot)
        else: base['pendingTasks'].append(slot)
    base['week'] = [week[key] for key in sorted(week)]
    own_pending = sorted((t for t in value['tasks'] if t['status'] == 'pendiente' and t['subject'] in active),
                         key=lambda t: t['date'] or '9999-12-31')
    if own_pending and base.get('priorityTitle') == 'Preparar tu primera sesión':
        base['priorityTitle'] = own_pending[0]['title']
        base['priorityDetail'] = own_pending[0]['detail'] or 'Recupera el enunciado, realiza tu intento y guarda por dónde continuar.'
    return base
