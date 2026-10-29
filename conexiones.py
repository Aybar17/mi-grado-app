"""Conexiones sin servicios de pago: chat externo, calendario y Ollama local."""
from datetime import datetime
from rutas import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import hashlib
import json
import re

from memoria import atomic_text, madrid_time
from perfiles import campus_url
from persistencia_capturas import writer_lock

CHATS = {'chatgpt': 'https://chatgpt.com/', 'claude': 'https://claude.ai/',
         'gemini': 'https://gemini.google.com/'}


def read_settings(config):
    path = config['runtime'] / 'conexiones.json'
    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    campus = config.get('campus', {})
    return {'center': value.get('center', campus.get('center', 'Otro centro')),
            'campus_url': value.get('campus_url', campus.get('url', '')),
            'chat': value.get('chat', config.get('ai_chat', 'chatgpt')),
            'chats': CHATS, 'local_ai': 'ollama', 'paid_api': False}


def save_settings(config, raw):
    if not isinstance(raw, dict) or set(raw) != {'center', 'campus_url', 'chat'}:
        raise ValueError('Configura centro, dirección del campus y chat.')
    if raw['center'] not in {'UGR', 'Otra universidad', 'FP', 'Otro centro'} or raw['chat'] not in CHATS:
        raise ValueError('Centro o chat desconocido.')
    if not isinstance(raw['campus_url'], str) or len(raw['campus_url']) > 1000:
        raise ValueError('Dirección del campus no válida.')
    value = {**raw, 'campus_url': campus_url(raw['campus_url'])}
    with writer_lock(config['runtime'] / 'connections-writer.lock'):
        atomic_text(config['runtime'] / 'conexiones.json', json.dumps(value, ensure_ascii=False, indent=2))
    return read_settings(config)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('La IA local intentó redirigir la petición; no se envió a otro servidor.')


def ollama_request(route, payload=None, timeout=5):
    # Sin proxies, direcciones configurables, cuentas cloud ni claves comerciales.
    request = Request('http://127.0.0.1:11434/api/' + route,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json'})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('La respuesta de la IA local es demasiado grande.')
        return json.loads(data)
    except (OSError, ValueError) as error:
        raise ValueError('No se pudo consultar Ollama local. Comprueba que está abierto en el puerto 11434.') from error


def local_models():
    value = ollama_request('tags')
    if not isinstance(value, dict) or not isinstance(value.get('models'), list):
        raise ValueError('Ollama no devolvió una lista de modelos válida.')
    models = []
    for model in value['models']:
        name = model.get('name', '') if isinstance(model, dict) else ''
        if (isinstance(name, str) and name and len(name) <= 160 and 'cloud' not in name.lower()
                and model.get('size', 0) > 0 and not model.get('remote_host') and not model.get('remote_model')):
            models.append(name)
    return {'models': models, 'cost': 'Sin API de pago; usa modelos descargados en este ordenador.'}


def local_chat(raw):
    if not isinstance(raw, dict) or set(raw) != {'model', 'context', 'question'}:
        raise ValueError('Elige un modelo local, contexto y pregunta.')
    if any(not isinstance(raw[key], str) for key in raw):
        raise ValueError('La consulta debe contener texto.')
    if not raw['question'].strip() or len(raw['question']) > 8000 or len(raw['context']) > 40000:
        raise ValueError('Escribe una pregunta de hasta 8000 caracteres y un contexto de hasta 40000.')
    if raw['model'] not in local_models()['models']:
        raise ValueError('El modelo no está descargado localmente o corresponde a un servicio cloud.')
    info = ollama_request('show', {'model': raw['model']})
    if info.get('remote_host') or info.get('remote_model') or not info.get('model_info'):
        raise ValueError('Este modelo no confirma ejecución local. No se hará la consulta.')
    response = ollama_request('chat', {
        'model': raw['model'], 'stream': False,
        'messages': [{'role': 'system', 'content': 'Ayuda a estudiar una idea cada vez. '
                      'Distingue un intento propio de ayuda. No inventes fuentes, entregas ni progreso.'},
                     {'role': 'user', 'content': raw['context'] + '\n\nPregunta: ' + raw['question']}],
        'options': {'num_predict': 1024}}, timeout=110)
    message = response.get('message', {}).get('content')
    if not isinstance(message, str) or not message.strip():
        raise ValueError('El modelo no devolvió una respuesta de texto. Prueba un modelo de conversación.')
    return {'text': message, 'model': raw['model'], 'source': 'Ollama local',
            'saved': False, 'evidence': 'Respuesta de IA; no demuestra comprensión autónoma.'}


def ics_text(value):
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1] in 'nN' else m[1], value)


