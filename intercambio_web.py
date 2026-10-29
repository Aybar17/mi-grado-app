"""Ida y vuelta manual con revisión de tres versiones y guardado recuperable."""
from rutas import Path
import base64
import copy
import hashlib
import json
import re
import uuid

from configuracion import read_panel, subject_source
from cuaderno_web import export_notebook, stable, text_parts, notebook_id
from gestion import management_state, note_path, save_task, save_schedule, write_checked, PLAN, SCHEDULE
from memoria import atomic_json, madrid_time
from perfiles import new_subject
from persistencia_capturas import writer_lock
from validar_cuaderno import validate_book, validate_exchange_snapshot, FIELDS, web_capture_id, session_details


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()
def b64(value):return base64.b64encode(value).decode() if value is not None else None
def unb64(value):return base64.b64decode(value,validate=True) if value is not None else None
def contents(path):return Path(path).read_bytes() if Path(path).is_file() else None


def location(config,folder,ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-z]+-[a-f0-9]{32}',ident):raise ValueError('Identificador de intercambio no válido.')
    target=(config['runtime']/folder/ident/'state.json').resolve()
    if not target.is_relative_to(config['runtime'].resolve()):raise ValueError('Intercambio fuera de su carpeta local.')
    return target


def prepare_exchange(app):
    with app.lock, writer_lock(app.config['runtime']/'review-writer.lock'):
        result=export_notebook(app)
        panel=read_panel(app.config)
        exchange='exchange-'+uuid.uuid4().hex
        receipt={'kind':'mi-grado-local','version':1,'exchangeId':exchange,'profileId':result['book']['id']}
        result['book']['transfer']=receipt
        mapping={}
        for subject in panel['subjects']:
            sid=stable('subject',subject['id'])
            original_ids={stable('topic',subject['id']+':'+str(i)) for i in range(200)}
            mapping[sid]={'id':subject['id'],'note':subject['note'],
                'canonicalTopics':[t['id'] for s in result['book']['subjects'] if s['id']==sid for t in s['topics'] if t['id'] in original_ids]}
        snapshot={'version':1,'receipt':receipt,'base':result['book'],'subjects':mapping,'createdAt':madrid_time()}
        atomic_json(location(app.config,'web-exchanges',exchange),snapshot)
        result['notice']+=' Conserva este archivo para poder devolver los cambios al mismo programa local.'
        return result


def _read_snapshot(app,book):
    receipt=book.get('transfer')
    if not receipt:raise ValueError('Esta copia no conserva el origen del traslado. Prepara una nueva desde el programa actualizado para volver con revisión de cambios.')
    path=location(app.config,'web-exchanges',receipt['exchangeId'])
    if not path.is_file():raise ValueError('No se encuentra el traslado original en este perfil. Abre el mismo programa local desde el que lo preparaste.')
    snapshot=json.loads(path.read_text(encoding='utf-8'))
    validate_exchange_snapshot(snapshot,read_panel(app.config)['subjects'],book['id'],receipt['exchangeId'])
    if snapshot.get('version')!=1 or snapshot.get('receipt')!=receipt or receipt['profileId']!=book['id'] or book['id']!=export_notebook(app)['book']['id']:
        raise ValueError('El cuaderno o su origen no corresponden a este perfil.')
    return snapshot


def download_exchange(app,exchange):
    with app.lock,writer_lock(app.config['runtime']/'review-writer.lock'):
        path=location(app.config,'web-exchanges',exchange)
        if not path.is_file():raise ValueError('Revisa el traslado antes de descargarlo.')
        snapshot=json.loads(path.read_text(encoding='utf-8'))
        validate_exchange_snapshot(snapshot,read_panel(app.config)['subjects'],notebook_id(app.config),exchange)
        before=copy.deepcopy(snapshot['base']);before.pop('transfer',None)
        if before!=export_notebook(app)['book']:
            raise ValueError('El cuaderno cambió desde la revisión. Pulsa Revisar traslado a la web antes de descargar una copia actualizada.')
        return {'book':snapshot['base']}


