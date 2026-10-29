"""Contrato del archivo web para el programa portable, sin Node ni red."""
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit
import json
import re
import hashlib

MAX_BYTES=4*1024*1024
FIELDS=('attempt','help','result','nextStep')
ID=re.compile(r'[a-z0-9][a-z0-9_-]{5,79}')


def web_capture_id(book_id,session):
    value=json.dumps([book_id,session],ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return 'web-'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:48]


def session_details(session):
    details='\n\n'.join('## '+title+'\n\n'+(session[key] or 'No indicado.') for title,key in zip(
        ('Lo que intenté','Ayuda recibida','Resultado observado','Próximo paso'),FIELDS))
    if session.get('referenceSnapshot'):
        details+='\n\n## Material referenciado en la sesión\n\n'+'\n\n'.join(
            r['title']+'\n'+r['location']+'\n'+r.get('link','')+'\n'+r['detail'] for r in session['referenceSnapshot'])
        details+='\n\nUna referencia no confirma lectura del archivo ni revisión del campus.'
    return details


def text(value,maximum=12000,required=False):
    if not isinstance(value,str) or '\x00' in value or len(value.encode('utf-16-le'))//2>maximum:
        raise ValueError('Texto ausente, inválido o demasiado largo en el cuaderno.')
    if required and not value.strip():raise ValueError('Falta un nombre u objetivo del cuaderno.')
    return value


def ident(value):
    if not isinstance(value,str) or not ID.fullmatch(value):raise ValueError('Identificador de cuaderno no válido.')
    return value


def rows(value,maximum):
    if not isinstance(value,list) or len(value)>maximum or any(not isinstance(x,dict) for x in value):
        raise ValueError('Lista inválida o demasiado grande en el cuaderno.')
    ids=[ident(x.get('id')) for x in value]
    if len(ids)!=len(set(ids)):raise ValueError('El cuaderno contiene identificadores repetidos.')
    return value


def stamp(value):
    text(value,80)
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if 'T' not in value or result.tzinfo is None:raise ValueError()
    except ValueError:raise ValueError('La fecha de un registro necesita hora y zona horaria.')
    return value


def minutes(value=0):
    if type(value) is not int or value<0 or value>480 or 0<value<5:raise ValueError('Duración inválida en el cuaderno.')
    return value


def web_reference(value):
    if not isinstance(value,dict):raise ValueError('Referencia de material no válida.')
    kind=value.get('kind');location=text(value.get('location',''),2000).strip()
    if kind=='web':
        parsed=urlsplit(location)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('La referencia necesita una dirección web sin credenciales.')
        location=urlunsplit((parsed.scheme,parsed.netloc,parsed.path or '/',parsed.query,parsed.fragment))
    elif kind=='local-file':
        location=location.replace('\\','/')
        if (not location or len(location)>400 or location.startswith('/') or ':' in location
                or any(p in ('','..','.','.git','.obsidian','.venv') for p in location.split('/'))
                or re.search(r'[<>"|?*\x00-\x1f]',location)):
            raise ValueError('Indica el nombre o una ruta relativa del material dentro de tus apuntes.')
    elif kind=='description':location=''
    else:raise ValueError('Tipo de referencia de material no válido.')
    link=text(value.get('link',''),2000)
    if link:
        parsed=urlsplit(link)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('El enlace del material necesita una dirección web sin credenciales.')
        link=urlunsplit((parsed.scheme,parsed.netloc,parsed.path or '/',parsed.query,parsed.fragment))
    return {'id':ident(value.get('id')),'title':text(value.get('title'),160,True),'kind':kind,'location':location,'link':link,
            'detail':text(value.get('detail',''),2000),'archived':value.get('archived') is True}


def web_origin(value):
    if value is None:return None
    if (not isinstance(value,dict) or value.get('kind')!='markdown-file'
            or not isinstance(value.get('contentHash'),str) or not re.fullmatch(r'[a-f0-9]{64}',value['contentHash'])):
        raise ValueError('El origen del tema no es válido.')
    return {'kind':'markdown-file','name':text(value.get('name'),180,True),'contentHash':value['contentHash'],
            'importedAt':stamp(value.get('importedAt')),'checkedAt':stamp(value.get('checkedAt')),
            'fileModifiedAt':stamp(value['fileModifiedAt']) if value.get('fileModifiedAt') else ''}


