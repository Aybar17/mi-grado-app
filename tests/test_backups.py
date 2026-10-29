"""Copia privada, restauración independiente y rechazo de archivos alterados."""
from pathlib import Path
import hashlib
import io
import json
import tempfile
import unittest
import zipfile

from perfiles import create_profile
from puente_memoria import Application
from copias import export_backup, preview_backup, restore_backup, unpack
from gestion import management_state, save_task


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='copia-ficticia-')
        # Windows runners can redirect TEMP through a junction; compare canonical paths.
        self.root = Path(self.tmp.name).resolve()
        self.config = create_profile(self.root/'Perfil/config.json', self.root/'Notas', ['Datos'])
        self.app = Application(self.config)

    def tearDown(self): self.tmp.cleanup()

    def test_restore_preserves_manual_capture_and_journal_verification_without_touching_source(self):
        capture = self.app.save({'id':'copia-captura-001','subject':self.app.panel['subjects'][0]['id'],
                                 'title':'Título inicial','details':'Un intento ficticio con ayuda.'})
        note = Path(capture['path'])
        note.write_text(note.read_text(encoding='utf-8').replace('# Título inicial','# Título editado a mano'),encoding='utf-8')
        unrelated = self.config['vaults']['degree']/'Privado.md';unrelated.write_text('NO INCLUIR',encoding='utf-8')
        save_task(self.config, {'planSha':None,'task':{'id':'','subject':self.app.panel['subjects'][0]['id'],
                  'title':'Repetir intento','date':'','minutes':45,'detail':'Sin pistas.','status':'pendiente'}})
        before = {path:path.read_bytes() for path in (note,Path(capture['diaryPath']),self.config['panel_file'])}
        data = export_backup(self.app)
        files,_,_=unpack(data); self.assertNotIn('degree/Privado.md',files)
        info = preview_backup(data); self.assertEqual(info['subjects'],['Datos'])
        restored = restore_backup(data,info['sha'],self.root/'Restaurado')
        from configuracion import load_config
        app = Application(load_config(restored['config']))
        state = app.state()
        self.assertTrue(state['captures'][0]['saved'] and state['captures'][0]['journalLinked'])
        self.assertEqual(state['captures'][0]['title'],'Título editado a mano')
        self.assertEqual(len(state['panel']['pendingTasks']),1)
        self.assertTrue(all(Path(c['path']).is_relative_to(self.root/'Restaurado') for c in state['captures']))
        self.assertTrue(app.save(state['captures'][0]['retryPayload'])['saved'])
        for path,content in before.items(): self.assertEqual(path.read_bytes(),content)
        with self.assertRaises(ValueError): restore_backup(data,info['sha'],self.root/'Restaurado')

    def test_tampered_archive_and_traversal_are_rejected_before_creating_destination(self):
        data = export_backup(self.app)
        original = zipfile.ZipFile(io.BytesIO(data))
        for name,body in [('panel.json',b'{}'),('../outside.md',b'bad')]:
            output = io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive:
                for item in original.infolist(): archive.writestr(item.filename,body if item.filename==name else original.read(item))
                if name.startswith('../'): archive.writestr(name,body)
            bad = output.getvalue()
            with self.assertRaises(ValueError): restore_backup(bad,hashlib.sha256(bad).hexdigest(),self.root/'Invalid')
            self.assertFalse((self.root/'Invalid').exists())
        with self.assertRaises(ValueError): restore_backup(data,'incorrect',self.root/'Invalid')


if __name__ == '__main__': unittest.main()
