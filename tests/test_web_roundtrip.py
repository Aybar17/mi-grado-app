"""Prueba del recorrido completo sin archivos ni cuentas de personas reales."""
from pathlib import Path
from unittest.mock import patch
import copy
import json
import tempfile
import unittest
import hashlib
import io
import zipfile
import threading
import os
import shutil
from rutas import Path as FilePath
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from perfiles import create_profile
from puente_memoria import Application, create_server
from gestion import management_state, save_task
from intercambio_web import prepare_exchange, preview_exchange, apply_exchange, download_exchange
import intercambio_web as exchange
from copias import export_backup, preview_backup, restore_backup, unpack
from configuracion import load_config
from cuaderno_web import export_notebook


class RoundTripTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ida-vuelta-ficticia-')
        self.root=Path(self.tmp.name).resolve()
        self.config=create_profile(self.root/'Perfil/config.json',self.root/'Apuntes',['Datos'])
        self.app=Application(self.config)
        subject=management_state(self.config)['subjects'][0]
        self.local_id=subject['id'];self.note=self.config['vaults']['degree']/subject['note']
        self.note.write_text('# Datos\n\nTexto original.\n',encoding='utf-8')
        before=management_state(self.config)
        save_task(self.config,{'planSha':before['planSha'],'task':{'id':'','subject':self.local_id,'title':'Primer intento','date':'','minutes':60,'detail':'Material original','status':'pendiente'}})
        self.book=prepare_exchange(self.app)['book'];self.sid=self.book['subjects'][0]['id']

    def tearDown(self):self.tmp.cleanup()

    def notes(self):return {str(p):p.read_bytes() for v in self.config['vaults'].values() for p in v.rglob('*.md')}

    def test_exam_metadata_survives_web_local_web_without_changing_current_date(self):
        book=copy.deepcopy(self.book)
        book['tasks'][0].update(kind='exam',dateStatus='declared',day='2026-11-16',proposedDay='2026-11-17')
        review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        local=management_state(self.config)
        exam=local['tasks'][0]
        self.assertEqual(exam['date'],'2026-11-16')
        self.assertEqual(exam['proposedDay'],'2026-11-17')
        # A previous local editor must preserve the additive metadata as well.
        edited={k:v for k,v in exam.items() if k not in ('kind','dateStatus','proposedDay')}
        edited['title']='Título editado'
        save_task(self.config,{'planSha':local['planSha'],'task':edited})
        exported=prepare_exchange(self.app)['book']['tasks'][0]
        for key in ('kind','dateStatus','proposedDay','day'):
            self.assertEqual(exported[key],book['tasks'][0][key])
    def choose(self,review,conflict='local'):
        return {r['id']:r['suggested'] or conflict for r in review['changes']}

    def changed_book(self):
        book=copy.deepcopy(self.book)
        book['subjects'][0]['topics'][0]['content']='# Datos\n\nVersión revisada en la web.\n'
        book['subjects'][0]['topics'].append({'id':'topic-new-web01','title':'Segundo tema','content':'# Segundo tema\nTexto nuevo.','filename':'tema2.md','archived':False})
        book['tasks'][0].update(minutes=90,detail='Material revisado')
        book['tasks'].append({'id':'task-new-web01','subjectId':self.sid,'title':'Tarea sin duración aún','day':'','done':False,'archived':False,'minutes':0,'detail':'No inventar disponibilidad.'})
        book['schedule']=[{'id':'class-new-web01','subjectId':self.sid,'day':7,'start':'10:00','end':'11:00','kind':'','room':''}]
        book['sessions']=[{'id':'session-new-web01','subjectId':self.sid,'createdAt':'2026-10-16T10:00:00+02:00','source':'ai-reviewed','topicIds':['topic-new-web01'],
                           'attempt':'Mi intento ficticio','help':'Una pista','result':'Resuelto con ayuda','nextStep':'Repetir otro caso sin pista'}]
        return book

    def test_roundtrip_preserves_four_fields_and_is_idempotent(self):
        book=self.changed_book();before=self.notes()
        review=preview_exchange(self.app,book)
        self.assertEqual(self.notes(),before);self.assertEqual(review['conflicts'],0)
        saved=apply_exchange(self.app,review['token'],self.choose(review))
        self.assertTrue(saved['saved']);self.assertEqual(saved['sessions'],1)
        self.assertEqual(self.note.read_text(encoding='utf-8'),book['subjects'][0]['topics'][0]['content'])
        imported=list((self.config['vaults']['degree']/'Mi grado/Notas web').rglob('*.md'))
        self.assertEqual(len(imported),1);self.assertEqual(imported[0].read_text(encoding='utf-8'),'# Segundo tema\nTexto nuevo.')
        state=management_state(self.config);self.assertEqual(len(state['tasks']),2)
        self.assertEqual({t['minutes'] for t in state['tasks']},{0,90})
        self.assertEqual(state['schedule']['classes'][0]['day'],'Domingo');self.assertFalse(state['schedule']['issues'])
        capture=self.app.state()['captures'][0]
        self.assertTrue(capture['saved'] and capture['journalLinked']);self.assertIn('Resuelto con ayuda',capture['details'])
        after=self.notes();again=apply_exchange(self.app,review['token'],self.choose(review))
        self.assertTrue(again['duplicate']);self.assertEqual(self.notes(),after)
        self.assertEqual(preview_exchange(self.app,book)['changes'],[])
        exported=prepare_exchange(self.app)['book']
        self.assertTrue(any(t['id']=='topic-new-web01' and t['content']=='# Segundo tema\nTexto nuevo.' for t in exported['subjects'][0]['topics']))
        restored=next(s for s in exported['sessions'] if s['id']==book['sessions'][0]['id'])
        for k in ('attempt','help','result','nextStep'):self.assertEqual(restored[k],book['sessions'][0][k])
        self.assertEqual(restored['topicIds'],book['sessions'][0]['topicIds'])

    def test_deep_restoration_preserves_identity_notes_and_verified_capture(self):
        book=self.changed_book()
        review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        data=export_backup(self.app);info=preview_backup(data)
        owned=FilePath(self.root/'Restauraciones de prueba')
        destination=owned
        while len(str(destination)) < 310:
            destination/='Carpeta ficticia con apuntes ñ'
        try:
            restored=restore_backup(data,info['sha'],destination/'Cuaderno recuperado')
            config=load_config(restored['config']);app=Application(config)
            copied=export_notebook(app)['book']
            self.assertEqual(copied['id'],book['id'])
            self.assertFalse(str(config['path']).startswith(chr(92)*2+'?'+chr(92)))
            self.assertTrue(any(t['id']=='topic-new-web01' for t in copied['subjects'][0]['topics']))
            capture=app.state()['captures'][0]
            self.assertTrue(capture['saved'] and capture['journalLinked'])
            for key in ('attempt','help','result','nextStep'):
                self.assertEqual(copied['sessions'][0][key],book['sessions'][0][key])
            self.assertEqual(preview_exchange(app,book)['changes'],[])
            self.assertTrue(preview_backup(export_backup(app))['files'] > 0)
            self.assertEqual(len(self.app.state()['captures']),1)
            with patch('copias.user_home',return_value=Path(str(destination))):
                default_copy=restore_backup(data,info['sha'])
            self.assertTrue(default_copy['saved'])
        finally:
            self.assertTrue(owned.resolve().is_relative_to(FilePath(self.root).resolve()))
            if owned.exists():shutil.rmtree(owned)

    def test_conflict_needs_choice_and_preserves_local_edits(self):
        book=copy.deepcopy(self.book);book['subjects'][0]['topics'][0]['content']='Cambio de la web'
        self.note.write_text('Cambio local manual',encoding='utf-8')
        review=preview_exchange(self.app,book)
        self.assertEqual(review['conflicts'],1)
        self.assertIsNone(review['changes'][0]['suggested'])
        with self.assertRaisesRegex(ValueError,'Elige'):apply_exchange(self.app,review['token'],{})
        apply_exchange(self.app,review['token'],self.choose(review))
        self.assertEqual(self.note.read_text(encoding='utf-8'),'Cambio local manual')
        other=preview_exchange(self.app,book)
        saved=apply_exchange(self.app,other['token'],self.choose(other,'web'))
        self.assertEqual(self.note.read_text(encoding='utf-8'),'Cambio de la web')
        self.assertTrue(any(p.read_bytes()==b'Cambio local manual' for p in Path(saved['backup']).glob('*.bak')))

    def test_change_after_review_never_writes(self):
        book=self.changed_book();review=preview_exchange(self.app,book)
        self.note.write_text('Edición mientras revisaba',encoding='utf-8');before=self.notes()
        with self.assertRaisesRegex(ValueError,'cambió'):apply_exchange(self.app,review['token'],self.choose(review))
        self.assertEqual(self.notes(),before)

    def interrupted(self):
        book=self.changed_book();review=preview_exchange(self.app,book);original=exchange.write_checked;calls=0
        def fail(config,path,before,content):
            nonlocal calls
            if config is self.config:
                calls+=1
                if calls==2:raise RuntimeError('Interrupción ficticia')
            return original(config,path,before,content)
        with patch.object(exchange,'write_checked',fail):
            with self.assertRaisesRegex(RuntimeError,'ficticia'):apply_exchange(self.app,review['token'],self.choose(review))
        return review

    def test_interrupted_import_resumes_after_restart_without_duplicates(self):
        review=self.interrupted();reopened=Application(self.config)
        result=apply_exchange(reopened,review['token'],self.choose(review))
        self.assertTrue(result['saved']);self.assertEqual(len(reopened.state()['captures']),1)
        self.assertEqual(len(management_state(self.config)['tasks']),2)

    def test_edit_during_interruption_is_kept(self):
        review=self.interrupted();self.note.write_text('Una edición posterior al fallo',encoding='utf-8');before=self.notes()
        with self.assertRaisesRegex(ValueError,'parcial'):apply_exchange(self.app,review['token'],self.choose(review))
        self.assertEqual(self.notes(),before)

    def test_foreign_or_forged_exchange_is_rejected_without_writes(self):
        before=self.notes()
        for change in ({'exchangeId':'../../archivo'},{'profileId':'book-foreign01'}):
            book=copy.deepcopy(self.book);book['transfer'].update(change)
            with self.assertRaises(ValueError):preview_exchange(self.app,book)
        book=copy.deepcopy(self.book);book['subjects'][0]['topics'][0]['id']='../nota'
        with self.assertRaises(ValueError):preview_exchange(self.app,book)
        self.assertEqual(self.notes(),before)

    def test_long_session_is_not_truncated(self):
        book=self.changed_book()
        for k in ('attempt','help','result','nextStep'):book['sessions'][0][k]=k+'x'*(12000-len(k))
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        capture=self.app.state()['captures'][0]
        for k in ('attempt','help','result','nextStep'):self.assertIn(book['sessions'][0][k],capture['details'])

    def test_backup_restores_imported_topics_and_complete_session_fields(self):
        book=self.changed_book()
        book['subjects'][0]['topics'][0].update(title='Ficha renombrada', archived=True)
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        before=self.notes();data=export_backup(self.app);info=preview_backup(data)
        files,_,_=unpack(data)
        self.assertTrue(any(n.startswith('web-topics/') for n in files))
        self.assertTrue(any(n.startswith('web-results/') for n in files))
        restored=restore_backup(data,info['sha'],self.root/'Recuperado')
        app=Application(load_config(restored['config']));copied=prepare_exchange(app)['book']
        topics=copied['subjects'][0]['topics']
        self.assertTrue(any(t['id']=='topic-new-web01' and t['content']=='# Segundo tema\nTexto nuevo.' for t in topics))
        self.assertEqual(topics[0]['title'],'Ficha renombrada');self.assertTrue(topics[0]['archived'])
        session=next(s for s in copied['sessions'] if s['id']==book['sessions'][0]['id'])
        for k in ('attempt','help','result','nextStep','topicIds'):self.assertEqual(session[k],book['sessions'][0][k])
        self.assertEqual(self.notes(),before)
        self.assertTrue(app.state()['captures'][0]['journalLinked'])

    def test_backup_rejects_web_registry_traversal_and_forged_session_before_writing(self):
        book=self.changed_book();review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        original,_,_=unpack(export_backup(self.app))
        topic=next(n for n in original if n.startswith('web-topics/'))
        result=next(n for n in original if n.startswith('web-results/'))
        for key,field,value in [(topic,'relative','../../Privado.md'),(result,'capture',{'id':'web-'+'a'*48,'subject':self.local_id})]:
            files=dict(original);record=json.loads(files[key]);record[field]=value
            files[key]=json.dumps(record,ensure_ascii=False).encode()
            manifest={'version':1,'files':{n:hashlib.sha256(body).hexdigest() for n,body in files.items() if n!='manifest.json'}}
            files['manifest.json']=json.dumps(manifest).encode()
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive:
                for name,body in files.items():archive.writestr(name,body)
            data=output.getvalue()
            with self.assertRaises(ValueError):restore_backup(data,hashlib.sha256(data).hexdigest(),self.root/'Invalid')
            self.assertFalse((self.root/'Invalid').exists())

    def test_backup_rejects_missing_imported_topic_instead_of_silent_loss(self):
        book=self.changed_book();review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        path=next((self.config['vaults']['degree']/'Mi grado/Notas web').rglob('*.md'))
        path.unlink()
        with self.assertRaisesRegex(ValueError,'Falta una nota web'):export_backup(self.app)
        reopened=Application(self.config)
        self.assertTrue(reopened.state()['panel']['materialIssues'])

    def test_imported_topic_can_be_studied_and_same_time_file_edits_refresh_its_text(self):
        book=self.changed_book();review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        first=self.app.state();material=first['panel']['subjects'][0]['materials'][0]
        self.assertEqual(material['title'],'Segundo tema');self.assertEqual(material['noteText'],'# Segundo tema\nTexto nuevo.')
        path=self.config['vaults']['degree']/material['path'];mtime=path.stat().st_mtime_ns
        old=path.read_bytes();new=old.replace(b'nuevo',b'OTRO!');self.assertEqual(len(old),len(new))
        path.write_bytes(new);os.utime(path,ns=(mtime,mtime))
        latest=self.app.state()['panel']['subjects'][0]['materials'][0]
        self.assertIn('OTRO!',latest['noteText']);self.assertNotEqual(latest['noteSha'],material['noteSha'])

    def test_topic_metadata_edit_after_review_is_preserved(self):
        book=self.changed_book();review=preview_exchange(self.app,book)
        apply_exchange(self.app,review['token'],self.choose(review))
        book=prepare_exchange(self.app)['book'];topic=next(t for t in book['subjects'][0]['topics'] if t['id']=='topic-new-web01')
        topic['title']='Cambio desde la web';review=preview_exchange(self.app,book)
        registry=next(p for p in (self.config['runtime']/'web-topics').glob('*.json') if json.loads(p.read_text(encoding='utf-8'))['id']=='topic-new-web01')
        record=json.loads(registry.read_text(encoding='utf-8'));record['title']='Otra edición local'
        registry.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');before=registry.read_bytes()
        with self.assertRaisesRegex(ValueError,'cambió'):apply_exchange(self.app,review['token'],self.choose(review))
        self.assertEqual(registry.read_bytes(),before)

    def test_retry_after_final_receipt_failure_keeps_topic_metadata_and_session_once(self):
        book=self.changed_book();review=preview_exchange(self.app,book);original=exchange.atomic_json
        def fail_receipt(path,value):
            if value.get('state')=='complete':raise RuntimeError('Fallo ficticio del recibo final')
            return original(path,value)
        with patch.object(exchange,'atomic_json',fail_receipt):
            with self.assertRaisesRegex(RuntimeError,'recibo final'):apply_exchange(self.app,review['token'],self.choose(review))
        records={p:p.read_bytes() for p in (self.config['runtime']/'web-topics').glob('*.json')}
        self.assertTrue(records)
        reopened=Application(self.config);result=apply_exchange(reopened,review['token'],self.choose(review))
        self.assertTrue(result['saved']);self.assertEqual(len(reopened.state()['captures']),1)
        for path,before in records.items():self.assertEqual(path.read_bytes(),before)

    def test_markdown_comments_and_obsidian_links_survive_the_roundtrip(self):
        book=self.changed_book()
        book['sessions'][0]['attempt']='Intento con [[Tema]] y <!-- memoria:ejemplo-no-es-el-recibo -->\nobsidian://open?vault=Prueba'
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        exported=prepare_exchange(self.app)['book'];session=next(s for s in exported['sessions'] if s['id']==book['sessions'][0]['id'])
        self.assertEqual(session['attempt'],book['sessions'][0]['attempt'])

    def test_imported_origin_survives_local_export_and_zip_restore(self):
        book=self.changed_book();topic=book['subjects'][0]['topics'][-1]
        origin={'kind':'markdown-file','name':'tema2.md','contentHash':hashlib.sha256(topic['content'].encode()).hexdigest(),
                'importedAt':'2026-10-16T10:00:00Z','checkedAt':'2026-10-16T11:00:00Z','fileModifiedAt':''}
        topic['origin']=origin
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        exported=prepare_exchange(self.app)['book']
        self.assertEqual(next(t for t in exported['subjects'][0]['topics'] if t['id']==topic['id'])['origin'],origin)
        data=export_backup(self.app);info=preview_backup(data)
        restored=restore_backup(data,info['sha'],self.root/'ConOrigen')
        copied=prepare_exchange(Application(load_config(restored['config'])))['book']
        self.assertEqual(next(t for t in copied['subjects'][0]['topics'] if t['id']==topic['id'])['origin'],origin)

    def test_restored_zip_accepts_pending_return_and_preserves_original_profile(self):
        before=self.notes();data=export_backup(self.app);info=preview_backup(data)
        restored=restore_backup(data,info['sha'],self.root/'Recibido')
        app=Application(load_config(restored['config']))
        self.assertEqual(prepare_exchange(app)['book']['id'],self.book['id'])
        subject=management_state(app.config)['subjects'][0];note=app.config['vaults']['degree']/subject['note']
        note.write_text('Una edición después de restaurar',encoding='utf-8')
        book=self.changed_book();review=preview_exchange(app,book)
        self.assertEqual(review['conflicts'],1)
        apply_exchange(app,review['token'],self.choose(review,'web'))
        self.assertEqual(note.read_text(encoding='utf-8'),book['subjects'][0]['topics'][0]['content'])
        self.assertTrue(app.state()['captures'][0]['journalLinked']);self.assertEqual(self.notes(),before)
        second=export_backup(app);second_info=preview_backup(second)
        again=restore_backup(second,second_info['sha'],self.root/'RecibidoOtraVez')
        another=Application(load_config(again['config']))
        self.assertEqual(preview_exchange(another,book)['changes'],[])
        self.assertEqual(len(another.state()['captures']),1)

    def test_forged_snapshot_destinations_and_notebook_ids_rejected_before_restore(self):
        original,_,_=unpack(export_backup(self.app))
        name=next(n for n in original if n.startswith('web-exchanges/'))
        snapshot=json.loads(original[name]);sid=next(iter(snapshot['subjects']))
        for field,value in [('note','../Fuera.md'),('note','00 Dashboard/Otra ficha.md'),('id','asignatura-ajena')]:
            files=dict(original);bad=copy.deepcopy(snapshot);bad['subjects'][sid][field]=value
            files[name]=json.dumps(bad,ensure_ascii=False).encode()
            files['manifest.json']=json.dumps({'version':1,'files':{n:hashlib.sha256(body).hexdigest() for n,body in files.items() if n!='manifest.json'}}).encode()
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive:
                for key,body in files.items():archive.writestr(key,body)
            data=output.getvalue()
            with self.assertRaises(ValueError):restore_backup(data,hashlib.sha256(data).hexdigest(),self.root/'Invalid')
            self.assertFalse((self.root/'Invalid').exists())

    def test_backup_waits_for_interrupted_return_instead_of_losing_recovery(self):
        review=self.interrupted()
        with self.assertRaisesRegex(ValueError,'guardado interrumpido'):export_backup(self.app)
        apply_exchange(self.app,review['token'],self.choose(review))
        self.assertTrue(export_backup(self.app))

    def test_shortened_split_fiche_keeps_parts_names_archive_and_session_selection(self):
        self.note.write_text('a'*100001,encoding='utf-8')
        book=prepare_exchange(self.app)['book'];topics=book['subjects'][0]['topics']
        self.assertEqual(len(topics),2)
        topics[0]['content']='Primera parte reducida.\n'
        topics[1].update(content='Segunda parte reducida.\n',title='Referencia conservada',archived=True)
        book['sessions']=[{'id':'session-split-web01','subjectId':self.sid,'createdAt':'2026-10-16T12:00:00Z','source':'user','topicIds':[topics[1]['id']],
                           'attempt':'Intento sobre la segunda parte','help':'Sin ayuda declarada','result':'Por comprobar','nextStep':'Otro caso'}]
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        copied=prepare_exchange(self.app)['book'];new_topics=copied['subjects'][0]['topics']
        self.assertEqual([(t['id'],t['content'],t['title'],t['archived']) for t in new_topics],[(t['id'],t['content'],t['title'],t['archived']) for t in topics])
        self.assertEqual(copied['sessions'][0]['topicIds'],[topics[1]['id']])
        self.assertEqual(preview_exchange(self.app,book)['changes'],[])

    def test_manual_edit_of_split_fiche_keeps_every_character_and_prior_topic_ids(self):
        self.note.write_text('a'*100001,encoding='utf-8')
        book=prepare_exchange(self.app)['book'];topics=book['subjects'][0]['topics']
        topics[0]['content']='Primera parte.\n';topics[1]['content']='Segunda parte.\n'
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choose(review))
        manual='🧪'*60000+'\nUna edición local posterior.'
        self.note.write_text(manual,encoding='utf-8')
        result=prepare_exchange(self.app);copied=result['book']['subjects'][0]['topics']
        self.assertEqual(''.join(t['content'] for t in copied),manual)
        self.assertTrue({t['id'] for t in topics}<={t['id'] for t in copied})
        self.assertTrue(all(len(t['content'].encode('utf-16-le'))//2<=100000 for t in copied))
        self.assertTrue(any('editó en local' in warning for warning in result['warnings']))

    def test_new_subject_requires_acceptance_before_any_note_or_task_write(self):
        book=copy.deepcopy(self.book)
        book['subjects'].append({'id':'subject-new-web01','name':'Lógica','archived':False,'checkpoint':'Primer caso','nextPractice':'Otro caso',
                                 'topics':[{'id':'topic-new-subject01','title':'Tema nuevo','content':'# Lógica\nTexto ficticio.','filename':'logica.md','archived':False}]})
        book['tasks'].append({'id':'task-new-subject01','subjectId':'subject-new-web01','title':'Practicar','day':'','done':False,'minutes':0,'detail':'','archived':False})
        review=preview_exchange(self.app,book);choices=self.choose(review);before=self.notes()
        subject_row=next(r for r in review['changes'] if r['kind']=='subject')
        choices[subject_row['id']]='local'
        with self.assertRaises(ValueError):apply_exchange(self.app,review['token'],choices)
        self.assertEqual(self.notes(),before);self.assertEqual(len(management_state(self.config)['subjects']),1)
        choices[subject_row['id']]='web';apply_exchange(self.app,review['token'],choices)
        self.assertEqual(len(management_state(self.config)['subjects']),2)
        self.assertEqual(preview_exchange(self.app,book)['changes'],[])
        self.assertTrue(any(t['content']=='# Lógica\nTexto ficticio.' for s in prepare_exchange(self.app)['book']['subjects'] for t in s['topics']))

    def test_legacy_tasks_preserve_general_rows_and_repeat_without_duplicates(self):
        panel=json.loads(self.config['panel_file'].read_text(encoding='utf-8'))
        general={'id':'general-availability','subject':'general','title':'Disponibilidad por confirmar','date':''}
        legacy={'id':'legacy-practice01','subject':self.local_id,'title':'Práctica previa','date':'2026-10-17','minutes':75,'material':'Ejercicio elegido'}
        panel.update(pendingTasks=[general,legacy],week=[{'date':'2026-10-18','slots':[{'subject':'general','title':'Revisar disponibilidad'}]}],deadlines=[])
        self.config['panel_file'].write_text(json.dumps(panel,ensure_ascii=False),encoding='utf-8')
        book=prepare_exchange(self.app)['book'];task=next(t for t in book['tasks'] if t['id'].startswith('task-previous-'))
        task.update(title='Práctica revisada',done=True)
        review=preview_exchange(self.app,book);self.assertEqual(review['conflicts'],0)
        apply_exchange(self.app,review['token'],self.choose(review))
        after=json.loads(self.config['panel_file'].read_text(encoding='utf-8'))
        self.assertEqual(after['pendingTasks'],[general]);self.assertEqual(after['week'],panel['week'])
        tasks=management_state(self.config)['tasks'];self.assertEqual(len(tasks),2)
        self.assertEqual(next(t for t in tasks if t['title']=='Práctica revisada')['status'],'realizada')
        self.assertEqual(preview_exchange(self.app,book)['changes'],[])

    def test_http_roundtrip_requires_origin_and_rejects_malformed_references(self):
        server=create_server(self.config,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}';before=self.notes()
        def post(route,payload,origin):
            return urlopen(Request(base+'/api/notebook/web/'+route,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Origin':origin}))
        try:
            for route in ('prepare','preview','apply','download'):
                with self.assertRaises(HTTPError) as error:post(route,{},'https://example.org')
                self.assertEqual(error.exception.code,403)
            with post('prepare',{},base) as response:book=json.load(response)['book']
            for invalid in ([],{},None):
                malformed=copy.deepcopy(book)
                malformed['tasks'][0]['subjectId']=invalid
                with self.assertRaises(HTTPError) as error:post('preview',{'book':malformed},base)
                self.assertEqual(error.exception.code,400)
            book['subjects'][0]['topics'][0]['content']='Cambio ficticio mediante HTTP'
            with post('preview',{'book':book},base) as response:review=json.load(response)
            self.assertEqual(self.notes(),before)
            with post('apply',{'token':review['token'],'choices':self.choose(review)},base) as response:self.assertTrue(json.load(response)['saved'])
            self.assertEqual(self.note.read_text(encoding='utf-8'),'Cambio ficticio mediante HTTP')
        finally:server.shutdown();server.server_close();thread.join()

    def test_download_checks_current_sources_again_instead_of_serving_old_preview(self):
        exchange_id=self.book['transfer']['exchangeId']
        self.assertEqual(download_exchange(self.app,exchange_id)['book'],self.book)
        self.note.write_text('Una edición posterior a revisar el traslado',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'cambió desde la revisión'):download_exchange(self.app,exchange_id)
        current=prepare_exchange(self.app)['book'];self.assertEqual(download_exchange(self.app,current['transfer']['exchangeId'])['book'],current)
