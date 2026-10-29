"""Capturas Markdown recuperables. No interpreta declaraciones ni acredita aprendizaje."""
from contextlib import contextmanager
from rutas import Path
from urllib.parse import quote
import base64, datetime as dt, hashlib, json, os, re, subprocess

SUBJECTS = {'general': 'General / disponibilidad'}
FIELDS = ('id','subject','kind','title','date','evidence','source','details','created','time','timezone')

def clean(raw):
    if not isinstance(raw, dict): raise ValueError('Captura inválida')
    capture={}
    for field in FIELDS:
        value=raw.get(field,'')
        if value is None: value=''
        if not isinstance(value,str): raise ValueError('Campo inválido: '+field)
        capture[field]=value.strip()
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{4,100}',capture['id']): raise ValueError('Identificador inválido')
    if capture['subject'] not in SUBJECTS: raise ValueError('Asignatura inválida')
    if not capture['title'] or not capture['details']: raise ValueError('Faltan título o detalle')
    limits={'title':160,'details':2000000,'source':500,'kind':160,'evidence':160,'created':100}
    for field,limit in limits.items():
        if len(capture[field])>limit: raise ValueError('Campo demasiado largo: '+field)
        if field!='details' and ('\n' in capture[field] or '\r' in capture[field]): raise ValueError('El campo debe ocupar una línea: '+field)
    if capture['date']:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',capture['date']): raise ValueError('Fecha inválida; usa YYYY-MM-DD')
        dt.date.fromisoformat(capture['date'])
    if capture['time'] and (not capture['date'] or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',capture['time'])):
        raise ValueError('La hora requiere fecha y formato HH:mm')
    capture['timezone']=capture['timezone'] or 'Europe/Madrid'
    if capture['timezone']!='Europe/Madrid': raise ValueError('Zona no admitida; usa Europe/Madrid')
    if capture['time']: event_at(capture)
    return capture

def digest(capture):
    # Los vacíos nuevos conservan la huella de las capturas anteriores a esta versión.
    value={k:capture.get(k,'') for k in FIELDS if k not in ('time','timezone')}
    if capture.get('time'): value.update(time=capture['time'],timezone=capture.get('timezone') or 'Europe/Madrid')
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def event_at(capture):
    if not capture.get('time'): return None
    wall=dt.datetime.fromisoformat(capture['date']+'T'+capture['time'])
    try:
        from zoneinfo import ZoneInfo
        zone=ZoneInfo('Europe/Madrid')
        candidates=[]
        for fold in (0,1):
            aware=wall.replace(tzinfo=zone,fold=fold)
            if aware.astimezone(dt.timezone.utc).astimezone(zone).replace(tzinfo=None)==wall:
                candidates.append(aware)
        if not candidates: raise ValueError('La hora no existe por el cambio horario')
        if len({c.utcoffset() for c in candidates})>1: raise ValueError('Hora ambigua por cambio horario; indica una hora inequívoca')
        return candidates[0].isoformat(timespec='minutes')
    except (ImportError,KeyError):
        if os.name!='nt': raise ValueError('Faltan datos de zona horaria para validar el plazo')
        # Valores ya validados numéricamente; no se interpola texto libre en PowerShell.
        stamp=wall.strftime('%Y-%m-%dT%H:%M')
        script="$z=[TimeZoneInfo]::FindSystemTimeZoneById('Romance Standard Time'); $d=[datetime]::ParseExact('"+stamp+"','yyyy-MM-ddTHH:mm',[Globalization.CultureInfo]::InvariantCulture); if($z.IsInvalidTime($d)){throw 'Hora inexistente por cambio horario'}; if($z.IsAmbiguousTime($d)){throw 'Hora ambigua por cambio horario'}; [DateTimeOffset]::new($d,$z.GetUtcOffset($d)).ToString('yyyy-MM-ddTHH:mmzzz')"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=10)
        if result.returncode: raise ValueError('Hora inexistente o ambigua por cambio horario')
        return result.stdout.strip()

def literal(text):
    return text.replace('[[','\\[\\[').replace('obsidian://','obsidian\\://')

def process_alive(pid):
    if pid<=0: return True
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle: return ctypes.get_last_error()!=87  # Sin certeza de ausencia, conservar el bloqueo.
        try:
            exit_code=ctypes.c_ulong()
            return not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)) or exit_code.value==259
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid,0); return True
    except ProcessLookupError: return False
    except PermissionError: return True

