"""Conectores sin llamadas reales de IA: fechas, origen local y exclusión cloud."""
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
import hashlib
import json
import tempfile
import threading
import unittest

from perfiles import create_profile
from conexiones import calendar_preview, import_calendar, save_settings, local_models, local_chat
from puente_memoria import Application, create_server

ICS = 'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:entrega-ficticia-001\r\nSUMMARY:Práctica de ejemplo\r\nDTSTART;VALUE=DATE:20261020\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mi-grado-conexion-')
        self.root = Path(self.tmp.name)
        self.config = create_profile(self.root/'Perfil'/'config.json', self.root/'Apuntes', ['Datos de ejemplo'])
        self.app = Application(self.config)

    def tearDown(self): self.tmp.cleanup()

    def request_for_calendar(self, content=ICS):
        preview = calendar_preview(self.config, content)
        return {'content': content, 'panelSha': preview['panelSha'],
                'assignments': {preview['events'][0]['importId']: self.app.panel['subjects'][0]['id']}}

    def test_calendar_preview_has_no_writes_and_import_has_canonical_source(self):
        before = self.config['panel_file'].read_bytes()
        raw = self.request_for_calendar()
        self.assertEqual(before, self.config['panel_file'].read_bytes())
        self.assertEqual(self.app.store().read_all()[0], [])
        first = import_calendar(self.config, raw, self.app.save)
        self.assertTrue(first['journalLinked'])
        self.assertIsNone(first['officialCheckedAt'])
        result = json.loads(self.config['panel_file'].read_text(encoding='utf-8'))
        self.assertEqual(result['deadlines'][0]['date'], '2026-10-20')
        self.assertIn('obsidian://', result['deadlines'][0]['source']['url'])
        second = import_calendar(self.config, self.request_for_calendar(), self.app.save)
        self.assertEqual(second['events'], 1)
        self.assertEqual(len(json.loads(self.config['panel_file'].read_text(encoding='utf-8'))['deadlines']), 1)
        self.assertEqual(len(self.app.store().read_all()[0]), 1)

    def test_calendar_conflict_and_incomplete_capture_never_apply_dates(self):
        raw = self.request_for_calendar()
        before = self.config['panel_file'].read_bytes()
        with self.assertRaises(ValueError): import_calendar(self.config, raw, lambda _: {'saved': False})
        self.assertEqual(before, self.config['panel_file'].read_bytes())
        self.config['panel_file'].write_bytes(before + b'\n')
        with self.assertRaises(ValueError): import_calendar(self.config, raw, self.app.save)
        self.assertEqual(self.app.store().read_all()[0], [])

    def test_ambiguous_and_recurring_calendar_events_are_not_imported(self):
        content = ICS.replace('DTSTART;VALUE=DATE:20261020', 'DTSTART:20261020T130000')
        self.assertEqual(calendar_preview(self.config, content)['events'], [])
        recurring = ICS.replace('END:VEVENT', 'RRULE:FREQ=WEEKLY\r\nEND:VEVENT')
        preview = calendar_preview(self.config, recurring)
        self.assertEqual(preview['events'], [])
        self.assertTrue(preview['issues'])

    def test_local_model_request_never_accepts_cloud_or_unknown_models(self):
        response = {'models': [{'name': 'modelo-local', 'size': 100},
                               {'name': 'remoto:cloud', 'size': 100},
                               {'name': 'alias-remoto', 'size': 10, 'remote_host': 'https://example.org'}]}
        with patch('conexiones.ollama_request', return_value=response) as request:
            self.assertEqual(local_models()['models'], ['modelo-local'])
            with self.assertRaises(ValueError): local_chat({'model': 'remoto:cloud', 'context': '', 'question': 'Hola'})
            self.assertFalse(any(call.args[0] == 'chat' for call in request.call_args_list))

    def test_only_validated_local_model_receives_visible_prompt_and_returns_text(self):
        responses = [{'models': [{'name': 'modelo-local', 'size': 100}]},
                     {'model_info': {'general.architecture': 'ficticia'}},
                     {'message': {'content': 'Respuesta ficticia'}}]
        with patch('conexiones.ollama_request', side_effect=responses) as request:
            result = local_chat({'model': 'modelo-local', 'context': 'Ficha elegida', 'question': 'Mi pregunta'})
        self.assertEqual(result['text'], 'Respuesta ficticia')
        self.assertFalse(result['saved'])
        self.assertFalse(request.call_args_list[-1].args[1]['stream'])
        self.assertIn('Ficha elegida', request.call_args_list[-1].args[1]['messages'][1]['content'])

    def test_settings_and_connector_posts_require_origin_and_have_no_paid_api(self):
        server = create_server(self.config, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(route, data, origin):
            return urlopen(Request(base + route, data=json.dumps(data).encode(),
                                  headers={'Origin': origin, 'Content-Type': 'application/json'}), timeout=10)
        try:
            with self.assertRaises(HTTPError) as error:
                post('/api/settings', {'center':'FP','chat':'claude','campus_url':'https://example.org'}, 'https://example.org')
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            with post('/api/settings', {'center':'FP','chat':'claude','campus_url':'https://example.org'}, base) as response:
                self.assertFalse(json.load(response)['paid_api'])
            with self.assertRaises(HTTPError) as error: post('/api/paid-ai', {}, base)
            self.assertEqual(error.exception.code, 404); error.exception.close()
            with post('/api/calendar/preview', {'content': ICS}, base) as response:
                self.assertEqual(len(json.load(response)['events']), 1)
        finally:
            server.shutdown(); server.server_close(); worker.join()


if __name__ == '__main__': unittest.main()