def _subject_value(s):
    if s is None:return None
    return {k:(s.get(k) is True if k=='archived' else s.get(k,'')) for k in ('name','archived','checkpoint','nextPractice')}


def _task_value(t,subjects):
    if t is None:return None
    return {'subject':subjects[t['subjectId']]['id'],'title':t['title'],'date':t['day'],
            'minutes':t.get('minutes',0),'detail':t.get('detail',''),
            **{k:t[k] for k in ('kind','dateStatus','proposedDay') if k in t},
            'status':'archivada' if t.get('archived') is True else 'realizada' if t.get('done') is True else 'pendiente'}


def _classes(book):
    return sorted([{k:c.get(k,'') for k in ('subjectId','day','start','end','kind','room')} for c in book['schedule']],key=encoded)


def preview_exchange(app,raw):
    book=validate_book(copy.deepcopy(raw))
    with app.lock, writer_lock(app.config['runtime']/'review-writer.lock'):
        snapshot=_read_snapshot(app,book)
        base=snapshot['base'];config=app.config
        current=export_notebook(app)['book'];managed=management_state(config);panel=read_panel(config)
        mapping=copy.deepcopy(snapshot['subjects']);rows=[];observed={};warnings=[]
        def observe(path):
            path=Path(path).resolve();observed[str(path)]=b64(contents(path));return contents(path)
        observe(config['path']);observe(config['panel_file'])
        for relative in (PLAN,SCHEDULE):observe(note_path(config,relative))
        def add(kind,key,label,before,local,incoming,operation):
            def comparable(value):
                if kind=='note' and isinstance(value,str):return value.replace('\r\n','\n')
                if kind=='note' and isinstance(value,dict):return {k:comparable(v) if k=='content' else v for k,v in value.items()}
                return value
            if comparable(before)==comparable(incoming) or comparable(local)==comparable(incoming):return
            conflict=comparable(local)!=comparable(before)
            rows.append({'id':stable('change',kind+':'+key),'kind':kind,'label':label,
                         'conflict':conflict,'suggested':None if conflict else 'web',
                         'local':local,'web':incoming,'operation':operation})
        base_subjects={s['id']:s for s in base['subjects']}
        current_subjects={s['id']:s for s in current['subjects']}
        incoming_subjects={s['id']:s for s in book['subjects']}
        for sid,s in incoming_subjects.items():
            if sid not in mapping:
                local_id='web-'+digest(sid)[:28]
                mapping[sid]={'id':local_id,'note':'01 Asignaturas/Mi grado web/'+local_id+'.md'}
            old=base_subjects.get(sid);now=current_subjects.get(sid)
            if old is None:
                existing=next((x for x in panel['subjects'] if x['id']==mapping[sid]['id']),None)
                add('subject',sid,s['name'],None,_subject_value(existing),_subject_value(s),{'subjectId':sid,'value':_subject_value(s),'new':True})
            else:
                for field in ('name','archived','checkpoint','nextPractice'):
                    add('subject',sid+':'+field,s['name']+' · '+{'name':'nombre','archived':'archivo','checkpoint':'último intento','nextPractice':'próximo paso'}[field],
                        _subject_value(old)[field],_subject_value(now)[field] if now else None,_subject_value(s)[field],
                        {'subjectId':sid,'field':field,'value':_subject_value(s)[field],'new':False})
            before_refs={r['id']:r for r in (old or {}).get('references',[])}
            live_subject=current_subjects.get(stable('subject',mapping[sid]['id']))
            local_refs={r['id']:r for r in (live_subject or {}).get('references',[])}
            incoming_refs={r['id']:r for r in s.get('references',[])}
            for rid in sorted(set(before_refs)|set(incoming_refs)):
                offered=incoming_refs.get(rid)
                if offered is None:offered={**before_refs[rid],'archived':True}
                add('reference',sid+':'+rid,s['name']+' · '+offered['title'],before_refs.get(rid),local_refs.get(rid),offered,
                    {'subjectId':sid,'value':offered})
            source=subject_source(config,mapping[sid]);raw_source=observe(source)
            old_ids=mapping[sid].get('canonicalTopics',[t['id'] for t in old['topics']]) if old else []
            incoming_topics={t['id']:t for t in s['topics']}
            for tid in incoming_topics:
                observe(config['runtime']/'web-topics'/(stable('topic',mapping[sid]['id']+':'+tid)+'.json'))
            if old_ids:
                if any(tid not in incoming_topics for tid in old_ids):
                    raise ValueError('Faltan partes de la ficha original de '+s['name']+'. Conserva sus temas originales para revisar la vuelta.')
                previous=''.join(t['content'] for t in old['topics'] if t['id'] in old_ids)
                offered=''.join(incoming_topics[tid]['content'] for tid in old_ids)
                local=raw_source.decode('utf-8-sig') if raw_source is not None else None
                def meta(t):return {**{k:t.get(k,False if k=='archived' else '') for k in ('id','title','filename','archived')},'origin':t.get('origin')}
                old_meta=[meta(t) for t in old['topics'] if t['id'] in old_ids]
                now_topics={t['id']:t for t in (now or {}).get('topics',[])}
                local_meta=[meta(now_topics.get(t['id'],t)) for t in old['topics'] if t['id'] in old_ids]
                new_meta=[meta(incoming_topics[tid]) for tid in old_ids]
                add('note',sid,s['name']+' · ficha original',{'content':previous,'topics':old_meta}, {'content':local,'topics':local_meta}, {'content':offered,'topics':new_meta},
                    {'path':str(source),'content':offered,'subjectId':sid,'topics':[{'version':1,**t,'canonical':True,'subject':mapping[sid]['id'],'relative':mapping[sid]['note'],
                        'partIndex':i,'contentLength':len(incoming_topics[t['id']]['content'].replace('\r\n','\n').replace('\r','\n')),
                        'noteSha':hashlib.sha256(offered.replace('\r\n','\n').replace('\r','\n').encode('utf-8')).hexdigest()} for i,t in enumerate(new_meta)]})
            for t in s['topics']:
                if t['id'] in old_ids:continue
                relative='Mi grado/Notas web/'+stable('notebook',book['id'])+'/'+stable('topic',sid+':'+t['id'])+'.md'
                path=note_path(config,relative)
                record=config['runtime']/'web-topics'/(stable('topic',mapping[sid]['id']+':'+t['id'])+'.json')
                previous_record={}
                if record.is_file():
                    previous_record=json.loads(record.read_text(encoding='utf-8'))
                    relative=previous_record['relative'];path=note_path(config,relative)
                    if not path.resolve().is_relative_to((config['vaults']['degree']/'Mi grado/Notas web').resolve()):raise ValueError('La nota web registrada está fuera de su carpeta.')
                actual=observe(path)
                previous=next((x for x in old['topics'] if x['id']==t['id']),None) if old else None
                def value(topic):return {**{k:topic.get(k,False if k=='archived' else '') for k in ('content','title','filename','archived')},'origin':topic.get('origin')} if topic is not None else None
                local_value=value({**previous_record,'content':actual.decode('utf-8-sig')}) if actual is not None else None
                add('note',sid+':'+t['id'],s['name']+' · '+t['title'],value(previous),local_value,value(t),
                    {'path':str(path),'content':t['content'],'subjectId':sid,'topic':{'id':t['id'],'subject':mapping[sid]['id'],'title':t['title'],'filename':t.get('filename',''),'archived':t.get('archived') is True,'relative':relative,'origin':t.get('origin')}})
        for sid,old in base_subjects.items():
            if sid not in incoming_subjects:
                now=current_subjects.get(sid)
                add('subject',sid+':archived',old['name']+' · retirada en la copia web',False,now.get('archived',False) if now else None,True,
                    {'subjectId':sid,'field':'archived','value':True,'new':False})
                warnings.append('Las notas de '+old['name']+' se conservan; retirar una asignatura de la copia propone archivarla, no borrar archivos.')
        aliases={stable('subject',v['id']):k for k,v in mapping.items()}
        for c in current['schedule']:c['subjectId']=aliases.get(c['subjectId'],c['subjectId'])
        old_tasks={t['id']:t for t in base['tasks']};new_tasks={t['id']:t for t in book['tasks']}
        local_tasks={stable('task',t['id']):t for t in managed['tasks']}
        legacy_old=[t for t in base['tasks'] if t['id'].startswith('task-previous-')]
        if legacy_old:
            offered=[new_tasks.get(t['id'],{**t,'archived':True}) for t in legacy_old]
            now=[t for t in current['tasks'] if t['id'].startswith('task-previous-')]
            if not now:
                converted=[]
                for t in legacy_old:
                    match=next((x for x in managed['tasks'] if x['id']=='task-'+digest(book['id']+':'+t['id'])[:32]),None)
                    if match:
                        converted.append({**t,'title':match['title'],'subjectId':next(k for k,v in mapping.items() if v['id']==match['subject']),
                                          'day':match['date'],'minutes':match['minutes'],'detail':match['detail'],
                                          'done':match['status']=='realizada','archived':match['status']=='archivada'})
                if converted:now=converted
            add('legacy','previous-plan','Plan del resumen anterior',legacy_old,now,offered,{'tasks':offered})
        for tid in set(old_tasks)|set(new_tasks):
            if tid.startswith('task-previous-') and tid in old_tasks:continue
            old=old_tasks.get(tid);incoming=new_tasks.get(tid)
            if incoming is None and old is not None:incoming={**old,'archived':True}
            if incoming is None:continue
            before=_task_value(old,mapping)
            local=local_tasks.get(tid)
            if local is None:
                possible='task-'+digest(book['id']+':'+tid)[:32]
                local=next((t for t in managed['tasks'] if t['id']==possible),None)
            value=_task_value(incoming,mapping)
            local_value={k:v for k,v in local.items() if k!='id'} if local else None
            local_id=local['id'] if local else 'task-'+digest(book['id']+':'+tid)[:32]
            add('task',tid,incoming['title'],before,local_value,value,{'id':local_id,'value':value})
        if managed['schedule'].get('issues') and _classes(base)!=_classes(book):
            raise ValueError('Revisa primero las filas no interpretadas del horario local. No se reemplazan al importar.')
        add('schedule','classes','Horario de clases',_classes(base),_classes(current),_classes(book),{'classes':_classes(book)})
        old_sessions={s['id']:s for s in base['sessions']}
        for session in book['sessions']:
            if old_sessions.get(session['id'])==session:continue
            subject=mapping[session['subjectId']]['id']
            capture={'id':web_capture_id(book['id'],session),'subject':subject,'kind':'Sesión revisada de Mi grado web',
                     'title':'Avance de '+incoming_subjects[session['subjectId']]['name'], 'details':session_details(session),
                     'created':session['createdAt'],'date':session['createdAt'][:10],
                     'source':'Mi grado web · '+book['id'],'evidence':'Declaración revisada; no confirma entrega ni dominio'}
            journal=app.store().journal_path(capture['id'])
            if journal.is_file():
                saved=json.loads(journal.read_text(encoding='utf-8'))
                if saved.get('state')=='complete' and app.store().verified(saved):continue
            add('session',session['id'],'Avance · '+incoming_subjects[session['subjectId']]['name'],None,None,{k:session[k] for k in FIELDS},
                {'capture':capture,'session':session,'bookId':book['id']})
        review='review-'+uuid.uuid4().hex
        state={'version':1,'id':review,'bookId':book['id'],'receipt':snapshot['receipt'],'subjects':mapping,
               'rows':rows,'observed':observed,'warnings':warnings,'state':'review','createdAt':madrid_time()}
        atomic_json(location(config,'web-reviews',review),state)
        return {'token':review,'label':book['label'],'changes':[{k:v for k,v in r.items() if k!='operation'} for r in rows],
                'subjectNames':{**{s['id']:s['name'] for s in panel['subjects']},**{s['id']:s['name'] for s in current['subjects']},**{s['id']:s['name'] for s in book['subjects']}},
                'warnings':warnings,'conflicts':sum(r['conflict'] for r in rows),'notice':'Revisa cada cambio. No se ha escrito en tus apuntes. Las ediciones posteriores a esta revisión detendrán el guardado.'}


