"""Cambios desde el panel, conservación de fuentes y conflictos de edición."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import tempfile
import threading
import unittest

from perfiles import create_profile
from puente_memoria import Application, create_server
from gestion import management_state, save_subject, save_task, save_schedule, PLAN, SCHEDULE


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cuaderno-ficticio-')
        self.root = Path(self.tmp.name)
        self.config = create_profile(self.root/'Perfil/config.json', self.root/'Apuntes', ['Datos', 'Lógica'])
        self.app = Application(self.config)

    def tearDown(self): self.tmp.cleanup()

    def edit(self, subject, **changes):
        return {'action': 'edit', 'panelSha': management_state(self.config)['panelSha'],
                'subject': {'id': subject['id'], 'name': subject['name'], 'checkpoint': 'Mi intento con ayuda',
                            'nextPractice': 'Repetir sin pista', 'archived': False, **changes}}

    def test_edit_archive_and_restore_subject_preserves_notes_and_saved_capture(self):
        subject = self.app.panel['subjects'][0]
        path = self.config['vaults']['degree']/subject['note']
        before = path.read_bytes()
        capture = self.app.save({'id':'gestion-intento-001', 'subject':subject['id'], 'title':'Intento ficticio', 'details':'Con una pista.'})
        stale = self.edit(subject)
        save_subject(self.config, self.edit(subject, name='Datos I', archived=True))
        with self.assertRaisesRegex(ValueError, 'cambiaron'): save_subject(self.config, stale)
        self.assertEqual(path.read_bytes(), before)
        state = self.app.state()
        self.assertEqual(len(state['panel']['subjects']), 1)
        self.assertTrue(state['captures'][0]['saved'])
        save_subject(self.config, self.edit({'id':subject['id'], 'name':'Datos I'}, archived=False))
        self.assertEqual(len(self.app.state()['panel']['subjects']), 2)
        self.assertTrue(Path(capture['path']).is_file())

    def test_new_subject_can_save_and_resume_without_restart(self):
        result = save_subject(self.config, {'action':'add','panelSha':management_state(self.config)['panelSha'],
                                          'subject':{'name':'Programación','note':''}})
        ident = result['subjects'][-1]['id']
        self.assertTrue(self.app.save({'id':'asignatura-nueva-001','subject':ident,'title':'Primer intento','details':'Ejemplo ficticio.'})['saved'])
        with self.assertRaises(ValueError):
            save_subject(self.config, {'action':'add','panelSha':result['panelSha'], 'subject':{'name':'Fuera','note':'../fuera.md'}})

    def test_plan_preserves_manual_text_and_overdue_tasks_survive_restart(self):
        path = self.config['vaults']['degree']/PLAN
        path.parent.mkdir(parents=True); path.write_text('# Mi plan\n\nUna decisión escrita a mano.\n',encoding='utf-8')
        old = management_state(self.config)
        task = {'id':'','subject':self.app.panel['subjects'][0]['id'],'title':'Resolver ejercicio',
                'date':'2020-01-01','minutes':60,'detail':'Sin solución visible.','status':'pendiente'}
        saved = save_task(self.config, {'planSha':old['planSha'],'task':task})
        self.assertIn('Una decisión escrita a mano.', path.read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'cambió'): save_task(self.config, {'planSha':old['planSha'],'task':task})
        restarted = Application(self.config)
        self.assertEqual(restarted.panel['pendingTasks'][0]['date'], '2020-01-01')
        self.assertEqual(restarted.panel['priorityTitle'], 'Resolver ejercicio')
        task = {**saved['tasks'][0], 'status':'realizada'}
        save_task(self.config, {'planSha':saved['planSha'],'task':task})
        self.assertEqual(restarted.state()['panel']['pendingTasks'], [])
        self.assertEqual(restarted.panel['subjects'][0]['stage'], 0)

    def test_schedule_preserves_text_and_detects_external_edits(self):
        path = self.config['vaults']['degree']/SCHEDULE
        path.parent.mkdir(parents=True); path.write_text('# Horario\n\nFuente: https://example.org/horario\nContraste: 2026-01-01\n\nMi anotación manual.\n',encoding='utf-8')
        old = management_state(self.config)
        raw = {'scheduleSha':old['scheduleSha'],'group':'G1','period':'Semestre',
               'classes':[{'day':'Lunes','start':'09:00','end':'10:00','subject':'Datos','kind':'Teoría','room':'A1'}]}
        result = save_schedule(self.config, raw)
        body = path.read_text(encoding='utf-8')
        self.assertIn('Mi anotación manual.',body); self.assertIn('Fuente: https://example.org/horario',body)
        self.assertNotIn('Contraste:',body)
        self.assertEqual(len(result['schedule']['classes']),1)
        with self.assertRaisesRegex(ValueError,'cambió'): save_schedule(self.config,raw)
        invalid = {**raw,'scheduleSha':result['scheduleSha'],'classes':[{**raw['classes'][0],'end':'08:00'}]}
        with self.assertRaises(ValueError): save_schedule(self.config,invalid)
        self.assertEqual(path.read_text(encoding='utf-8'),body)

    def test_mutations_require_origin_and_preserve_last_active_subject(self):
        first, second = self.app.panel['subjects']
        save_subject(self.config, self.edit(first, archived=True))
        with self.assertRaisesRegex(ValueError,'al menos una'): save_subject(self.config,self.edit(second,archived=True))
        server = create_server(self.config,0)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for route in ('subject','task','schedule','reference'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/manage/'+route,data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.org'}))
                self.assertEqual(error.exception.code,403)
            with urlopen(base+'/api/manage') as response: self.assertEqual(len(json.load(response)['subjects']),2)
        finally: server.shutdown();server.server_close();thread.join()


if __name__ == '__main__': unittest.main()