def calendar_preview(config, content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > 65000:
        raise ValueError('Elige un calendario .ics de hasta 65 KB.')
    if not content.lstrip('\ufeff\r\n ').startswith('BEGIN:VCALENDAR'):
        raise ValueError('El archivo no es un calendario iCalendar.')
    unfolded = re.sub(r'\r?\n[ \t]', '', content)
    events, issues, event = [], [], None
    for line in unfolded.splitlines():
        if line == 'BEGIN:VEVENT':
            event = {}
        elif line == 'END:VEVENT' and event is not None:
            if len(events) >= 200:
                raise ValueError('Máximo 200 eventos por importación.')
            try:
                if event.get('RRULE') or event.get('RECURRENCE-ID') or event.get('STATUS') == 'CANCELLED':
                    raise ValueError('Evento recurrente o cancelado: revisar manualmente.')
                uid = event.get('UID', '')
                title = ics_text(event.get('SUMMARY', '')).strip()
                date_value, params = event.get('DTSTART', ''), event.get('_date_params', '')
                if not uid or not title or len(title) > 200:
                    raise ValueError('Evento sin identificador o título válido.')
                time = ''
                if re.fullmatch(r'\d{8}', date_value):
                    date = datetime.strptime(date_value, '%Y%m%d').date().isoformat()
                else:
                    moment = datetime.strptime(date_value.rstrip('Z'), '%Y%m%dT%H%M%S')
                    if date_value.endswith('Z'):
                        moment = moment.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Madrid'))
                    elif 'TZID=' in params:
                        tz = params.split('TZID=', 1)[1].split(';', 1)[0].strip('"')
                        moment = moment.replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo('Europe/Madrid'))
                    else:
                        raise ValueError('Hora sin zona: confirmar manualmente antes de importarla.')
                    date, time = moment.date().isoformat(), moment.strftime('%H:%M')
                event_id = 'ics-' + hashlib.sha256(uid.encode()).hexdigest()[:24]
                if any(e['importId'] == event_id for e in events):
                    raise ValueError('Identificador de evento repetido.')
                events.append({'importId': event_id, 'title': title, 'date': date, 'time': time,
                               'timezone': 'Europe/Madrid',
                               'detail': ics_text(event.get('DESCRIPTION', ''))[:2000]})
            except (ValueError, ZoneInfoNotFoundError) as error:
                issues.append(str(error) if not isinstance(error, ZoneInfoNotFoundError)
                              else 'Falta la zona horaria del calendario; prueba la aplicación Windows o confirma la fecha manualmente.')
            event = None
        elif event is not None and ':' in line:
            key, value = line.split(':', 1)
            field = key.split(';', 1)[0].upper()
            event[field] = value
            if field == 'DTSTART': event['_date_params'] = key
    if event is not None:
        raise ValueError('El archivo contiene un evento incompleto.')
    return {'events': events, 'issues': issues,
            'panelSha': hashlib.sha256(config['panel_file'].read_bytes()).hexdigest(),
            'status': 'Vista previa; aún no se ha guardado ninguna fecha.'}


def import_calendar(config, raw, save_capture):
    if not isinstance(raw, dict) or set(raw) != {'content', 'assignments', 'panelSha'}:
        raise ValueError('Revisa el calendario y asigna cada evento a una asignatura.')
    preview = calendar_preview(config, raw['content'])
    if preview['panelSha'] != raw['panelSha']:
        raise ValueError('El panel cambió desde la vista previa. Revisa el calendario de nuevo.')
    assignments = raw['assignments']
    if not isinstance(assignments, dict) or not assignments:
        raise ValueError('Selecciona al menos un evento y su asignatura.')
    events = {event['importId']: event for event in preview['events']}
    if set(assignments) - set(events):
        raise ValueError('Hay eventos fuera de la vista previa.')
    with writer_lock(config['runtime'] / 'review-writer.lock'):
        before = config['panel_file'].read_bytes()
        if hashlib.sha256(before).hexdigest() != raw['panelSha']:
            raise ValueError('El panel cambió. Vuelve a revisar la importación.')
        panel = json.loads(before.decode('utf-8-sig'))
        ids = {subject['id'] for subject in panel['subjects']}
        if any(subject not in ids for subject in assignments.values()):
            raise ValueError('Una asignatura elegida ya no existe.')
        keep = [event for event in panel.get('deadlines', []) if event.get('importId') not in assignments]
        now = madrid_time()
        imported = [{**events[event_id], 'subject': subject, 'importedAt': now,
                     'evidence': 'Importado de archivo; no confirma una entrega realizada.'}
                    for event_id, subject in assignments.items()]
        canonical = [{k: v for k, v in event.items() if k != 'importedAt'} for event in imported]
        canonical.sort(key=lambda event: event['importId'])
        details = 'Fechas aportadas desde un archivo iCalendar; requieren contraste en el campus.\n\n' + json.dumps(canonical, ensure_ascii=False, indent=2)
        if len(details) > 16000:
            raise ValueError('Esta selección es demasiado grande. Importa menos eventos en cada paso.')
        capture_id = 'calendario-' + hashlib.sha256(details.encode()).hexdigest()[:32]
        captured = save_capture({'id': capture_id, 'subject': 'general', 'kind': 'Calendario importado',
                    'title': 'Fechas aportadas desde mi campus', 'date': '', 'time': '',
                    'timezone': 'Europe/Madrid', 'evidence': 'Pendiente de verificar',
                    'source': 'Archivo .ics seleccionado por el usuario', 'details': details, 'created': ''})
        if not captured.get('saved') or captured.get('saveState') != 'complete' or not captured.get('journalLinked'):
            raise ValueError('La fuente del calendario no tiene cierre confirmado. Reintenta antes de aplicar las fechas.')
        for event in imported:
            event['source'] = {'title': 'Calendario aportado; pendiente de contraste actual', 'url': captured['url']}
            event['canonicalCaptureId'] = capture_id
        panel['deadlines'] = keep + imported
        backup = config['runtime'] / 'review-backups' / (hashlib.sha256(before).hexdigest() + '.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with backup.open('xb') as out: out.write(before)
        def verify():
            if backup.read_bytes() != before or config['panel_file'].read_bytes() != before:
                raise ValueError('Edición concurrente. Se ha conservado la copia anterior.')
        verify()
        atomic_text(config['panel_file'], json.dumps(panel, ensure_ascii=False, indent=2), before_replace=verify)
    return {'saved': True, 'events': len(imported), 'officialCheckedAt': panel.get('checked'),
            'canonicalUrl': captured['url'], 'journalLinked': True}
