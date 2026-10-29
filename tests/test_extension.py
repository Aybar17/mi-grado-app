from pathlib import Path
import json, os, tempfile, unittest
from extension_panel import goal_data, load_extension
import test_smoke as smoke
from configuracion import subject_source
from actualizar_panel import update

class ExtensionTests(unittest.TestCase):
    def test_manual_goals_are_the_source_and_duplicates_are_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            hub=Path(folder);note=hub/'Objetivos.md'
            note.write_text('## [estudio] Practicar\nEstado: Activo\nSiguiente paso: Ejercicio oficial\n- [ ] Mi intento\n',encoding='utf-8')
            first=goal_data(note,hub)
            note.write_text('## [estudio] Mi corrección manual\nEstado: Pausado\nSiguiente paso: Consultar enunciado\n- [x] Mi intento declarado\n## [estudio] Duplicado\n',encoding='utf-8')
            current=goal_data(note,hub)
            self.assertNotEqual(first['sha'],current['sha'])
            self.assertEqual(current['items'][0]['title'],'Mi corrección manual')
            self.assertEqual(current['items'][0]['status'],'Pausado')
            self.assertEqual(len(current['items']),1)
            self.assertTrue(current['issues'])
            self.assertTrue(current['items'][0]['milestones'][0]['done'])
    def test_invalid_team_member_does_not_hide_valid_results(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'equipo.local.json').write_text(json.dumps({'roles':[None,{'id':'ok','domain':'Diseño','group':'head'}]}),encoding='utf-8')
            team=load_extension(p,p)['team']
            self.assertEqual([r['id'] for r in team['roles']],['ok'])
            self.assertTrue(team['issues'])

class ReviewedRegression(unittest.TestCase):
    setUp=smoke.PortableSmoke.setUp
    tearDown=smoke.PortableSmoke.tearDown
    def test_unscheduled_tasks_survive_an_empty_week_and_a_later_review(self):
        checked=self.app.panel['checked']
        levels=[(s['id'], s.get('stage')) for s in self.app.panel['subjects']]
        task={'id':'demo-pendiente','subject':'logica','title':'Intento ficticio sin fecha','minutes':60}
        update(self.config,{'plan':{'week':[{'date':'2030-01-01','slots':[]}],'pendingTasks':[task]}})
        update(self.config,{'plan':{'priorityTitle':'Otra revisión ficticia'}})
        current=self.app.state()['panel']
        self.assertEqual(current['pendingTasks'],[task])
        self.assertEqual(current['checked'],checked)
        self.assertEqual([(s['id'],s.get('stage')) for s in current['subjects']],levels)
    def test_invalid_unscheduled_task_does_not_change_saved_data(self):
        before=self.config['panel_file'].read_bytes()
        task={'id':'demo-pendiente','subject':'logica','title':'Intento ficticio'}
        for tasks in ([{**task,'subject':'desconocida'}],[task,task],[{**task,'minutes':-10}],[None]):
            with self.assertRaises(ValueError):update(self.config,{'plan':{'pendingTasks':tasks}})
            self.assertEqual(self.config['panel_file'].read_bytes(),before)
    def test_bad_plan_never_advances_the_saved_revision(self):
        before=self.config['panel_file'].read_bytes()
        for value in (None,'texto',{},[{'date':'2030-01-01','slots':None}]):
            with self.assertRaises(ValueError):update(self.config,{'plan':{'week':value}})
            self.assertEqual(self.config['panel_file'].read_bytes(),before)
    def test_canonical_restore_with_same_size_mtime_marks_summary_stale(self):
        subject=self.app.panel['subjects'][0];source=subject_source(self.config,subject)
        import hashlib
        update(self.config,{'subjects':[{'id':subject['id'],'sourceSha':hashlib.sha256(source.read_bytes()).hexdigest(),'patch':{'checkpoint':'Control ficticio'}}]})
        self.assertFalse(self.app.state()['panel']['subjects'][0]['summaryNeedsReview'])
        stamp=source.stat();old=source.read_bytes();new=old.replace(b'---',b'___',1)
        self.assertEqual(len(old),len(new));source.write_bytes(new);os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        state=self.app.state()
        self.assertTrue(state['panel']['subjects'][0]['summaryNeedsReview'])
        self.assertEqual(state['canonical'][0]['text'].encode('utf-8'),new)