def recover_stale_lock(path):
    if not path.exists(): return
    before=path.read_bytes()
    try: pid=int(before.decode().strip())
    except (ValueError,UnicodeError): return
    if not process_alive(pid) and path.exists() and path.read_bytes()==before: path.unlink()

@contextmanager
def writer_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    recover_stale_lock(path)
    try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise RuntimeError('Hay otro guardado en curso; reintenta sin cambiar el identificador')
    try:
        os.write(fd,str(os.getpid()).encode())
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        if path.exists() and path.read_bytes()==str(os.getpid()).encode(): path.unlink()

class CaptureStore:
    def __init__(self,memory,config,degree,hub,captures):
        self.memory=memory
        self.config=Path(config)
        self.degree=Path(degree).resolve()
        self.hub=Path(hub).resolve()
        self.captures=Path(captures).resolve()
        self.cfg=memory.read_json(self.config)
        self.config_sha=memory.file_hash(self.config)
        self.operations=Path(self.cfg['state']).resolve().parent/'capturas-operaciones'
        self.base=memory.Memory(self.config)

    def uri(self,path):
        path=Path(path).resolve()
        vault=self.degree if path.is_relative_to(self.degree) else self.hub
        return 'obsidian://open?vault='+quote(vault.name)+'&file='+quote(path.relative_to(vault).as_posix())

    def issue(self,code,path,message,kind='capture'):
        return {'code':code,'kind':kind,'path':Path(path).as_posix(),'url':self.uri(path) if Path(path).resolve().is_relative_to(self.degree) or Path(path).resolve().is_relative_to(self.hub) else '', 'message':message,'severity':'warning'}

    def journal_path(self,ident):
        # 96 bits y validación del ID completo: rutas breves incluso con los
        # temporales del guardado protegido en Windows.
        return self.operations/hashlib.sha256(ident.encode()).hexdigest()[:24]/'journal.json'

    def validate_record(self,record,journal):
        original=clean(record['originalCapture'])
        if record.get('version')!=2 or record['id']!=original['id'] or record['requestSha']!=digest(original) or self.journal_path(record['id'])!=Path(journal):
            raise ValueError('Registro de recuperación inválido')
        note=Path(record['notePath']).resolve(); diary=Path(record['diaryPath']).resolve()
        if note.parent!=self.captures or not self.base.allowed(note) or diary.parent!=self.hub/'Notas diarias' or not self.base.allowed(diary):
            raise ValueError('Destino de recuperación fuera del alcance autorizado')
        if Path(record['checkpointPath']).resolve()!=Path(journal).with_name('checkpoint.json').resolve(): raise ValueError('Punto de recuperación inválido')
        if Path(record['noteOperation']['path']).resolve()!=note or Path(record['diaryOperation']['path']).resolve()!=diary: raise ValueError('Operaciones de recuperación incoherentes')
        if record['noteOperation']['id']!='captura.'+original['id'] or not record['diaryOperation']['id'].startswith('diario.'+original['id']): raise ValueError('Identidad de operación inválida')
        return record

    def metadata(self,path):
        text=path.read_text(encoding='utf-8-sig').replace('\r\n','\n')
        match=re.search(r'<!--\s*captura-meta:(.*?)-->',text,re.S)
        if not match:
            if 'captura-meta:' in text or re.search(r'^capture_id:',text,re.M): raise ValueError('Faltan metadatos de recuperación de la captura')
            return None,text
        meta=json.loads(base64.b64decode(match[1].strip(),validate=True))
        if not isinstance(meta,dict) or not isinstance(meta.get('capture'),dict): raise ValueError('Metadatos de captura inválidos')
        original=clean(meta['capture'])
        if meta.get('sha256')!=digest(original): raise ValueError('La huella de origen de la captura no coincide')
        at=dt.datetime.fromisoformat(meta['savedAt'])
        if at.tzinfo is None: raise ValueError('Fecha de captura sin zona horaria')
        meta['capture']=original
        return meta,text

    def visible(self,meta,text):
        item=dict(meta['capture'])
        heading=re.search(r'^# ([^\n]+)',text,re.M)
        if heading: item['title']=heading[1].strip()
        properties={}
        if text.startswith('---\n') and '\n---\n' in text[4:]:
            block=text[4:].split('\n---\n',1)[0]
            for line in block.splitlines():
                field=re.match(r'^([A-Za-z_]+):\s*(.*)$',line)
                if not field: continue
                value=field[2].strip()
                if value.startswith('"'):
                    try: value=json.loads(value)
                    except ValueError: continue
                if isinstance(value,str): properties[field[1]]=value
        names={'kind':('tipo_novedad','Tipo'),'date':('fecha_evento','Fecha del evento'),'time':('hora_evento','Hora del evento'),'timezone':('zona_horaria','Zona horaria'),'evidence':('estado_declarado','Estado declarado'),'source':('fuente','Fuente declarada')}
        for key,(prop,label) in names.items():
            if prop in properties: item[key]=properties[prop]
            else:
                line=re.search(r'^'+re.escape(label)+r':\s*([^\n]*)',text,re.M)
                if line: item[key]=line[1].strip()
        subject=properties.get('asignatura')
        if subject:
            inverse={value:key for key,value in SUBJECTS.items()}
            item['subject']=inverse.get(subject,subject if subject in SUBJECTS else item['subject'])
        if item['date']=='sin indicar': item['date']=''
        if item['source']=='sin aportar': item['source']=''
        detail=text.split('## Detalle declarado\n',1)
        if len(detail)==2:
            marker='<!-- memoria:captura.'+meta['capture']['id']+' -->'
            item['details']=detail[1].strip().removesuffix(marker).rstrip()
        # Las propiedades editadas se muestran literalmente; nunca se cambian las afirmaciones por inferencia.
        item['eventAt']=None
        if item.get('time'):
            try: item['eventAt']=event_at(clean(item))
            except ValueError: item['visibleValidationIssue']='Revisa fecha, hora o propiedades editadas en Obsidian'
        return item

    def verified(self,record):
        try:
            note=Path(record['notePath']); diary=Path(record['diaryPath'])
            meta,text=self.metadata(note)
            if not meta or meta['capture']['id']!=record['id'] or meta['sha256']!=record['requestSha']: return False
            note_marker='<!-- memoria:'+record['noteOperation']['id']+' -->'
            diary_text=diary.read_text(encoding='utf-8-sig')
            if note_marker not in text or '<!-- memoria:'+record['diaryOperation']['id']+' -->' not in diary_text or self.uri(note) not in diary_text: return False
            checkpoint=self.memory.read_json(record['checkpointPath'])
            for operation in (record['noteOperation'],record['diaryOperation']):
                expected=self.memory.hash_bytes(json.dumps(operation,sort_keys=True,ensure_ascii=False).encode())
                if checkpoint.get('applied',{}).get(operation['id'])!=expected: return False
            return True
        except (OSError,ValueError,KeyError,TypeError): return False

    def legacy_complete(self,meta,path,text):
        try:
            diary=self.hub/'Notas diarias'/(meta['savedAt'][:10]+'.md')
            diary_text=diary.read_text(encoding='utf-8-sig')
            point=self.memory.read_json(self.cfg['state'])
            ids=('captura.'+meta['capture']['id'],'diario.'+meta['capture']['id'])
            return all(ident in point.get('applied',{}) for ident in ids) and '<!-- memoria:'+ids[0]+' -->' in text and '<!-- memoria:'+ids[1]+' -->' in diary_text and self.uri(path) in diary_text,diary
        except (OSError,ValueError,KeyError,TypeError): return False,None

    def decode(self,path):
        path=Path(path).resolve()
        if path.parent != self.captures or not self.base.allowed(path):
            raise ValueError('Captura fuera del alcance permitido')
        meta,text=self.metadata(path)
        if not meta: return None
        item=self.visible(meta,text)
        journal=self.journal_path(meta['capture']['id'])
        if journal.exists():
            record=self.validate_record(self.memory.read_json(journal),journal)
            complete=record.get('state')=='complete' and self.verified(record)
            diary=Path(record['diaryPath'])
        else: complete,diary=self.legacy_complete(meta,path,text)
        item.update(saved=complete,saveState='complete' if complete else 'incomplete',journalLinked=complete,
                    savedAt=meta['savedAt'],path=path.as_posix(),url=self.uri(path),modified=path.stat().st_mtime_ns,
                    diaryPath=diary.as_posix() if diary else None,diaryUrl=self.uri(diary) if diary else None,
                    retryPayload=meta['capture'])
        return item

    def read_all(self):
        items=[]; capture_issues=[]; journal_issues=[]
        for path in sorted(self.captures.glob('*.md')):
            try:
                item=self.decode(path)
                if item:
                    items.append(item)
                    if not item['saved']: journal_issues.append(self.issue('save_incomplete',path,'El guardado necesita completar o comprobar el enlace al diario y su punto de revisión.','journal'))
                    if item.get('visibleValidationIssue'): capture_issues.append(self.issue('visible_fields_invalid',path,item['visibleValidationIssue']))
            except Exception:
                capture_issues.append(self.issue('capture_metadata_invalid',path,'No se pudo interpretar esta captura; se conserva intacta y las demás siguen disponibles.'))
        if self.operations.exists():
            for journal in sorted(self.operations.glob('*/journal.json')):
                try:
                    record=self.validate_record(self.memory.read_json(journal),journal)
                    if record.get('state')!='complete':
                        issue=self.issue('operation_pending',journal,'Hay una operación de guardado pendiente de recuperar.','journal')
                        issue.update(captureId=record.get('id'),retryPayload=record.get('originalCapture'))
                        journal_issues.append(issue)
                except Exception: journal_issues.append(self.issue('journal_invalid',journal,'Registro de recuperación no interpretable; no se modifica automáticamente.','journal'))
        return sorted(items,key=lambda c:c['savedAt']),capture_issues,journal_issues

    def note_text(self,capture,at):
        meta={'version':2,'capture':capture,'savedAt':at,'sha256':digest(capture)}
        encoded=base64.b64encode(json.dumps(meta,ensure_ascii=False).encode()).decode()
        properties={'tipo':'nota-de-clase','areas':['carrera'],'estado':'pendiente de verificar','creado':at[:10],'verificado':'','capture_id':capture['id'],'asignatura':SUBJECTS[capture['subject']],'tipo_novedad':capture['kind'],'fecha_evento':capture['date'],'hora_evento':capture['time'],'zona_horaria':capture['timezone'],'estado_declarado':capture['evidence'],'fuente':capture['source']}
        text='---\n'+''.join(key+': '+json.dumps(value,ensure_ascii=False)+'\n' for key,value in properties.items())+'---\n\n# '+literal(capture['title'])+'\n\n<!-- captura-meta:'+encoded+' -->\n\nGuardada: '+at+'\n\nEsta entrada conserva una declaración del usuario. No acredita por sí sola entrega ni dominio autónomo.\n\n## Detalle declarado\n'+literal(capture['details'])
        return text

    def diary_operation(self,capture,path,day,recovery=False):
        ident='diario.'+capture['id']+('.recuperacion.'+day if recovery else '')
        prefix='Recuperación del enlace a una captura anterior' if recovery else 'Nota de clase / novedad declarada'
        text='- '+prefix+' en '+SUBJECTS[capture['subject']]+': ['+literal(capture['title']).replace('[','').replace(']','')+']('+self.uri(path)+'). Pendiente de contrastar su contenido.'
        return {'path':str(self.hub/'Notas diarias'/(day+'.md')),'id':ident,'text':text}

    def save(self,raw):
        capture=clean(raw)
        journal=self.journal_path(capture['id'])
        with writer_lock(self.operations/'writer.lock'):
            if journal.exists():
                record=self.validate_record(self.memory.read_json(journal),journal)
                if record['requestSha']!=digest(capture): raise ValueError('La captura ya existe con otro contenido; crea una corrección nueva')
                if record.get('state')=='complete' and self.verified(record): return self.decode(record['notePath'])
            else:
                existing=[]
                for path in self.captures.glob('*.md'):
                    try:
                        meta,text=self.metadata(path)
                        if meta and meta['capture']['id']==capture['id']: existing.append((path,meta,text))
                    except Exception: continue
                if len(existing)>1: raise RuntimeError('El identificador aparece en más de una nota; revisar sin sobrescribir')
                now=self.memory.madrid_time()
                if existing:
                    path,meta,text=existing[0]
                    if meta['sha256']!=digest(capture): raise ValueError('La captura ya existe con otro contenido; crea una corrección nueva')
                    at=meta['savedAt']
                    marker='<!-- memoria:captura.'+capture['id']+' -->'
                    if marker not in text: raise RuntimeError('Falta el marcador de guardado de la nota existente; revisar sin reemplazarla')
                    note_text=text.split(marker,1)[0].rstrip()
                    original_day=at[:10]
                    diary=self.hub/'Notas diarias'/(original_day+'.md')
                    day=original_day if diary.exists() else now[:10]
                else:
                    at=now; day=now[:10]
                    path=self.captures/(day+' - '+hashlib.sha256(capture['id'].encode()).hexdigest()[:24]+'.md')
                    if path.exists(): raise RuntimeError('El destino de la captura ya existe y necesita revisión; no se reemplaza')
                    note_text=self.note_text(capture,at)
                record={'version':2,'id':capture['id'],'requestSha':digest(capture),'originalCapture':capture,'createdAt':at,'state':'pending','notePath':str(path),'diaryPath':str(self.hub/'Notas diarias'/(day+'.md')),'checkpointPath':str(journal.with_name('checkpoint.json')),'noteOperation':{'path':str(path),'id':'captura.'+capture['id'],'text':note_text},'diaryOperation':self.diary_operation(capture,path,day,recovery=day!=at[:10])}
                if not self.base.allowed(path) or not self.base.allowed(Path(record['diaryPath'])): raise RuntimeError('Destino fuera del alcance autorizado')
                self.memory.atomic_json(journal,record)
            now=self.memory.madrid_time()
            diary=Path(record['diaryPath'])
            if not diary.exists() and diary.stem!=now[:10]:
                record['diaryOperation']=self.diary_operation(record['originalCapture'],Path(record['notePath']),now[:10],recovery=True)
                record['diaryPath']=record['diaryOperation']['path']
                record['state']='pending'
                self.memory.atomic_json(journal,record)
            note=Path(record['notePath'])
            if record.get('state')=='complete' and not note.exists(): raise RuntimeError('La nota fue retirada después del guardado; revisar antes de recuperarla')
            if note.exists():
                meta,text=self.metadata(note)
                if not meta or meta['capture']['id']!=record['id'] or meta['sha256']!=record['requestSha']: raise RuntimeError('La nota cambió su identidad; no se reemplaza')
                if '<!-- memoria:'+record['noteOperation']['id']+' -->' not in text: raise RuntimeError('El marcador de la nota fue editado; revisar sin reemplazar contenido')
            self.apply_record(journal,record)
            record['state']='complete'; record['completedAt']=self.memory.madrid_time()
            if not self.verified(record): raise RuntimeError('Falta verificar nota, diario o punto; el guardado sigue pendiente')
            self.memory.atomic_json(journal,record)
            item=self.decode(record['notePath'])
            if not item or not item['saved']: raise RuntimeError('Guardado completo sin verificar')
            return item

    def apply_record(self,journal,record):
        if self.memory.file_hash(self.config)!=self.config_sha: raise RuntimeError('Cambió el alcance autorizado; releer antes de guardar')
        paths=[Path(record['notePath']),Path(record['diaryPath'])]
        if not all(self.base.allowed(path) for path in paths): raise RuntimeError('Destino fuera del alcance autorizado')
        cfg=dict(self.cfg)
        cfg.update(files=[str(path) for path in paths],folders=[],state=record['checkpointPath'])
        config=journal.with_name('config.json')
        self.memory.atomic_json(config,cfg)
        class PlannedTargetsMemory(self.memory.Memory):
            def snapshot(self):
                # Solo estos destinos pueden ser nuevos. Los errores de lectura de destinos existentes siguen bloqueando.
                exact=self.exact
                self.exact={name for name in exact if Path(name).exists()}
                try: return super().snapshot()
                finally: self.exact=exact
        m=PlannedTargetsMemory(config)
        recover_stale_lock(m.state.with_suffix('.lock'))
        scan=m.scan()
        reviewed={path:{'status':'propia','note':'Lectura y comparación para confirmar exclusivamente esta captura y su enlace; no revisión académica.'} for path in scan['changed']}
        for path in scan['removed']:
            if Path(path).exists(): raise RuntimeError('Cambió el alcance del guardado; revisar el punto anterior')
            reviewed[path]={'status':'retirada-confirmada','note':'Destino anterior ausente; la operación conserva la captura y recupera su enlace en el diario actual.'}
        plan={'reviewed':reviewed,'summary':'Guardar o recuperar una declaración explícita y comprobar sus dos destinos.','limits':['El contenido académico queda pendiente de contraste.'],'errors':[],'operations':[record['noteOperation'],record['diaryOperation']]}
        m.apply(scan,plan)
