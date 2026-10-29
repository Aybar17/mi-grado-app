"""Referencias portables sin lectura de PDFs, revisión y conservación de la sesión."""
from pathlib import Path
from unittest.mock import patch
import copy
import hashlib
import json
import tempfile
import unittest
import io
import zipfile

from perfiles import create_profile
from configuracion import load_config,read_panel
from puente_memoria import Application
from cuaderno_web import export_notebook
from intercambio_web import prepare_exchange,preview_exchange,apply_exchange
from gestion import management_state,save_reference
from referencias import collect_references,local_materials
from copias import export_backup,preview_backup,restore_backup,unpack


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='material-ficticio-');self.root=Path(self.tmp.name).resolve()
        self.config=create_profile(self.root/'Perfil/config.json',self.root/'Apuntes',['Datos'])
        self.pdf=self.root/'Material privado'/'Relacion.pdf';self.pdf.parent.mkdir();self.pdf.write_bytes(b'%PDF FICTICIO NO LEER')
        panel=read_panel(self.config);self.sid=panel['subjects'][0]['id']
        panel['subjects'][0]['materials']=[{'title':'Relación elegida','path':str(self.pdf),'url':'https://campus.example.org/material','detail':'Página 2, ejercicio 1'}]
        panel['subjects'][0]['sources']=[{'title':'Calendario del centro','url':'https://campus.example.org/calendario'}]
        self.config['panel_file'].write_text(json.dumps(panel,ensure_ascii=False),encoding='utf-8')
        self.app=Application(self.config)
    def tearDown(self):self.tmp.cleanup()
    def choices(self,review,conflict='local'):return {r['id']:r['suggested'] or conflict for r in review['changes']}

    def test_legacy_label_ending_in_extension_is_description_not_file_path(self):
        label='DATOS DEL EJEMPLO: muestra-a.csv, muestra-b.csv'
        panel=read_panel(self.config)
        panel['subjects'][0]['materials']=[label,'Materiales/muestra.csv']
        panel['subjects'][0]['sources']=[]
        self.config['panel_file'].write_text(json.dumps(panel,ensure_ascii=False),encoding='utf-8')
        before=self.config['panel_file'].read_bytes()
        refs=management_state(self.config)['references'][self.sid]
        self.assertEqual(refs[0]['kind'],'description')
        self.assertEqual(refs[0]['title'],label)
        self.assertEqual(refs[0]['location'],'')
        self.assertEqual(refs[1]['kind'],'local-file')
        self.assertEqual(refs[1]['location'],'Materiales/muestra.csv')
        book=prepare_exchange(self.app)['book']
        self.assertEqual(book['subjects'][0]['references'],refs)
        self.assertEqual(self.config['panel_file'].read_bytes(),before)

    def test_selected_references_export_without_private_paths_or_reading_pdf(self):
        original=Path.read_bytes
        def guarded(path):
            if path.resolve()==self.pdf:raise AssertionError('No se autoriza leer el PDF para trasladar su referencia.')
            return original(path)
        with patch.object(Path,'read_bytes',guarded):
            book=export_notebook(self.app)['book']
            materials=local_materials(self.config,read_panel(self.config)['subjects'][0])[0]
        refs=book['subjects'][0]['references'];self.assertEqual(len(refs),2)
        self.assertEqual(refs[0]['location'],'Relacion.pdf');self.assertEqual(refs[0]['link'],'https://campus.example.org/material')
        self.assertNotIn(str(self.pdf),json.dumps(book));self.assertTrue(any(m.get('referenceId')==refs[0]['id'] for m in materials))

    def test_each_reference_is_reviewed_and_conflicting_local_title_is_kept(self):
        book=prepare_exchange(self.app)['book'];ref=book['subjects'][0]['references'][0]
        ref['detail']='Página 3, ejercicio 2'
        panel=read_panel(self.config);panel['subjects'][0]['materials'][0]['title']='Nombre editado en local'
        self.config['panel_file'].write_text(json.dumps(panel),encoding='utf-8')
        review=preview_exchange(self.app,book);rows=[r for r in review['changes'] if r['kind']=='reference']
        self.assertEqual(len(rows),1);self.assertTrue(rows[0]['conflict'])
        apply_exchange(self.app,review['token'],self.choices(review))
        self.assertEqual(export_notebook(self.app)['book']['subjects'][0]['references'][0]['title'],'Nombre editado en local')
        again=preview_exchange(self.app,book);apply_exchange(self.app,again['token'],self.choices(again,'web'))
        self.assertEqual(preview_exchange(self.app,book)['changes'],[])
        material=local_materials(self.config,read_panel(self.config)['subjects'][0])[0][0]
        self.assertEqual(material['detail'],'Página 3, ejercicio 2');self.assertEqual(material['path'],str(self.pdf))

    def test_archiving_reference_retains_identity_and_history(self):
        book=prepare_exchange(self.app)['book'];removed=book['subjects'][0]['references'].pop(0)
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choices(review))
        copied=export_notebook(self.app)['book'];ref=next(r for r in copied['subjects'][0]['references'] if r['id']==removed['id'])
        self.assertTrue(ref['archived']);self.assertTrue(self.pdf.is_file());self.assertEqual(preview_exchange(self.app,book)['changes'],[])

    def test_restore_preserves_reference_ids_but_missing_attachment_does_not_link_original(self):
        book=prepare_exchange(self.app)['book'];ref=book['subjects'][0]['references'][0]
        book['sessions']=[{'id':'session-material01','subjectId':book['subjects'][0]['id'],'createdAt':'2026-10-16T12:00:00Z','source':'user','topicIds':[],
                          'referenceIds':[ref['id']],'referenceSnapshot':[copy.deepcopy(ref)],'attempt':'Intento ficticio','help':'Una pista','result':'Caso guiado','nextStep':'Repetir'}]
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choices(review))
        data=export_backup(self.app);info=preview_backup(data);restored=restore_backup(data,info['sha'],self.root/'Recuperado')
        app=Application(load_config(restored['config']));copied=export_notebook(app)['book']
        self.assertEqual(copied['subjects'][0]['references'][0]['id'],ref['id'])
        self.assertEqual(copied['sessions'][0]['referenceIds'],[ref['id']]);self.assertEqual(copied['sessions'][0]['referenceSnapshot'],[ref])
        material=app.state()['panel']['subjects'][0]['materials'][0]
        self.assertNotEqual(material['path'],str(self.pdf));self.assertIn('no localizado',material['materialStatus'])
        self.assertTrue(self.pdf.is_file());self.assertIn('Página 2',app.state()['captures'][0]['details'])

    def test_local_editor_uses_version_and_rejects_absolute_public_location(self):
        current=management_state(self.config)
        ref={'id':'reference-editor01','title':'Práctica','kind':'local-file','location':'Materiales/practica.pdf','detail':'Ejercicio 2','archived':False}
        saved=save_reference(self.config,{'panelSha':current['panelSha'],'subject':self.sid,'reference':ref})
        self.assertTrue(any(r['id']==ref['id'] for r in saved['references'][self.sid]))
        with self.assertRaisesRegex(ValueError,'cambiaron'):save_reference(self.config,{'panelSha':current['panelSha'],'subject':self.sid,'reference':ref})
        before=self.config['panel_file'].read_bytes()
        with self.assertRaises(ValueError):save_reference(self.config,{'panelSha':saved['panelSha'],'subject':self.sid,'reference':{**ref,'location':'C:/privado.pdf'}})
        self.assertEqual(before,self.config['panel_file'].read_bytes())

    def test_forged_historical_material_is_rejected_before_restoring(self):
        book=prepare_exchange(self.app)['book'];subject=book['subjects'][0];ref=subject['references'][0]
        book['sessions']=[{'id':'session-backuprefs01','subjectId':subject['id'],'createdAt':'2026-10-16T12:00:00Z',
            'source':'user','topicIds':[],'referenceIds':[ref['id']],'referenceSnapshot':[copy.deepcopy(ref)],
            'attempt':'Intento ficticio','help':'Una pista','result':'Guiado','nextStep':'Repetir'}]
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choices(review))
        original,_,_=unpack(export_backup(self.app));name=next(n for n in original if n.startswith('web-results/'))
        for value in ([],[{**ref,'location':'../../privado.pdf'}],[ref,ref],[{**ref,'title':'Título manipulado'}]):
            with self.subTest(snapshot=value):
                files=dict(original);record=json.loads(files[name]);record['session']['referenceSnapshot']=value
                files[name]=json.dumps(record).encode()
                files['manifest.json']=json.dumps({'version':1,'files':{n:hashlib.sha256(body).hexdigest() for n,body in files.items() if n!='manifest.json'}}).encode()
                output=io.BytesIO()
                with zipfile.ZipFile(output,'w') as archive:
                    for file,body in files.items():archive.writestr(file,body)
                data=output.getvalue();destination=self.root/'No crear'
                with self.assertRaises(ValueError):restore_backup(data,hashlib.sha256(data).hexdigest(),destination)
                self.assertFalse(destination.exists())

    def test_many_selected_references_are_saved_without_cutting_the_four_fields(self):
        book=prepare_exchange(self.app)['book'];subject=book['subjects'][0]
        subject['references']+=[{'id':'reference-large'+str(i).zfill(3),'title':'Material '+str(i),'kind':'web',
             'location':'https://campus.example.org/'+str(i)+'a'*1900,'link':'https://campus.example.org/extra/'+str(i)+'b'*1900,
             'detail':'d'*2000,'archived':False} for i in range(198)]
        session={'id':'session-large-refs01','subjectId':subject['id'],'createdAt':'2026-10-16T12:00:00Z','source':'user','topicIds':[],
                 'referenceIds':[r['id'] for r in subject['references']],'referenceSnapshot':copy.deepcopy(subject['references']),
                 'attempt':'a'*12000,'help':'h'*12000,'result':'r'*12000,'nextStep':'n'*12000}
        book['sessions']=[session]
        review=preview_exchange(self.app,book);apply_exchange(self.app,review['token'],self.choices(review))
        capture=self.app.state()['captures'][0]
        for key in ('attempt','help','result','nextStep'):self.assertIn(session[key],capture['details'])
        copied=export_notebook(self.app)['book']['sessions'][0]
        self.assertEqual(copied['referenceSnapshot'],session['referenceSnapshot'])

    def test_merged_reference_limit_is_checked_before_any_file_is_written(self):
        book=prepare_exchange(self.app)['book'];subject=book['subjects'][0]
        subject['references']=[{'id':'reference-limit'+str(i).zfill(3),'title':'Nuevo '+str(i),'kind':'description','location':'','detail':'Enunciado pendiente','archived':False} for i in range(200)]
        subject['topics'][0]['content']='No escribir este cambio si el material no cabe.'
        review=preview_exchange(self.app,book)
        before={p:p.read_bytes() for p in self.config['vaults']['degree'].rglob('*.md')};panel=self.config['panel_file'].read_bytes()
        with self.assertRaisesRegex(ValueError,'200 referencias'):apply_exchange(self.app,review['token'],self.choices(review))
        self.assertEqual(self.config['panel_file'].read_bytes(),panel)
        self.assertEqual({p:p.read_bytes() for p in before},before)

if __name__=='__main__':unittest.main()
