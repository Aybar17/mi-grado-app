"""Pruebas con carpetas temporales; nunca leen una bóveda personal."""
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import hashlib
import json
import tempfile
import threading
import unittest

from configuracion import ROOT, load_config, subject_source
from generar_panel import build
from puente_memoria import Application, create_server
from actualizar_panel import update
import memoria
import persistencia_capturas as storage


class PortableSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mi-grado-test-')
        self.root = Path(self.tmp.name)
        raw = {'version': 1, 'timezone': 'Europe/Madrid',
               'vaults': {'degree': 'Grado demo', 'hub': 'Centro demo', 'projects': 'Proyectos demo'},
               'runtime': 'technical', 'panel_file': 'panel.json'}
        self.config_path = self.root / 'config.json'
        self.config_path.write_text(json.dumps(raw), encoding='utf-8')
        self.config = load_config(self.config_path)
        self.config['demo'] = True
        self.app = Application(self.config)
        self.capture = {'id': 'captura-demo-001', 'subject': 'logica', 'kind': 'Intento ficticio',
                        'title': 'Comprobación sintética', 'details': 'Probé una condición con ayuda.',
                        'date': '', 'time': '', 'timezone': 'Europe/Madrid',
                        'evidence': 'Intentado con ayuda', 'source': 'Demo sintética', 'created': ''}

    def tearDown(self):
        self.tmp.cleanup()

    def test_demo_generation_and_no_external_vaults(self):
        result = build(self.config)
        self.assertEqual(len(result['subjects']), 3)
        self.assertTrue(result['demo'])
        self.assertEqual(result['checked'], None)
        self.assertTrue(all(Path(note['path']).resolve().is_relative_to(self.root.resolve()) for note in result['notes']))
        html = (self.config['runtime'] / 'panel.html').read_text(encoding='utf-8')
        self.assertNotIn('__DATA__', html)
        self.assertIn('Datos de ejemplo', html)

    def test_complete_save_retry_and_manual_edit(self):
        saved = self.app.save(self.capture)
        self.assertTrue(saved['saved'] and saved['journalLinked'])
        note = Path(saved['path'])
        diary = Path(saved['diaryPath'])
        self.assertIn('obsidian://open?', diary.read_text(encoding='utf-8'))
        note.write_text(note.read_text(encoding='utf-8').replace('Comprobación sintética', 'Título editado'), encoding='utf-8')
        retried = self.app.save(self.capture)
        self.assertEqual(retried['title'], 'Título editado')
        self.assertEqual(len(list(self.config['captures'].glob('*.md'))), 1)
        self.assertEqual(diary.read_text(encoding='utf-8').count('<!-- memoria:diario.captura-demo-001 -->'), 1)

    def test_conflicting_identifier_is_rejected(self):
        self.app.save(self.capture)
        with self.assertRaisesRegex(ValueError, 'otro contenido'):
            self.app.save({**self.capture, 'details': 'Cambio que requiere un ID nuevo.'})

    def test_corrupt_capture_is_isolated(self):
        self.app.save(self.capture)
        broken = self.config['captures'] / 'corrupta.md'
        broken.write_text('# Nota dañada\n<!-- captura-meta:invalido -->', encoding='utf-8')
        state = self.app.state()
        self.assertEqual(len(state['captures']), 1)
        self.assertTrue(state['captureIssues'])
        self.assertTrue(broken.exists())

    def test_partial_save_is_recovered_without_false_success(self):
        store = self.app.store()
        original = store.memory.Memory.apply
        def fail_once(instance, scan, plan):
            result = original(instance, scan, plan)
            raise RuntimeError('Fallo simulado antes de confirmar la operación')
        try:
            store.memory.Memory.apply = fail_once
            with self.assertRaisesRegex(RuntimeError, 'simulado'):
                store.save(self.capture)
        finally:
            store.memory.Memory.apply = original
        items, _, issues = self.app.store().read_all()
        self.assertFalse(items[0]['saved'])
        self.assertTrue(issues)
        recovered = self.app.save(self.capture)
        self.assertTrue(recovered['saved'] and recovered['journalLinked'])
        self.assertEqual(len(list(self.config['captures'].glob('*.md'))), 1)

    def test_bad_id_and_dst_time(self):
        with self.assertRaises(ValueError):
            self.app.save({**self.capture, 'id': '../escape'})
        with self.assertRaises(ValueError):
            self.app.save({**self.capture, 'date': '', 'time': '12:00'})
        # Regla de cambio horario, sin relación con fechas académicas reales.
        with self.assertRaisesRegex(ValueError, 'ambigua'):
            storage.clean({**self.capture, 'date': '2030-10-27', 'time': '02:30'})

    def test_review_sha_and_summary_staleness(self):
        subject = self.app.panel['subjects'][0]
        source = subject_source(self.config, subject)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertTrue(subject['summaryNeedsReview'])
        result = update(self.config, {'subjects': [{'id': subject['id'], 'sourceSha': sha,
                                                  'patch': {'checkpoint': 'Comprobación ficticia revisada'}}]})
        self.assertEqual(result['status'], 'saved')
        self.assertFalse(build(self.config)['subjects'][0]['summaryNeedsReview'])
        source.write_text(source.read_text(encoding='utf-8') + '\nEdición manual.\n', encoding='utf-8')
        self.assertTrue(build(self.config)['subjects'][0]['summaryNeedsReview'])
        with self.assertRaisesRegex(ValueError, 'cambió'):
            update(self.config, {'subjects': [{'id': subject['id'], 'sourceSha': sha, 'patch': {'level': 'No guardar'}}]})

    def test_memory_concurrent_edit_is_rejected(self):
        saved = self.app.save(self.capture)
        note = Path(saved['path'])
        cfg = {'timezone': 'Europe/Madrid', 'vaults': [str(self.config['vaults']['degree'])],
               'central': str(self.config['vaults']['hub']), 'files': [str(note)], 'folders': [],
               'forbidden': ['.obsidian'], 'state': str(self.root / 'review-state.json'),
               'history': str(self.root / 'history'), 'backups': str(self.root / 'backups')}
        config_file = self.root / 'memory-test.json'
        memoria.atomic_json(config_file, cfg)
        memory = memoria.Memory(config_file)
        scan = memory.scan()
        before = note.read_text(encoding='utf-8')
        note.write_text(before + '\nCambio concurrente.\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'cambió'):
            memory.apply(scan, {'reviewed': {str(note): {'status': 'leida', 'note': 'Prueba ficticia'}},
                                'operations': [{'id': 'prueba.concurrente', 'path': str(note), 'text': 'No sobrescribir'}]})
        self.assertIn('Cambio concurrente', note.read_text(encoding='utf-8'))
        self.assertNotIn('No sobrescribir', note.read_text(encoding='utf-8'))

    def test_configuration_path_traversal_is_rejected(self):
        raw = json.loads(self.config_path.read_text(encoding='utf-8'))
        raw['captures'] = '../escape'
        self.config_path.write_text(json.dumps(raw), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'dentro'):
            load_config(self.config_path)

    def test_external_memory_config_is_preserved(self):
        old_config = self.app.capture_config
        before = old_config.read_bytes()
        alternate = {**self.config, 'memory_config': old_config}
        connected = Application(alternate)
        saved = connected.save(self.capture)
        self.assertTrue(saved['saved'])
        self.assertEqual(old_config.read_bytes(), before)
        self.assertEqual(connected.store().journal_path(self.capture['id']), self.app.store().journal_path(self.capture['id']))

    def test_demo_preserves_edited_fixture_copy(self):
        subject = self.app.panel['subjects'][0]
        note = subject_source(self.config, subject)
        note.write_text('# Edición propia de la demo\n', encoding='utf-8')
        build(self.config)
        self.assertEqual(note.read_text(encoding='utf-8'), '# Edición propia de la demo\n')

    def test_http_flow_and_origin_protection(self):
        guide = self.root / 'guia.md'
        guide.write_text('# Guía ficticia\n<script>alert(1)</script>\n', encoding='utf-8')
        self.config['documents'] = {'/guia.md': guide}
        server = create_server(self.config, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/health') as response:
                self.assertEqual(json.load(response)['service'], 'mi-grado-memoria')
            with urlopen(base + '/panel.html') as response:
                self.assertIn(b'panel-data', response.read())
            with urlopen(base + '/api/state') as response:
                self.assertEqual(len(json.load(response)['canonical']), 3)
            data = json.dumps(self.capture).encode()
            request = Request(base + '/api/captures', data=data,
                              headers={'Content-Type': 'application/json', 'Origin': base})
            with urlopen(request) as response:
                self.assertTrue(json.load(response)['capture']['saved'])
            denied = Request(base + '/api/captures', data=data,
                             headers={'Content-Type': 'application/json', 'Origin': 'https://example.invalid'})
            with self.assertRaises(HTTPError) as error:
                urlopen(denied)
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(HTTPError) as error:
                urlopen(base + '/config.local.json')
            self.assertEqual(error.exception.code, 404)
            with urlopen(base + '/guia.md') as response:
                self.assertIn(b'<script>', response.read())
            with urlopen(base + '/guia.html') as response:
                body = response.read()
                self.assertIn(b'&lt;script&gt;', body)
                self.assertNotIn(b'<script>', body)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
