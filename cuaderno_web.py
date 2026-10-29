"""Traslado explícito a la web: solo fichas seleccionadas, plan, horario y capturas completas."""
from datetime import datetime
from rutas import Path
import hashlib
import json
import re

from configuracion import read_panel, subject_source
from conexiones import read_settings
from gestion import management_state
from validar_cuaderno import web_topic, web_origin, text
from referencias import collect_references


def stable(prefix, value):
    return prefix+'-'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def notebook_id(config):
    from validar_cuaderno import ident
    return ident(config.get('web_notebook_id') or stable('book-local',str(config['path'])))


def text_parts(value, maximum=100000):
    """El navegador limita unidades UTF-16, no puntos Unicode de Python."""
    start=used=0
    parts=[]
    for i,char in enumerate(value):
        width=2 if ord(char)>0xffff else 1
        if used+width>maximum:
            parts.append(value[start:i]);start=i;used=0
        used+=width
    if start<len(value):parts.append(value[start:])
    return parts


def imported_topics(config, subjects):
    """Lee exclusivamente temas registrados de las asignaturas de este perfil."""
    known={s['id']:s for s in subjects}
    for registry in sorted((config['runtime']/'web-topics').glob('*.json')):
        record=json.loads(registry.read_text(encoding='utf-8'))
        if isinstance(record,dict) and isinstance(record.get('subject'),str) and record['subject'] not in known:continue
        if web_topic(record,known)!=registry.name:raise ValueError('La identidad de un tema web no coincide con su registro.')
        if record.get('canonical') is True:
            yield record, None
            continue
        path=(config['vaults']['degree']/record['relative']).resolve()
        if not path.is_relative_to((config['vaults']['degree']/'Mi grado/Notas web').resolve()):raise ValueError('Una nota web registrada está fuera de su carpeta.')
        if not path.is_file():raise ValueError('Falta una nota web importada. Revisa su archivo antes de preparar el traslado.')
        content=path.read_text(encoding='utf-8-sig');text(content,100000)
        yield {**record,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'modifiedAt':datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec='seconds')}, content


def canonical_parts(content,subject,records):
    """Conserva las partes revisadas; nunca elimina su identidad al acortar la ficha."""
    expected={stable('topic',subject+':'+str(i)):i for i in range(200)}
    selected=[r for r,_ in records if r['subject']==subject and r.get('canonical') is True]
    if any(r['id'] not in expected for r in selected):raise ValueError('Una parte de ficha tiene una identidad ajena a la asignatura.')
    selected.sort(key=lambda r:expected[r['id']])
    minimum=max((expected[r['id']]+1 for r in selected),default=0)
    if selected and all('partIndex' in r for r in selected):
        if [r['partIndex'] for r in selected]!=list(range(len(selected))) or len({r['noteSha'] for r in selected})!=1:
            raise ValueError('Faltan partes registradas de la ficha. Revisa sus metadatos antes de trasladarla.')
        position=0;segments=[]
        for i,record in enumerate(selected):
            end=position+record['contentLength'] if i<len(selected)-1 else len(content)
            segments.append(content[position:end]);position=end
        changed=hashlib.sha256(content.encode('utf-8')).hexdigest()!=selected[0]['noteSha']
        if not changed and sum(r['contentLength'] for r in selected)!=len(content):raise ValueError('Las longitudes de partes no corresponden a su ficha.')
        parts=[part for segment in segments for part in (text_parts(segment) or [''])]
        return parts,changed
    parts=text_parts(content)
    return parts+['']*max(0,minimum-len(parts)),False


