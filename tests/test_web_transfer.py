"""El traslado no cambia las fuentes y su resultado se abre en el motor web real."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from perfiles import create_profile
from puente_memoria import Application
from cuaderno_web import export_notebook, text_parts
from gestion import management_state, save_task, save_schedule


class WebTransferTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='traslado-ficticio-')
        self.root=Path(self.tmp.name)
        self.config=create_profile(self.root/'Perfil/config.json',self.root/'Apuntes',['Datos'])
        self.app=Application(self.config)

    def tearDown(self): self.tmp.cleanup()

    def test_legacy_capture_dates_use_confirmed_save_without_inventing_creation_time(self):
        subject=management_state(self.config)['subjects'][0]
        for i,original in enumerate(('2026-10-07','7/10/2026, 16:18:34','2026-10-07T16:18:34')):
            self.app.save({'id':'legacy-date-demo-'+str(i),'subject':subject['id'],'title':'Registro ficticio','details':'Texto original intacto.'})
        captures,issues,journal=self.app.store().read_all()
        for c,original in zip(captures,('2026-10-07','7/10/2026, 16:18:34','2026-10-07T16:18:34')):
            c['created']=original;c['savedAt']='2026-10-08T10:00:00+02:00'
        before={p:p.read_bytes() for v in self.config['vaults'].values() for p in v.rglob('*.md')}
        with patch.object(type(self.app.store()),'read_all',return_value=(captures,issues,journal)):
            result=export_notebook(self.app)
        self.assertEqual(len(result['book']['sessions']),3)
        for session in result['book']['sessions']:
            self.assertEqual(session['createdAt'],'2026-10-08T10:00:00+02:00')
            self.assertIn('Texto original intacto.',session['attempt'])
            self.assertIn('No se ha deducido una hora de creación.',session['attempt'])
        all_details='\n'.join(s['attempt'] for s in result['book']['sessions'])
        for original in ('2026-10-07','7/10/2026, 16:18:34','2026-10-07T16:18:34'):
            self.assertIn(original,all_details)
        self.assertTrue(any('3 capturas antiguas' in w for w in result['warnings']))
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        captures[0]['savedAt']='2026-10-08'
        with patch.object(type(self.app.store()),'read_all',return_value=(captures,issues,journal)):
            with self.assertRaisesRegex(ValueError,'guardado confirmado'):export_notebook(self.app)

    def test_non_bmp_notes_split_at_browser_limit_without_losing_characters(self):
        text='a'+'🧪'*50001+'\nTexto final'
        parts=text_parts(text)
        self.assertEqual(''.join(parts),text)
        self.assertEqual(len(parts),2)
        self.assertTrue(all(len(p.encode('utf-16-le'))//2<=100000 for p in parts))

    def test_selected_sources_preserved_and_validated_by_web(self):
        s=management_state(self.config)['subjects'][0]
        note=self.config['vaults']['degree']/s['note']
        literal='# Datos\n\nMi texto exacto.\n'+('a'*100020)+'\n'
        note.write_text(literal,encoding='utf-8')
        private=self.config['vaults']['hub']/'otra-nota.md';private.write_text('NO EXPORTAR OTRAS NOTAS',encoding='utf-8')
        old=management_state(self.config)
        save_task(self.config,{'planSha':old['planSha'],'task':{'id':'','subject':s['id'],'title':'Primer intento','date':'','minutes':75,'detail':'Con el material elegido','status':'pendiente'}})
        save_schedule(self.config,{'scheduleSha':old['scheduleSha'],'group':'G1','period':'Semestre','classes':[{'day':'Lunes','start':'10:00','end':'11:00','subject':'Datos','kind':'Prácticas','room':'A1'}]})
        self.app.save({'id':'traslado-captura-001','subject':s['id'],'title':'Prueba ficticia','details':'Intenté resolverlo con una pista.'})
        before={p:p.read_bytes() for v in self.config['vaults'].values() for p in v.rglob('*.md')}
        result=export_notebook(self.app);book=result['book']
        self.assertEqual({p:p.read_bytes() for p in before},before)
        self.assertEqual(''.join(t['content'] for t in book['subjects'][0]['topics']),literal)
        self.assertNotIn('NO EXPORTAR',json.dumps(book))
        self.assertNotIn(str(self.config['path']),json.dumps(book))
        self.assertEqual(book['tasks'][0]['minutes'],75)
        self.assertEqual(book['schedule'][0]['kind'],'Prácticas')
        self.assertEqual(len(book['sessions']),1)
        self.assertIn('No desglosada',book['sessions'][0]['help'])
        self.assertEqual(book['connections'],{'obsidian':None,'ai':None})
        self.assertEqual(book['id'],export_notebook(self.app)['book']['id'])
        if shutil.which('node'):
            subprocess.run(['node','-e',"const C=require('./web/app/core.js');let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const b=C.parse(s);if(b.subjects.length!==1||b.tasks[0].minutes!==75)process.exit(2)});"],input=json.dumps(book),text=True,check=True,cwd=Path(__file__).resolve().parents[1],capture_output=True)

    def test_missing_note_and_broken_plan_fail_without_partial_export(self):
        s=management_state(self.config)['subjects'][0]
        note=self.config['vaults']['degree']/s['note'];content=note.read_bytes();note.unlink()
        with self.assertRaisesRegex(ValueError,'Falta la ficha'):export_notebook(self.app)
        note.write_bytes(content)
        plan=self.config['vaults']['degree']/'00 Dashboard/Plan de Mi grado.md'
        plan.parent.mkdir(parents=True,exist_ok=True)
        plan.write_text('<!-- mi-grado:plan -->\ninvalid\n<!-- /mi-grado:plan -->',encoding='utf-8')
        # Invalid dates/unknown subjects are already rejected by management_state.
        with self.assertRaises(ValueError):export_notebook(self.app)

    def test_previous_week_and_undated_tasks_keep_their_details(self):
        panel=json.loads(self.config['panel_file'].read_text(encoding='utf-8'))
        sid=panel['subjects'][0]['id']
        panel['week']=[{'date':'2026-10-16','slots':[{'subject':sid,'title':'Práctica anterior','duration':'90 min','outcome':'Un intento sin pistas'}]}]
        panel['pendingTasks']=[{'subject':sid,'title':'Pendiente sin día','detail':'Conservar este detalle'}]
        panel['deadlines']=[{'title':'Fecha sin asignatura','date':'2026-10-17'}]
        self.config['panel_file'].write_text(json.dumps(panel),encoding='utf-8')
        result=export_notebook(self.app)
        self.assertEqual(len(result['book']['tasks']),2)
        planned=next(t for t in result['book']['tasks'] if t['day'])
        self.assertEqual(planned['minutes'],90)
        self.assertIn('Un intento sin pistas',planned['detail'])
        self.assertTrue(result['warnings'])