def web_topic(record, subjects):
    """Identidad y ruta de un tema que el usuario ya eligió incorporar."""
    if not isinstance(record, dict) or record.get('version') != 1:
        raise ValueError('Un tema web tiene un registro inválido.')
    subject = record.get('subject')
    if not isinstance(subject, str) or subject not in subjects:
        raise ValueError('Un tema web pertenece a otra asignatura.')
    ident(record.get('id')); text(record.get('title'), 160, True); text(record.get('filename', ''), 180)
    web_origin(record.get('origin'))
    relative = record.get('relative')
    if not isinstance(relative, str): raise ValueError('Ruta de tema web no válida.')
    if record.get('canonical') is True:
        if relative != subjects[subject]['note']: raise ValueError('La ficha de un tema web no corresponde a su asignatura.')
        layout=('partIndex','contentLength','noteSha')
        if any(k in record for k in layout):
            if (not all(k in record for k in layout) or type(record['partIndex']) is not int or not 0<=record['partIndex']<200
                    or type(record['contentLength']) is not int or not 0<=record['contentLength']<=100000
                    or not isinstance(record['noteSha'],str) or not re.fullmatch(r'[a-f0-9]{64}',record['noteSha'])
                    or record['id']!='topic-'+hashlib.sha256((subject+':'+str(record['partIndex'])).encode('utf-8')).hexdigest()[:32]):
                raise ValueError('La distribución de partes de una ficha no es válida.')
    elif not re.fullmatch(r'Mi grado/Notas web/notebook-[a-f0-9]{32}/topic-[a-f0-9]{32}\.md', relative):
        raise ValueError('Un tema web está fuera de su carpeta de notas.')
    return 'topic-'+hashlib.sha256((subject+':'+record['id']).encode('utf-8')).hexdigest()[:32]+'.json'


