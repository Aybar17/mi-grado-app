"""Servicio solo local; captura declaraciones sin inferir aprendizaje."""
from rutas import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit
import argparse
import hashlib
import html
import json
import threading
import base64
import subprocess
import sys

from configuracion import ROOT, add_options, load_config, read_panel, subject_source
from generar_panel import build, note_url
import memoria
import persistencia_capturas as storage
from conexiones import read_settings, save_settings, calendar_preview, import_calendar, local_models, local_chat
from gestion import management_state, save_subject, save_task, save_schedule, save_reference
from copias import export_backup, preview_backup, restore_backup, MAX_BYTES
from cuaderno_web import export_notebook, imported_topics
from intercambio_web import prepare_exchange, preview_exchange, apply_exchange, download_exchange


class Application:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.panel = build(config)
        self.last_signature = None
        self.restorations = {}
        storage.SUBJECTS = {s['id']: s['name'] for s in self.panel['subjects']}
        storage.SUBJECTS['general'] = 'General / disponibilidad'
        cfg = {'timezone': 'Europe/Madrid',
               'vaults': [str(v) for v in config['vaults'].values()],
               'central': str(config['vaults']['hub']),
               'files': [], 'folders': [str(config['captures']), str(config['vaults']['hub'] / 'Notas diarias')],
               'forbidden': ['.obsidian', '.git', '.venv', 'sources'],
               'state': str(config['runtime'] / 'capture-state.json'),
               'history': str(config['runtime'] / 'capture-history'),
               'backups': str(config['runtime'] / 'capture-backups')}
        self.capture_config = config.get('memory_config') or config['runtime'] / 'capture-config.json'
        if config.get('memory_config'):
            existing = memoria.Memory(self.capture_config)
            # Reutilizar el protocolo anterior sin sustituir su alcance ni puntos.
            if not existing.allowed(config['captures'] / 'scope-check.md') or not existing.allowed(config['vaults']['hub'] / 'Notas diarias' / 'scope-check.md'):
                raise ValueError('La configuración de memoria no autoriza capturas y diario en estos destinos')
        elif not self.capture_config.exists() or memoria.read_json(self.capture_config) != cfg:
            memoria.atomic_json(self.capture_config, cfg)

    def store(self):
        c = self.config
        storage.SUBJECTS = {s['id']: s['name'] for s in read_panel(c)['subjects']}
        storage.SUBJECTS['general'] = 'General / disponibilidad'
        return storage.CaptureStore(memoria, self.capture_config, c['vaults']['degree'], c['vaults']['hub'], c['captures'])

    def save(self, raw):
        with self.lock:
            return self.store().save(raw)

    def state(self):
        with self.lock:
            now = memoria.madrid_time()
            titles = [(str(file), file.stat().st_mtime_ns, file.stat().st_size)
                      for vault in self.config['vaults'].values() for file in sorted(vault.rglob('*.md'))
                      if '.obsidian' not in file.parts and file.resolve().is_relative_to(vault)]
            titles.extend((str(file), file.stat().st_mtime_ns, file.stat().st_size)
                          for file in (self.config['panel_file'], ROOT / 'panel-template.html', ROOT/'team-ui.js', ROOT/'panel-extra.js', ROOT/'modelos.json', ROOT/'extension_panel.py',ROOT/'apoyo-diseno.css') if file.exists())
            for file in (ROOT / 'conexiones-ui.js', ROOT / 'gestion-ui.js', ROOT/'intercambio-ui.js', ROOT/'materiales-ui.js', self.config['runtime'] / 'conexiones.json'):
                if file.exists(): titles.append((str(file), file.stat().st_mtime_ns, file.stat().st_size))
            for file in (ROOT / 'identidad.css', ROOT / 'assets' / 'mi-grado.svg', ROOT/'interfaz.js', ROOT/'flujo-estudio.js'):
                if file.exists(): titles.append((str(file), file.stat().st_mtime_ns, file.stat().st_size))
            for file in (self.config['runtime']/'equipo.local.json',self.config['runtime']/'equipo.example.json'):
                if file.exists():titles.append((str(file),file.stat().st_mtime_ns,file.stat().st_size))
            titles.append(('today', now[:10]))
            # Las fichas y objetivos pueden restaurarse conservando tamaño/mtime.
            # Su SHA protege la vigencia; no se lee el cuerpo de las otras áreas.
            for subject in read_panel(self.config)['subjects']:
                file=subject_source(self.config,subject)
                if file.exists():titles.append(('canonical-sha',str(file),hashlib.sha256(file.read_bytes()).hexdigest()))
            try:
                titles.extend(('web-topic-sha',json.dumps(record,sort_keys=True,ensure_ascii=False)) for record,_ in imported_topics(self.config,read_panel(self.config)['subjects']))
            except (ValueError,KeyError,OSError,TypeError) as error:
                titles.append(('web-topic-issue',str(error)))
            goal_file=self.config.get('goals_file') or self.config['vaults']['hub']/'30 Áreas/Objetivos/Objetivos.md'
            if Path(goal_file).exists():titles.append(('goal-sha',hashlib.sha256(Path(goal_file).read_bytes()).hexdigest()))
            signature = hashlib.sha256(json.dumps(titles).encode()).hexdigest()
            if signature != self.last_signature:
                self.panel = build(self.config, now)
                self.last_signature = signature
            canonical = []
            for subject in self.panel['subjects']:
                file = subject_source(self.config, subject)
                if file.exists():
                    canonical.append({'id': subject['id'], 'path': file.as_posix(),
                                      'text': file.read_text(encoding='utf-8-sig'),
                                      'modified': file.stat().st_mtime_ns,
                                      'url': note_url(self.config['vaults']['degree'], file.relative_to(self.config['vaults']['degree']).as_posix())})
            captures, capture_issues, journal_issues = self.store().read_all()
            return {'version': 2, 'panel': self.panel, 'captures': captures, 'canonical': canonical,
                    'notes': self.panel['notes'], 'memory': self.panel['memory'],
                    'panelRevision': self.panel['revision'], 'captureIssues': capture_issues,
                    'journalIssues': journal_issues, 'issues': capture_issues + journal_issues,
                    'snapshotDate': self.panel.get('checked'), 'today': now[:10], 'time': now,
                    'daily': self.config.get('daily', 'no configurada')}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def safe_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def output(self, code, data, content='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(code)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.safe_host():
            return self.output(403, {'error': 'Origen local requerido'})
        route = urlsplit(self.path).path
        try:
            app = self.server.app
            if route == '/api/health':
                return self.output(200, {'service': 'mi-grado-memoria', 'version': 2, 'demo': app.config['demo'],'instance':hashlib.sha256(str(app.config['path']).encode()).hexdigest()[:16]})
            if route == '/api/state':
                return self.output(200, app.state())
            if route == '/api/settings':
                return self.output(200, read_settings(app.config))
            if route == '/api/manage':
                with app.lock: result = management_state(app.config)
                return self.output(200, result)
            if route == '/api/backup/download':
                return self.output(200, export_backup(app), 'application/zip')
            if route == '/api/notebook/web':
                return self.output(200, export_notebook(app))
            if route in ('/', '/panel.html'):
                return self.output(200, (app.config['runtime'] / 'panel.html').read_bytes(), 'text/html; charset=utf-8')
            documents = app.config.get('documents', {})
            if route in documents:
                return self.output(200, documents[route].read_bytes(), 'text/plain; charset=utf-8')
            readers = {name.removesuffix('.md') + '.html': file for name, file in documents.items()}
            if route in readers:
                file = readers[route]
                text = file.read_text(encoding='utf-8-sig')
                title = next((line.lstrip('# ').strip() for line in text.splitlines() if line.startswith('# ')), file.stem)
                page = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><style>body{max-width:1000px;margin:32px auto;padding:0 24px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.6 ui-monospace,monospace}</style><a href="/panel.html#asignaturas">Volver a mis asignaturas</a><h1>' + html.escape(title) + '</h1><pre>' + html.escape(text) + '</pre></html>'
                return self.output(200, page.encode('utf-8'), 'text/html; charset=utf-8')
            return self.output(404, {'error': 'Ruta no disponible'})
        except ValueError as error:
            return self.output(400, {'error': str(error)})
        except Exception:
            return self.output(500, {'error': 'No se pudo consultar la fuente local; revisar configuración y archivos'})

    def do_POST(self):
        port = self.server.server_port
        allowed = (f'http://127.0.0.1:{port}', f'http://localhost:{port}')
        if not self.safe_host() or self.headers.get('Origin') not in allowed:
            # Consumir cuerpos pequeños ya enviados evita un reset TCP antes del 403
            # en Windows; no interpretar ni guardar datos de un origen rechazado.
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if 0 < length <= 200000:
                    self.connection.settimeout(2)
                    self.rfile.read(length)
            except (OSError, ValueError):
                pass
            return self.output(403, {'error': 'Origen local requerido'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.output(415, {'error': 'Se requiere JSON'})
        route = urlsplit(self.path).path
        if route not in {'/api/captures', '/api/settings', '/api/calendar/preview',
                         '/api/calendar/import', '/api/local-ai/models', '/api/local-ai/chat',
                         '/api/manage/subject', '/api/manage/task', '/api/manage/schedule', '/api/manage/reference',
                         '/api/backup/preview', '/api/backup/restore', '/api/backup/open',
                         '/api/notebook/web/prepare', '/api/notebook/web/preview', '/api/notebook/web/apply','/api/notebook/web/download'}:
            return self.output(404, {'error': 'Ruta no disponible'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            limit = 45 * 1024 * 1024 if route in {'/api/backup/preview', '/api/backup/restore'} else 5 * 1024 * 1024 if route=='/api/notebook/web/preview' else 300000 if route == '/api/captures' else 200000
            if not 0 < size <= limit:
                raise ValueError('Tamaño no admitido')
            raw = json.loads(self.rfile.read(size))
            app = self.server.app
            if route == '/api/captures':
                return self.output(200, {'capture': app.save(raw)})
            if route=='/api/notebook/web/download':
                if not isinstance(raw,dict) or set(raw)!={'exchangeId'}:raise ValueError('Selecciona el traslado que has revisado.')
                result=download_exchange(app,raw['exchangeId'])
            elif route == '/api/notebook/web/prepare':
                if raw!={}:raise ValueError('La preparación no admite otros parámetros.')
                result=prepare_exchange(app)
            elif route == '/api/notebook/web/preview':
                if not isinstance(raw,dict) or set(raw)!={'book'}:raise ValueError('Selecciona el JSON del cuaderno web.')
                result=preview_exchange(app,raw['book'])
            elif route == '/api/notebook/web/apply':
                if not isinstance(raw,dict) or set(raw)!={'token','choices'}:raise ValueError('Revisa y elige los cambios antes de guardarlos.')
                result=apply_exchange(app,raw['token'],raw['choices'])
            elif route == '/api/settings':
                with app.lock: result = save_settings(app.config, raw)
            elif route in {'/api/manage/subject', '/api/manage/task', '/api/manage/schedule','/api/manage/reference'}:
                operation = {'/api/manage/subject': save_subject, '/api/manage/task': save_task,
                             '/api/manage/schedule': save_schedule,'/api/manage/reference':save_reference}[route]
                with app.lock: result = operation(app.config, raw)
            elif route in {'/api/backup/preview', '/api/backup/restore'}:
                expected = {'archive'} if route.endswith('preview') else {'archive', 'sha'}
                if not isinstance(raw, dict) or set(raw) != expected or not isinstance(raw['archive'], str):
                    raise ValueError('Selecciona una copia de Mi grado.')
                try: data = base64.b64decode(raw['archive'], validate=True)
                except ValueError: raise ValueError('La copia no está codificada correctamente.')
                if len(data) > MAX_BYTES: raise ValueError('La copia supera 32 MB.')
                if route.endswith('preview'): result = preview_backup(data)
                else:
                    with app.lock:
                        result = restore_backup(data, raw['sha'])
                        token = hashlib.sha256(result['config'].encode()).hexdigest()
                        app.restorations[token] = result['config']
                        result['token'] = token
            elif route == '/api/backup/open':
                if not isinstance(raw, dict) or set(raw) != {'token'} or raw['token'] not in app.restorations:
                    raise ValueError('Restaura primero el cuaderno en esta sesión.')
                path = app.restorations[raw['token']]
                command = [sys.executable] + ([] if getattr(sys, 'frozen', False) else [str(ROOT/'escritorio.py')]) + ['--config', path]
                subprocess.Popen(command, cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                result = {'opened': True}
            elif route == '/api/calendar/preview':
                if not isinstance(raw, dict) or set(raw) != {'content'}:
                    raise ValueError('Selecciona un calendario .ics.')
                with app.lock: result = calendar_preview(app.config, raw['content'])
            elif route == '/api/calendar/import':
                with app.lock: result = import_calendar(app.config, raw, app.save)
            elif route == '/api/local-ai/models':
                if raw != {}: raise ValueError('La consulta de modelos no admite parámetros.')
                result = local_models()
            else:
                result = local_chat(raw)
            return self.output(200, result)
        except (ValueError, KeyError) as error:
            return self.output(400, {'error': str(error)})
        except Exception as error:
            return self.output(409, {'error': 'No se ha confirmado el guardado: ' + str(error)})


def create_server(config, port=8770):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    try:
        server.app = Application(config)
    except Exception:
        server.server_close()
        raise
    return server


def main():
    parser = add_options(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--capture', type=Path, help='JSON de una declaración explícita')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    config = load_config(args.config, args.demo)
    if args.capture or args.refresh:
        app = Application(config)
        result = app.save(memoria.read_json(args.capture)) if args.capture else {'status': 'generated', 'demo': config['demo']}
        print(json.dumps(result, ensure_ascii=False))
        return
    with create_server(config, args.port) as server:
        print(f'Panel local: http://127.0.0.1:{server.server_port}/panel.html', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