def export_notebook(app):
    with app.lock:
        config=app.config
        panel=read_panel(config)
        managed=management_state(config)
        if managed.get('planIssue'):
            raise ValueError('Revisa el plan antes de trasladarlo: '+managed['planIssue'])
        settings=read_settings(config)
        captures, capture_issues, journal_issues=app.store().read_all()
        warnings=[]
        book={'kind':'mi-grado-notebook','version':5,'id':notebook_id(config),
              'label':config.get('profile_label') or panel.get('title') or 'Mi cuaderno', 'rev':0,
              'subjects':[],'tasks':[],'schedule':[],'sessions':[],'requests':[],
              'settings':{'degree':config['vaults']['degree'].name,'center':settings['center'],
                          'vault':config['vaults']['degree'].name,'provider':settings['chat'],'campus':settings['campus_url']},
              'connections':{'obsidian':None,'ai':None}}
        ids={s['id']:stable('subject',s['id']) for s in managed['subjects']}
        imported=list(imported_topics(config,managed['subjects']))
        # No se recorren otras notas de las bóvedas ni se exportan rutas de configuración.
        for s in managed['subjects']:
            source=subject_source(config,s)
            if not source.is_file():
                raise ValueError('Falta la ficha de '+s['name']+'. No se ha preparado una copia incompleta.')
            content=source.read_text(encoding='utf-8-sig')
            parts,changed=canonical_parts(content,s['id'],imported)
            if changed:warnings.append('La ficha de '+s['name']+' se editó en local después del último regreso. Revisa sus partes antes de compartirlas.')
            topics=[{'id':stable('topic',s['id']+':'+str(i)),
                     'title':('Ficha de '+s['name'])[:140]+(f' · parte {i+1}' if len(parts)>1 else ''),
                     'content':part,'filename':source.name,'archived':False} for i,part in enumerate(parts)]
            if len(topics)>200: raise ValueError('La ficha de '+s['name']+' supera el límite de temas web.')
            raw_subject=next(row for row in panel['subjects'] if row['id']==s['id'])
            references,_,reference_warnings=collect_references(config,raw_subject);warnings.extend(reference_warnings)
            book['subjects'].append({'id':ids[s['id']],'name':s['name'],'archived':s['archived'],'references':references,
                                     'checkpoint':s.get('checkpoint',''),'nextPractice':s.get('nextPractice',''),'topics':topics})
        for record, content in imported:
            subject=next(s for s in book['subjects'] if s['id']==ids[record['subject']])
            if record.get('canonical') is True:
                target=next((t for t in subject['topics'] if t['id']==record['id']),None)
                if target is not None:target.update(title=record['title'],filename=record.get('filename',''),archived=record.get('archived') is True,origin=web_origin(record.get('origin')))
                continue
            subject['topics'].append({'id':record['id'],'title':record['title'],'content':content,'filename':record.get('filename',''),'archived':record.get('archived') is True,'origin':web_origin(record.get('origin'))})
        for t in managed['tasks']:
            book['tasks'].append({'id':stable('task',t['id']),'subjectId':ids[t['subject']],
                                  'title':t['title'],'day':t['date'],'minutes':t['minutes'],'detail':t['detail'],
                                  **{k:t[k] for k in ('kind','dateStatus','proposedDay') if k in t},
                                  'done':t['status']=='realizada','archived':t['status']=='archivada'})
        # Los perfiles anteriores también planifican en el resumen revisado: conservarlos.
        legacy=[(t,t.get('date','')) for t in panel.get('pendingTasks',[])]
        legacy.extend((t,d.get('date','')) for d in panel.get('week',[]) for t in d.get('slots',[]))
        legacy.extend((t,t.get('date','')) for t in panel.get('deadlines',[]))
        known_tasks={t['id'] for t in managed['tasks']}
        seen=set()
        for t,day in legacy:
            if t.get('id') in known_tasks: continue
            if t.get('subject') not in ids or not isinstance(t.get('title'),str):
                warnings.append('Una tarea o fecha general del resumen no se ha trasladado: necesita asignatura y título.');continue
            detail=json.dumps({k:v for k,v in t.items() if k not in ('id','subject','title','date')},ensure_ascii=False)
            identity=t.get('id') or json.dumps([t,day],sort_keys=True,ensure_ascii=False)
            if identity in seen: continue
            seen.add(identity)
            if len(detail)>2000 or len(t['title'])>300: raise ValueError('Una tarea del resumen supera el tamaño web. No se ha recortado su detalle.')
            try:
                if day: datetime.fromisoformat(day)
                if day and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day): raise ValueError()
            except (ValueError,TypeError): raise ValueError('Revisa una fecha del resumen antes de trasladar el cuaderno.')
            duration=t.get('minutes',0)
            if type(duration) is not int or not 5<=duration<=480:
                match=re.fullmatch(r'(\d+)\s*min(?:utos)?',str(t.get('duration','')))
                duration=int(match[1]) if match and 5<=int(match[1])<=480 else 0
            book['tasks'].append({'id':stable('task-previous',identity),'subjectId':ids[t['subject']],
                                  'title':t['title'],'day':day,'minutes':duration,'detail':detail if detail!='{}' else '',
                                  **{k:t[k] for k in ('kind','dateStatus','proposedDay') if k in t and (k!='kind' or t[k] in ('task','exam'))},
                                  'done':t.get('completed') is True or t.get('done') is True,'archived':False})
        names={}
        for s in managed['subjects']:
            for name in {s['name'],s.get('short','')}:
                if name: names.setdefault(name,set()).add(ids[s['id']])
        days=['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
        for i,c in enumerate(managed['schedule']['classes']):
            matches=names.get(c['subject'],set())
            if len(matches)!=1:
                warnings.append('Clase omitida por asignatura ambigua o desconocida: '+c['subject']);continue
            book['schedule'].append({'id':stable('class',str(i)+json.dumps(c,sort_keys=True,ensure_ascii=False)),
                                     'subjectId':next(iter(matches)),'day':days.index(c['day'])+1,
                                     'start':c['start'],'end':c['end'],'room':c['room'],'kind':c['kind']})
        warnings.extend(managed['schedule'].get('issues',[]))
        omitted=0;dated_by_save=0
        for c in captures:
            if c.get('subject') not in ids or not (c.get('saved') is True and c.get('saveState')=='complete' and c.get('journalLinked') is True):
                omitted+=1;continue
            registry=config['runtime']/'web-results'/(c['id']+'.json')
            if registry.is_file():
                stored=json.loads(registry.read_text(encoding='utf-8'))
                from persistencia_capturas import literal
                from validar_cuaderno import stamp, ident, text, FIELDS
                session=stored.get('session',{})
                # Una edición visible posterior manda sobre los campos estructurados del intercambio.
                if stored.get('version')==1 and stored.get('capture',{}).get('subject')==c['subject'] and literal(stored.get('capture',{}).get('details','')).strip()==c.get('details','').strip():
                    for field in FIELDS:text(session.get(field))
                    ident(session.get('id'));stamp(session.get('createdAt'))
                    known_topics={t['id'] for s in book['subjects'] if s['id']==ids[c['subject']] for t in s['topics']}
                    target_subject=next(s for s in book['subjects'] if s['id']==ids[c['subject']])
                    for reference in session.get('referenceSnapshot',[]):
                        if not any(r['id']==reference['id'] for r in target_subject['references']):
                            from validar_cuaderno import web_reference
                            target_subject['references'].append({**web_reference(reference),'archived':True})
                            warnings.append('Se conserva una referencia histórica que ya no está en el material local: '+reference['title'])
                    known_refs={r['id'] for s in book['subjects'] if s['id']==ids[c['subject']] for r in s['references']}
                    row={**session,'subjectId':ids[c['subject']],'topicIds':[tid for tid in session.get('topicIds',[]) if tid in known_topics],
                         'referenceIds':[rid for rid in session.get('referenceIds',[]) if rid in known_refs]}
                    if any(x['id']==row['id'] for x in book['sessions']):row['id']=stable('session',c['id'])
                    book['sessions'].append(row);continue
            from validar_cuaderno import stamp
            at=c.get('created') or c.get('savedAt');date_note=''
            try:stamp(at)
            except (ValueError,TypeError):
                try:at=stamp(c.get('savedAt'))
                except (ValueError,TypeError):raise ValueError('Una captura no tiene fecha con hora y zona ni guardado confirmado válido. Revisa su guardado antes de trasladarla.')
                dated_by_save+=1
                date_note='Fecha de creación declarada en el original: '+str(c.get('created') or 'sin indicar')+'. Para ordenar este registro se usa el guardado confirmado: '+at+'. No se ha deducido una hora de creación.'
            attempt='\n\n'.join(x for x in [c.get('title',''),c.get('details',''),date_note] if x)
            if len(attempt.encode('utf-16-le'))//2>12000:
                subject=next(s for s in book['subjects'] if s['id']==ids[c['subject']])
                for i,part in enumerate(text_parts(attempt)):
                    subject['topics'].append({'id':stable('topic-capture',c['id']+':'+str(i)),'title':('Registro local · '+c['title'])[:160],
                                              'content':part,'filename':Path(c['path']).name,'archived':False})
                attempt='Registro local: '+c['title']+'. Su detalle completo se conserva en los temas de esta asignatura.'
            book['sessions'].append({'id':stable('session',c['id']),'subjectId':ids[c['subject']],
                                      'createdAt':at,'source':'user','topicIds':[],'attempt':attempt,
                                      'help':'No desglosada en la captura original; consulta el detalle.',
                                      'result':'Declaración trasladada del cuaderno local; no verificada de nuevo.',
                                      'nextStep':''})
        book['sessions'].sort(key=lambda s:s['createdAt'])
        if dated_by_save:warnings.append(f'{dated_by_save} capturas antiguas se ordenan por su guardado confirmado; conservan la fecha original declarada en el detalle, sin inventar una hora de creación.')
        if any(len(s['topics'])>200 for s in book['subjects']):raise ValueError('Los registros completos superan el límite de temas. Conserva el original y selecciona el material antes de trasladarlo.')
        if omitted: warnings.append(f'{omitted} capturas generales o con guardado incompleto no se trasladan.')
        if capture_issues or journal_issues: warnings.append('Hay incidencias de capturas o diario: revisa el panel local; no se han dado por completas.')
        from validar_cuaderno import validate_book
        validate_book(book)
        for key,limit in [('subjects',100),('tasks',1000),('schedule',500),('sessions',2000)]:
            if len(book[key])>limit: raise ValueError('El número de '+key+' supera el límite web. No se ha recortado la copia.')
        if len(json.dumps(book,ensure_ascii=False).encode('utf-8'))>4*1024*1024:
            raise ValueError('El cuaderno supera 4 MB. Conserva la copia local y traslada por separado los temas que necesites.')
        return {'book':book,'warnings':warnings,'notice':'Copia privada para traslado. No incluye adjuntos, otras notas, objetivos generales, borradores del navegador ni sincronización. El ZIP local sigue siendo la copia completa del cuaderno.'}