def validate_book(raw):
    if not isinstance(raw,dict) or raw.get('kind')!='mi-grado-notebook' or raw.get('version') not in (4,5):
        raise ValueError('Selecciona una copia JSON web actualizada de Mi grado (formato 4 o 5).')
    if len(json.dumps(raw,ensure_ascii=False,allow_nan=False).encode('utf-8'))>MAX_BYTES:
        raise ValueError('El cuaderno supera 4 MB.')
    ident(raw.get('id'));text(raw.get('label'),120,True)
    subjects=rows(raw.get('subjects'),100);known={s['id'] for s in subjects}
    def subject(value):
        if not isinstance(value,str) or value not in known:raise ValueError('Un registro pertenece a una asignatura desconocida.')
    topics={}
    for s in subjects:
        text(s.get('name'),120,True);text(s.get('checkpoint',''),2000);text(s.get('nextPractice',''),2000)
        topics[s['id']]={t['id'] for t in rows(s.get('topics'),200)}
        s['references']=[web_reference(r) for r in rows(s.get('references',[]),200)]
        for t in s['topics']:
            text(t.get('title'),160,True);text(t.get('content'),100000);text(t.get('filename',''),180)
            t['origin']=web_origin(t.get('origin'))
    for t in rows(raw.get('tasks'),1000):
        subject(t.get('subjectId'));text(t.get('title'),300,True);text(t.get('detail',''),2000);minutes(t.get('minutes',0))
        if t.get('kind','task') not in ('task','exam'):raise ValueError('Tipo de tarea no válido.')
        if t.get('dateStatus','declared') not in ('declared','confirmed'):raise ValueError('Estado de fecha no válido.')
        proposed=t.get('proposedDay','')
        if not isinstance(proposed,str):raise ValueError('Fecha propuesta no válida.')
        if proposed:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',proposed):raise ValueError('Fecha propuesta no válida.')
            date.fromisoformat(proposed)
        if t.get('day')!='':
            if not isinstance(t.get('day'),str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',t['day']):raise ValueError('Día de tarea no válido.')
            date.fromisoformat(t['day'])
    for c in rows(raw.get('schedule'),500):
        subject(c.get('subjectId'))
        if type(c.get('day')) is not int or not 1<=c['day']<=7:raise ValueError('Día de clase no válido.')
        if any(not isinstance(c.get(k),str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',c[k]) for k in ('start','end')) or c['end']<=c['start']:
            raise ValueError('Horas de clase no válidas.')
        text(c.get('room'),120);text(c.get('kind',''),120)
    requests=rows(raw.get('requests'),2000)
    for r in requests:
        subject(r.get('subjectId'));stamp(r.get('createdAt'));text(r.get('goal'),2000,True)
        minutes(r.get('minutes',0));text(r.get('exercise',''),2000);text(r.get('checkpoint',''),2000)
    for s in rows(raw.get('sessions'),2000):
        subject(s.get('subjectId'));stamp(s.get('createdAt'))
        if s.get('source') not in ('user','ai-reviewed'):raise ValueError('Fuente de registro no válida.')
        for key in FIELDS:text(s.get(key))
    for item in requests+raw['sessions']:
        selected=item.get('topicIds',[])
        if not isinstance(selected,list) or len(selected)>200 or any(not isinstance(x,str) for x in selected) or len(set(selected))!=len(selected) or any(x not in topics[item['subjectId']] for x in selected):
            raise ValueError('Temas de otra asignatura o repetidos en un registro.')
        references=item.get('referenceIds',[])
        known_references={r['id'] for s in subjects if s['id']==item['subjectId'] for r in s['references']}
        if not isinstance(references,list) or len(references)>200 or any(not isinstance(x,str) for x in references) or len(set(references))!=len(references) or any(x not in known_references for x in references):
            raise ValueError('Referencias de otra asignatura o repetidas en un registro.')
        item['referenceIds']=references
        subject=next(s for s in subjects if s['id']==item['subjectId'])
        snapshot=item.get('referenceSnapshot')
        if snapshot is None:snapshot=[r for r in subject['references'] if r['id'] in references]
        snapshot=[web_reference(r) for r in rows(snapshot,200)]
        if len(snapshot)!=len(references) or any(r['id'] not in references for r in snapshot):raise ValueError('El material registrado no coincide con la selección original.')
        item['referenceSnapshot']=snapshot
    settings=raw.get('settings',{})
    if not isinstance(settings,dict) or settings.get('provider') not in ('chatgpt','claude','gemini'):raise ValueError('Configuración de IA no válida.')
    for field in ('degree','center','vault'):text(settings.get(field,''),120)
    campus=text(settings.get('campus',''),2000)
    if campus:
        u=urlsplit(campus)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:raise ValueError('Campus no válido.')
    transfer=raw.get('transfer')
    if transfer is not None:
        if not isinstance(transfer,dict) or set(transfer)!={'kind','version','exchangeId','profileId'} or transfer['kind']!='mi-grado-local' or transfer['version']!=1:
            raise ValueError('Identidad del traslado no válida.')
        ident(transfer['exchangeId']);ident(transfer['profileId'])
    return raw


def validate_exchange_snapshot(raw, subjects, notebook_id, exchange_id):
    """El ZIP solo lleva recibos con rutas relativas de este mismo cuaderno."""
    if not isinstance(raw,dict) or raw.get('version')!=1:raise ValueError('Recibo de traslado no válido.')
    if not re.fullmatch(r'exchange-[a-f0-9]{32}',exchange_id):raise ValueError('Identidad de traslado no válida.')
    expected={'kind':'mi-grado-local','version':1,'exchangeId':exchange_id,'profileId':notebook_id}
    if raw.get('receipt')!=expected:raise ValueError('El recibo de traslado pertenece a otro cuaderno.')
    book=validate_book(raw.get('base'))
    if book['id']!=notebook_id or book.get('transfer')!=expected:raise ValueError('La salida original no coincide con su recibo.')
    stamp(raw.get('createdAt'))
    known={s['id']:s for s in subjects};mapping=raw.get('subjects')
    if not isinstance(mapping,dict) or set(mapping)!={s['id'] for s in book['subjects']}:
        raise ValueError('Faltan asignaturas en el recibo de traslado.')
    local_ids=set()
    for subject in book['subjects']:
        item=mapping[subject['id']]
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or item['id'] not in known or item['id'] in local_ids:
            raise ValueError('Un traslado previo tiene asignaturas ajenas o retiradas. Revisa su origen antes de copiarlo.')
        local_ids.add(item['id'])
        stable_subject='subject-'+hashlib.sha256(item['id'].encode('utf-8')).hexdigest()[:32]
        if subject['id']!=stable_subject or item.get('note')!=known[item['id']]['note']:
            raise ValueError('La ficha de un traslado no corresponde a su asignatura actual.')
        ids=item.get('canonicalTopics')
        if not isinstance(ids,list) or len(ids)>200:raise ValueError('Partes de ficha no válidas en el traslado.')
        expected_ids=['topic-'+hashlib.sha256((item['id']+':'+str(i)).encode('utf-8')).hexdigest()[:32] for i in range(len(ids))]
        if ids!=expected_ids or any(tid not in {t['id'] for t in subject['topics']} for tid in ids):
            raise ValueError('Las partes de la ficha original no coinciden con el traslado.')
    return raw
