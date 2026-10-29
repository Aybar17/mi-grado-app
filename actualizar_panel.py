"""Actualizar resúmenes explícitos con copia y comprobación de la ficha leída."""
from rutas import Path
import argparse
import hashlib
import json

from configuracion import add_options, load_config, initialize_demo, subject_source
from memoria import atomic_text, madrid_time
from persistencia_capturas import writer_lock

SUBJECT_FIELDS = {'level', 'covered', 'evidence', 'checkpoint', 'studied', 'materials', 'nextPractice', 'stage', 'tutorMode'}
PLAN_FIELDS = {'priorityTitle', 'priorityDetail', 'week', 'weekLabel', 'deadlines', 'alerts', 'sessionTemplate', 'pendingTasks'}


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def update(config, review):
    initialize_demo(config)
    output = config['runtime']
    output.mkdir(parents=True, exist_ok=True)
    with writer_lock(output / 'review-writer.lock'):
        return apply_update(config, review)


def apply_update(config, review):
    file = config['panel_file']
    before = file.read_bytes()
    changed = json.loads(before.decode('utf-8-sig'))
    by_id = {s['id']: s for s in changed['subjects']}
    if not isinstance(review, dict) or set(review) - {'subjects', 'plan'}:
        raise ValueError('Revisión inválida; solo subjects y plan')
    entries = review.get('subjects', [])
    if not isinstance(entries, list):
        raise ValueError('subjects debe ser una lista')
    if not entries and not review.get('plan'):
        return {'status': 'unchanged', 'subjects': 0}
    now = madrid_time()
    sources = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {'id', 'sourceSha', 'patch'}:
            raise ValueError('Entrada de asignatura inválida')
        subject = by_id.get(entry.get('id'))
        if subject is None or subject['id'] in seen:
            raise ValueError('Asignatura desconocida o duplicada')
        seen.add(subject['id'])
        source = subject_source(config, subject)
        if not source.exists():
            raise ValueError('Falta fuente canónica')
        sha = hash_file(source)
        if sha != entry.get('sourceSha'):
            raise ValueError('La ficha cambió desde la lectura: ' + subject['id'])
        patch = entry.get('patch', {})
        if not isinstance(patch, dict) or set(patch) - SUBJECT_FIELDS:
            raise ValueError('Campo de resumen no admitido')
        for key, value in patch.items():
            if key in {'covered', 'evidence', 'studied', 'materials'}:
                if not isinstance(value, list) or not all(isinstance(v, (str, dict)) for v in value):
                    raise ValueError('Lista inválida: ' + key)
            elif key == 'stage':
                if type(value) is not int or not 0 <= value <= 4:
                    raise ValueError('Etapa inválida')
            elif not isinstance(value, str):
                raise ValueError('Texto inválido: ' + key)
        subject.update(patch, canonicalReviewedSha=sha, summaryReviewedAt=now)
        sources.append((source, sha))
    plan = review.get('plan', {})
    if not isinstance(plan, dict) or set(plan) - PLAN_FIELDS:
        raise ValueError('Campo de plan no admitido')
    for key,value in plan.items():
        if key in {'priorityTitle','priorityDetail','weekLabel','sessionTemplate'}:
            if not isinstance(value,str):raise ValueError('Texto de plan inválido: '+key)
        elif not isinstance(value,list):raise ValueError('Lista de plan inválida: '+key)
    for day in plan.get('week',[]):
        if not isinstance(day,dict) or not isinstance(day.get('date'),str) or not isinstance(day.get('slots',[]),list):
            raise ValueError('Día o bloques del plan inválidos')
        import datetime
        try:datetime.date.fromisoformat(day['date'])
        except ValueError:raise ValueError('Fecha de plan inválida')
        for slot in day.get('slots',[]):
            if not isinstance(slot,dict) or slot.get('subject') not in by_id or not isinstance(slot.get('title'),str):
                raise ValueError('Bloque o asignatura de plan inválidos')
            if 'minutes' in slot and (type(slot['minutes']) is not int or not 0<slot['minutes']<=1440):
                raise ValueError('Duración de bloque inválida')
    for entry in plan.get('deadlines',[]):
        if not isinstance(entry,dict) or entry.get('subject') not in by_id or not isinstance(entry.get('title'),str):
            raise ValueError('Entrega de plan inválida')
    pending_ids = set()
    for task in plan.get('pendingTasks', []):
        if (not isinstance(task, dict) or task.get('subject') not in by_id
                or not isinstance(task.get('title'), str) or not task['title'].strip()
                or not isinstance(task.get('id'), str) or not task['id'].strip()
                or task['id'] in pending_ids):
            raise ValueError('Tarea pendiente inválida o duplicada')
        pending_ids.add(task['id'])
        if 'minutes' in task and (type(task['minutes']) is not int or not 0 < task['minutes'] <= 1440):
            raise ValueError('Duración de tarea pendiente inválida')
        for field in ('priority', 'outcome', 'reason'):
            if field in task and not isinstance(task[field], str):
                raise ValueError('Texto de tarea pendiente inválido')
    if any(not isinstance(value,(str,dict)) for value in plan.get('alerts',[])):
        raise ValueError('Aviso de plan inválido')
    changed.update(plan)
    changed['memoryReviewedAt'] = now
    changed['panelSummaryReviewedAt'] = now
    def verify():
        if file.read_bytes() != before or any(hash_file(path) != sha for path, sha in sources):
            raise RuntimeError('Edición concurrente; conservar cambios y volver a leer')
    verify()
    backups = config['runtime'] / 'review-backups'
    backups.mkdir(exist_ok=True)
    backup = backups / (hashlib.sha256(before).hexdigest() + '.json')
    if not backup.exists():
        with backup.open('xb') as stream:
            stream.write(before)
    if backup.read_bytes() != before:
        raise RuntimeError('Copia no verificada')
    verify()
    atomic_text(file, json.dumps(changed, ensure_ascii=False, indent=2), before_replace=verify)
    if file.read_text(encoding='utf-8') != json.dumps(changed, ensure_ascii=False, indent=2):
        raise RuntimeError('Guardado no verificado; revisar copia')
    return {'status': 'saved', 'subjects': len(sources), 'memoryReviewedAt': now,
            'officialCheckedAt': changed.get('checked'), 'backup': str(backup)}


def main():
    parser = add_options(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--review', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(update(load_config(args.config, args.demo),
                            json.loads(args.review.read_text(encoding='utf-8-sig'))), ensure_ascii=False))


if __name__ == '__main__':
    main()
