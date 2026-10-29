from pathlib import Path
import tempfile
import unittest
from horario import load_schedule

class ScheduleTests(unittest.TestCase):
    def test_manual_edit_replaces_classes_and_invalid_rows_are_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            degree = Path(folder)
            note = degree / '00 Dashboard/Horario de clase.md'
            note.parent.mkdir()
            note.write_text('Grupo: Demo\n| Día | Inicio | Fin | Asignatura | Tipo | Aula |\n|---|---|---|---|---|---|\n| Lunes | 16:00 | 18:00 | Materia ficticia | Teoría | 01 |\n', encoding='utf-8')
            first = load_schedule(degree)
            self.assertEqual(len(first['classes']), 1)
            note.write_text('| Martes | 18:00 | 20:00 | Otra materia ficticia | Prácticas | 02 |\n| Lunes | 25:00 | 26:00 | Inválida | Teoría | 01 |\n', encoding='utf-8')
            current = load_schedule(degree)
            self.assertNotEqual(first['sha'], current['sha'])
            self.assertEqual([c['day'] for c in current['classes']], ['Martes'])
            self.assertTrue(current['issues'])

    def test_no_note_has_no_invented_classes(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_schedule(Path(folder))['classes'], [])
