"""Configuración portable. Las rutas relativas se resuelven junto al JSON."""
from rutas import Path
import argparse
import json
import os
import re

ROOT = Path(__file__).resolve().parent
DEMO_CONFIG = ROOT / 'examples' / 'demo' / 'config.json'


def add_options(parser):
    parser.add_argument('--config', type=Path, help='Configuración local; también MI_GRADO_CONFIG')
    parser.add_argument('--demo', action='store_true', help='Usar exclusivamente datos ficticios locales')
    return parser


def load_config(path=None, demo=False):
    selected = DEMO_CONFIG if demo else path or os.environ.get('MI_GRADO_CONFIG')
    if selected is None:
        selected = ROOT / 'config.local.json'
        if not selected.exists():
            raise ValueError('Crea config.local.json o usa --demo')
    selected = Path(selected).resolve()
    raw = json.loads(selected.read_text(encoding='utf-8-sig'))
    if raw.get('version') != 1 or raw.get('timezone') != 'Europe/Madrid':
        raise ValueError('Se requiere versión 1 y timezone Europe/Madrid')
    if 'web_notebook_id' in raw:
        from validar_cuaderno import ident
        ident(raw['web_notebook_id'])
    base = selected.parent
    def absolute(value):
        return (base / value).resolve()
    vaults = raw.get('vaults', {})
    if not isinstance(vaults, dict) or not vaults.get('degree') or not vaults.get('hub'):
        raise ValueError('Faltan vaults.degree y vaults.hub')
    resolved = {role: absolute(value) for role, value in vaults.items() if value}
    if len({str(path) for path in resolved.values()}) != len(resolved):
        raise ValueError('Cada bóveda debe tener su propia carpeta')
    runtime = absolute(raw['runtime'])
    if any(runtime.is_relative_to(vault) or vault.is_relative_to(runtime) for vault in resolved.values()):
        # Se admite una raíz común (runtime/demo), pero runtime guarda solo artefactos técnicos.
        raise ValueError('El runtime técnico y las bóvedas deben ocupar carpetas separadas')
    captures = (resolved['degree'] / raw.get('captures', '06 Registro de clase/Capturas')).resolve()
    if not captures.is_relative_to(resolved['degree']):
        raise ValueError('Las capturas deben quedar dentro de la bóveda del grado')
    panel_file = absolute(raw['panel_file'])
    if any(panel_file.is_relative_to(vault) for vault in resolved.values()):
        raise ValueError('El resumen reconstruible debe estar fuera de las bóvedas')
    documents = raw.get('documents', {})
    if not isinstance(documents, dict):
        raise ValueError('documents debe ser un mapa de rutas explícitas')
    document_paths = {}
    for route, value in documents.items():
        if not isinstance(route, str) or not re.fullmatch(r'/[A-Za-z0-9_-]+\.md', route):
            raise ValueError('Ruta de documento no admitida')
        file = absolute(value)
        if file.suffix != '.md':
            raise ValueError('Solo documentos Markdown explícitos')
        document_paths[route] = file
    memory_config = absolute(raw['memory_config']) if raw.get('memory_config') else None
    goals_file = absolute(raw['goals_file']) if raw.get('goals_file') else None
    if goals_file and (not goals_file.is_relative_to(resolved['hub']) or goals_file.suffix!='.md'):
        raise ValueError('La nota de objetivos debe estar dentro de la bóveda central')
    return {**raw, 'path': selected, 'vaults': resolved, 'runtime': runtime,
            'captures': captures, 'panel_file': panel_file,
            'documents': document_paths, 'memory_config': memory_config, 'goals_file': goals_file,
            'demo': bool(demo or selected == DEMO_CONFIG.resolve())}


def initialize_demo(config):
    """Copia únicamente los ejemplos ficticios, sin reemplazar ediciones existentes."""
    if not config['demo']:
        return
    if not config['panel_file'].exists():
        config['panel_file'].parent.mkdir(parents=True, exist_ok=True)
        with config['panel_file'].open('xb') as stream:
            stream.write((ROOT / 'examples' / 'demo' / 'panel.json').read_bytes())
    fixtures = ROOT / 'examples' / 'demo' / 'notes'
    for role, vault in config['vaults'].items():
        source = fixtures / role
        if not source.exists():
            continue
        for file in sorted(source.rglob('*.md')):
            destination = vault / file.relative_to(source)
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Apertura exclusiva: una edición concurrente no se reemplaza.
                with destination.open('xb') as stream:
                    stream.write(file.read_bytes())


def read_panel(config):
    value = json.loads(config['panel_file'].read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or not isinstance(value.get('subjects'), list):
        raise ValueError('El resumen debe contener una lista subjects')
    ids = [item.get('id') for item in value['subjects'] if isinstance(item, dict)]
    if len(ids) != len(value['subjects']) or not ids or len(set(ids)) != len(ids):
        raise ValueError('Asignaturas ausentes o duplicadas')
    if any(not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,40}', sid) for sid in ids):
        raise ValueError('Identificadores de asignatura inválidos')
    return value


def subject_source(config, subject):
    relative = subject.get('note')
    if not isinstance(relative, str) or not relative:
        raise ValueError('Cada asignatura necesita note relativa a la bóveda del grado')
    path = (config['vaults']['degree'] / relative).resolve()
    if not path.is_relative_to(config['vaults']['degree']) or path.suffix != '.md':
        raise ValueError('Ficha fuera de la bóveda del grado')
    return path
