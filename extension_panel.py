"""Vistas derivadas: la nota de objetivos sigue siendo la fuente editable."""
from rutas import Path
import datetime, hashlib, json, re
from urllib.parse import quote

FIELDS={'Área':'area','Estado':'status','Prioridad':'priority','Origen':'origin','Propósito':'purpose','Siguiente paso':'next','Indicador':'indicator','Plazo':'deadline'}

def goal_data(path, vault):
    path, vault = Path(path), Path(vault)
    result={'items':[], 'available':False, 'issues':[], 'readAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if not path.exists():
        result['issues'].append('No se encontró la fuente de objetivos. Configura su nota en Obsidian.')
        return result
    try:
        relative=path.resolve().relative_to(vault.resolve()).as_posix()
        body=path.read_text(encoding='utf-8-sig')
    except (OSError, ValueError) as error:
        result['issues'].append('Fuente de objetivos no disponible en la bóveda configurada: '+str(error))
        return result
    result.update(available=True,source={'title':'Objetivos en Obsidian','path':path.as_posix(),'modifiedAt':datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat(),'url':'obsidian://open?vault='+quote(vault.name)+'&file='+quote(relative)},sha=hashlib.sha256(body.encode()).hexdigest())
    current=None
    ids=set()
    for line in body.splitlines():
        match=re.fullmatch(r'## \[([a-z0-9_-]+)\] (.+)',line)
        if match:
            ident, title=match.groups()
            if ident in ids:
                result['issues'].append('Identificador de objetivo repetido: '+ident)
                current=None
                continue
            ids.add(ident)
            current=dict(id=ident,title=title,milestones=[],source=result['source'])
            result['items'].append(current)
        elif line.startswith('## '):
            current=None
        elif current:
            milestone=re.fullmatch(r'- \[([ xX])\] (.+)',line)
            if milestone:
                current['milestones'].append({'done':milestone.group(1).lower()=='x','title':milestone.group(2)})
            elif ':' in line:
                name,value=line.split(':',1)
                if name in FIELDS: current[FIELDS[name]]=value.strip()
    if not result['items']:
        result['issues'].append('La nota existe, pero no tiene secciones ## [id] Título. No se inventan objetivos.')
    return result

def load_extension(output, hub, goals_path=None):
    output,hub=Path(output),Path(hub)
    goals=goal_data(goals_path or hub/'30 Áreas/Objetivos/Objetivos.md',hub)
    team={'roles':[], 'issues':[], 'snapshot':None}
    for name in ('equipo.local.json','equipo.example.json'):
        path=output/name
        if path.exists():
            try:
                loaded=json.loads(path.read_text(encoding='utf-8-sig'))
                if not isinstance(loaded,dict) or not isinstance(loaded.get('roles'),list):
                    raise ValueError('Falta la lista de roles')
                team=loaded
                valid=[];ids=set();issues=list(team.get('issues') or [])
                for role in team['roles']:
                    if not isinstance(role,dict) or not isinstance(role.get('id'),str) or not role['id'] or role['id'] in ids or role.get('group') not in {'head','reviewer','support'} or not isinstance(role.get('domain'),str):
                        issues.append('Se ha aislado un rol nulo, duplicado o no válido; revisa el registro de equipo.')
                        continue
                    ids.add(role['id']);valid.append(role)
                team['roles']=valid;team['issues']=issues
            except (ValueError,OSError) as error:
                team['issues']=['Registro de equipo no válido: '+str(error)]
            break
    return {'goals':goals,'team':team}
