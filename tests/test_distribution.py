"""Instalación nueva, reutilización de notas y reanudación con datos ficticios."""
from pathlib import Path
import json
import tempfile
import unittest

from perfiles import create_profile, add_subject
from configuracion import load_config
from puente_memoria import Application


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mi-grado-perfil-')
        self.root = Path(self.tmp.name).resolve()
        self.path = self.root / 'Perfil' / 'config.json'
        self.notes = self.root / 'Apuntes propios'

    def tearDown(self): self.tmp.cleanup()

    def test_new_student_can_save_restart_and_resume_without_private_paths(self):
        config = create_profile(self.path, self.notes, ['Programación de ejemplo', 'Datos de ejemplo'], center='FP')
        app = Application(config)
        subject = app.panel['subjects'][0]
        self.assertEqual(subject['stage'], 0)
        self.assertIsNone(app.panel['checked'])
        capture = {'id': 'intento-perfil-001', 'subject': subject['id'], 'title': 'Primer intento ficticio',
                   'details': 'Probé una condición; recibí una pista. Siguiente paso: intentarlo solo.',
                   'evidence': 'Intentado con ayuda', 'source': 'Prueba ficticia'}
        saved = app.save(capture)
        self.assertTrue(saved['saved'] and saved['journalLinked'])
        restarted = Application(load_config(self.path))
        state = restarted.state()
        self.assertEqual(state['captures'][0]['title'], capture['title'])
        self.assertEqual(state['panel']['subjects'][0]['stage'], 0)
        self.assertTrue(all(Path(n['path']).is_relative_to(self.root) for n in state['notes']))
        self.assertEqual(len(restarted.store().read_all()[0]), 1)
        self.assertTrue(restarted.save(capture)['saved'])
        self.assertEqual(len(restarted.store().read_all()[0]), 1)

    def test_existing_fiche_is_preserved_and_only_selected_as_subject(self):
        self.notes.mkdir()
        note = self.notes / 'Mi ficha.md'
        content = '# Mi ficha\n\nTexto editado a mano, sin evaluación todavía.\n'
        note.write_text(content, encoding='utf-8')
        (self.notes / 'Otra nota.md').write_text('Una nota que no se seleccionó.', encoding='utf-8')
        config = create_profile(self.path, self.notes, [], existing_notes=[note])
        app = Application(config)
        self.assertEqual(note.read_text(encoding='utf-8'), content)
        self.assertEqual(len(app.panel['subjects']), 1)
        canonical = app.state()['canonical']
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]['text'], content)
        with self.assertRaises(ValueError): create_profile(self.path, self.notes, ['Otra'])
        self.assertEqual(note.read_text(encoding='utf-8'), content)

    def test_invalid_configuration_does_not_create_a_profile(self):
        foreign = self.root / 'fuera.md'; foreign.write_text('# Fuera', encoding='utf-8')
        for names, selected, campus in [([], [foreign], ''), (['Datos', 'Datos'], [], ''),
                                        (['Datos'], [], 'javascript:alert(1)')]:
            with self.assertRaises(ValueError):
                create_profile(self.path, self.notes, names, existing_notes=selected, campus=campus)
            self.assertFalse(self.path.exists())

    def test_add_subject_preserves_existing_notes_and_previous_capture(self):
        config = create_profile(self.path, self.notes, ['Datos'])
        app = Application(config)
        saved = app.save({'id': 'captura-primer-perfil', 'subject': app.panel['subjects'][0]['id'],
                          'title': 'Intento', 'details': 'Dato ficticio con ayuda.'})
        note = self.notes / 'Otra ficha.md'; note.write_text('# Otra ficha\n\nMi edición.\n', encoding='utf-8')
        added = add_subject(config, 'Otra materia', note)
        app.state()
        self.assertEqual(len(app.panel['subjects']), 2)
        self.assertEqual(note.read_text(encoding='utf-8'), '# Otra ficha\n\nMi edición.\n')
        self.assertEqual(app.panel['subjects'][1]['id'], added['id'])
        self.assertTrue(Path(saved['path']).exists())
        with self.assertRaises(ValueError): add_subject(config, 'Otra materia', note)


if __name__ == '__main__': unittest.main()