def _safe_target(config,path):
    p=Path(path).resolve()
    if p==config['panel_file'].resolve():return p
    if p.parent==(config['runtime']/'web-topics').resolve() and re.fullmatch(r'topic-[a-f0-9]{32}\.json',p.name):return p
    if not p.is_relative_to(config['vaults']['degree'].resolve()) or p.suffix!='.md' or any(x in {'.git','.obsidian','.venv'} for x in p.parts):
        raise ValueError('Destino de intercambio fuera del alcance permitido.')
    return p


def _prepare_files(app,state,choices):
    config=app.config
    chosen=[r for r in state['rows'] if choices[r['id']]=='web']
    panel=read_panel(config);by_id={s['id']:s for s in panel['subjects']}
    mapping=state['subjects'];files={};captures=[];topic_records=[];created_subjects=set()
    shadow=location(config,'web-reviews',state['id']).parent/'stage'
    degree=shadow/'degree';runtime=shadow/'technical';degree.mkdir(parents=True,exist_ok=True);runtime.mkdir(exist_ok=True)
    staged={**config,'runtime':runtime,'panel_file':shadow/'panel.json','vaults':{'degree':degree,'hub':shadow/'hub'}}
    for relative in (PLAN,SCHEDULE):
        src=note_path(config,relative);target=degree/relative
        if src.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(src.read_bytes())
    for row in chosen:
        op=row['operation']
        if row['kind']=='subject':
            sid=mapping[op['subjectId']]['id']
            if op['new']:
                if sid not in by_id:
                    s=new_subject(op['value']['name'],mapping[op['subjectId']]['note']);s['id']=sid;panel['subjects'].append(s);by_id[sid]=s;created_subjects.add(sid)
                by_id[sid].update(op['value']);by_id[sid]['short']=by_id[sid]['name']
            else:
                if sid not in by_id:raise ValueError('La asignatura local fue retirada. Vuelve a revisar antes de importar.')
                by_id[sid][op['field']]=op['value']
                if op['field']=='name':by_id[sid]['short']=op['value']
    if not any(not s.get('archived') for s in panel['subjects']):raise ValueError('Conserva al menos una asignatura activa.')
    if len(panel['subjects'])>100:raise ValueError('Máximo 100 asignaturas entre las locales y las incorporadas.')
    if len({s['name'].casefold() for s in panel['subjects']})!=len(panel['subjects']):raise ValueError('Hay asignaturas con nombres repetidos; revisa la elección antes de guardar.')
    for s in panel['subjects']:
        source=subject_source(config,s)
        if s['id'] in created_subjects and not source.exists():files[str(source)]=('# '+s['name']+'\n').encode('utf-8')
    staged['panel_file'].write_text(json.dumps(panel,ensure_ascii=False,indent=2),encoding='utf-8')
    plan=management_state(staged)
    for row in chosen:
        op=row['operation']
        if row['kind']=='task':
            task={**op['value'],'id':op['id']}
            known=next((t for t in plan['tasks'] if t['id']==task['id']),None)
            if known is None:
                # save_task valida las nuevas filas antes de asignar su ID; aquí se mantiene el ID portable estable.
                from gestion import read_plan, validate_tasks, START, END
                path,before,body,match,value=read_plan(staged);value['tasks'].append(task);validate_tasks(staged,value['tasks'])
                block=START+'\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n'+END
                body=body[:match.start()]+block+body[match.end():] if match else body.rstrip()+'\n\n'+block+'\n'
                write_checked(staged,path,before,body);plan=management_state(staged)
            else:plan=save_task(staged,{'planSha':plan['planSha'],'task':task})
        elif row['kind']=='legacy':
            panel['pendingTasks']=[];panel['week']=[];panel['deadlines']=[]
            # El grupo se revisa completo: fechas generales no representadas se conservan.
            original=read_panel(config)
            def exported(t):return t.get('subject') in by_id and isinstance(t.get('title'),str)
            for key in ('pendingTasks','deadlines'):
                panel[key]=[t for t in original.get(key,[]) if not exported(t)]
            panel['week']=[{**d,'slots':[t for t in d.get('slots',[]) if not exported(t)]} for d in original.get('week',[])]
            for t in op['tasks']:
                task={'id':'task-'+digest(state['bookId']+':'+t['id'])[:32],**_task_value(t,mapping)}
                from gestion import read_plan, validate_tasks, START, END
                path,before,body,match,value=read_plan(staged);value['tasks']=[x for x in value['tasks'] if x['id']!=task['id']]+[task];validate_tasks(staged,value['tasks'])
                block=START+'\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n'+END
                body=body[:match.start()]+block+body[match.end():] if match else body.rstrip()+'\n\n'+block+'\n'
                write_checked(staged,path,before,body);plan=management_state(staged)
        elif row['kind']=='reference':
            sid=mapping[op['subjectId']]['id']
            if sid not in by_id:raise ValueError('Para traer el material, acepta también su nueva asignatura.')
            references=by_id[sid].setdefault('webReferences',[])
            references[:]=[r for r in references if r['id']!=op['value']['id']]+[op['value']]
        elif row['kind']=='note':
            if mapping[op['subjectId']]['id'] not in by_id:raise ValueError('Para traer sus notas, acepta también la nueva asignatura.')
            files[op['path']]=op['content'].encode('utf-8')
            if 'topic' in op:topic_records.append(op['topic'])
            topic_records.extend(op.get('topics',[]))
        elif row['kind']=='schedule':
            classes=[]
            days=['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
            for c in op['classes']:
                sid=mapping[c['subjectId']]['id']
                if sid not in by_id:raise ValueError('El horario necesita una asignatura que has decidido no incorporar.')
                classes.append({'subject':by_id[sid]['name'],'day':days[c['day']-1],**{k:c[k] for k in ('start','end','kind','room')}})
            live=management_state(staged)
            save_schedule(staged,{'scheduleSha':live['scheduleSha'],'group':live['schedule'].get('group',''),'period':live['schedule'].get('period',''),'classes':classes})
        elif row['kind']=='session':
            if op['capture']['subject'] not in by_id:raise ValueError('El avance necesita su asignatura. Revisa las elecciones.')
            captures.append(op)
    panel_data=json.dumps(panel,ensure_ascii=False,indent=2).encode('utf-8')
    from referencias import collect_references
    for subject in panel['subjects']:collect_references(config,subject)
    if json.loads(config['panel_file'].read_text(encoding='utf-8-sig'))!=panel:files[str(config['panel_file'].resolve())]=panel_data
    for relative in (PLAN,SCHEDULE):
        target=degree/relative;original=note_path(config,relative)
        if target.exists() and target.read_bytes()!=contents(original):files[str(original)]=target.read_bytes()
    for record in topic_records:
        registry=config['runtime']/'web-topics'/(stable('topic',record['subject']+':'+record['id'])+'.json')
        files[str(registry.resolve())]=(json.dumps({'version':1,**record},ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    # La identidad local y las rutas no se toman del archivo recibido.
    return files,captures,topic_records


def apply_exchange(app,token,choices):
    path=location(app.config,'web-reviews',token)
    if not path.is_file():raise ValueError('Vuelve a revisar el cuaderno antes de guardar.')
    with app.lock, writer_lock(app.config['runtime']/'review-writer.lock'):
        state=json.loads(path.read_text(encoding='utf-8'))
        ids={r['id'] for r in state['rows']}
        if not isinstance(choices,dict) or set(choices)!=ids or any(v not in ('local','web') for v in choices.values()):
            raise ValueError('Elige conservar local o incorporar web para cada cambio, incluidos los conflictos.')
        if state.get('choices') is not None and state['choices']!=choices:raise ValueError('El guardado ya empezó con otras elecciones. Reintenta con las mismas o vuelve a revisar.')
        if state['state']=='complete':return {'saved':True,'duplicate':True,'files':len(state['files']),'sessions':len(state['captures']),'backup':str(path.parent/'before')}
        if state['state']=='review':
            for target,before in state['observed'].items():
                if contents(target)!=unb64(before):raise ValueError('Una fuente cambió después de la revisión. No se ha escrito: vuelve a seleccionar el archivo y revisa sus cambios.')
            files,captures,topic_records=_prepare_files(app,state,choices)
            for target,before in state['observed'].items():
                if contents(target)!=unb64(before):raise ValueError('Una fuente cambió al preparar el guardado. No se ha escrito; vuelve a revisar.')
            previous={target:state['observed'].get(str(Path(target).resolve())) for target in files}
            for target,data in files.items():
                _safe_target(app.config,target)
                if str(Path(target).resolve()) not in state['observed']:
                    # Solo una ficha nueva de una asignatura nueva puede no existir en la revisión.
                    if contents(target) is not None:raise ValueError('Apareció una nota nueva desde la revisión. Vuelve a revisar.')
                    previous[target]=None
                backup=path.parent/'before'/(digest(target)+'.bak')
                if previous[target] is not None:
                    backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(unb64(previous[target]))
                    if backup.read_bytes()!=unb64(previous[target]):raise ValueError('No se pudo comprobar una copia anterior.')
            state.update(state='applying',choices=choices,files={k:b64(v) for k,v in files.items()},before=previous,captures=captures,topics=topic_records)
            atomic_json(path,state)
        # Recuperación por archivo: no reemplazar ediciones posteriores a un fallo parcial.
        for target,before in state['observed'].items():
            if target not in state['files'] and contents(target)!=unb64(before):
                raise ValueError('Otra fuente cambió desde la revisión. Se conserva; vuelve a revisar antes de continuar.')
        for target,after in state['files'].items():
            actual=contents(_safe_target(app.config,target))
            if actual not in (unb64(state['before'][target]),unb64(after)):
                raise ValueError('Una fuente cambió durante un guardado parcial. Sus ediciones se conservan; revisa antes de continuar.')
        for target,after in state['files'].items():
            p=_safe_target(app.config,target);data=unb64(after)
            if contents(p)!=data:write_checked(app.config,p,unb64(state['before'][target]),data.decode('utf-8'))
            if contents(p)!=data:raise RuntimeError('Un archivo no confirmó su contenido; reintenta el mismo guardado.')
        for op in state['captures']:
            result=app.save(op['capture'])
            if not (result.get('saved') and result.get('saveState')=='complete' and result.get('journalLinked')):
                raise RuntimeError('El avance no confirmó nota y diario. Reintenta el mismo guardado.')
            registry=app.config['runtime']/'web-results'/(op['capture']['id']+'.json')
            atomic_json(registry,{'version':1,'bookId':op['bookId'],'session':op['session'],'capture':op['capture']})
        state.update(state='complete',completedAt=madrid_time());atomic_json(path,state)
        return {'saved':True,'duplicate':False,'files':len(state['files']),'sessions':len(state['captures']),'backup':str(path.parent/'before')}
