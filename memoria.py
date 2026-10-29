# Adaptado del módulo de la skill local cerrar-sesion-memoria; véase ATTRIBUTION.md.
"""Guardado local de memoria: lista de fuentes, huellas, copia, parches y punto confirmado.

La interpretación de cada cambio corresponde al agente; este módulo no infiere hechos.
"""
from rutas import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlparse, parse_qs


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()

def file_hash(path):
    path = Path(path)
    return hash_bytes(path.read_bytes()) if path.exists() else None

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)

def atomic_text(path, text, before_replace=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def madrid_time():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds')
    except (ImportError, KeyError):
        if os.name != 'nt':
            raise RuntimeError('Faltan las reglas Europe/Madrid; instala tzdata si el sistema no las incluye')
        return subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            "[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTimeOffset]::UtcNow,'Romance Standard Time').ToString('yyyy-MM-ddTHH:mm:sszzz')"],
            text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=10).strip()

class Memory:
    def __init__(self, config):
        self.config_path = Path(config).resolve()
        self.cfg = read_json(self.config_path)
        if self.cfg['timezone'] != 'Europe/Madrid':
            raise ValueError('Zona no admitida en este piloto')
        self.vaults = [Path(p).resolve() for p in self.cfg['vaults']]
        self.exact = {str(Path(p).resolve()) for p in self.cfg['files']}
        self.folders = [Path(p).resolve() for p in self.cfg['folders']]
        self.state = Path(self.cfg['state']).resolve()
        self.history = Path(self.cfg['history']).resolve()
        self.backups = Path(self.cfg['backups']).resolve()
        for path in [self.state, self.history, self.backups]:
            if any(path.is_relative_to(v) for v in self.vaults):
                raise ValueError('Estado, historial y copias deben quedar fuera de las bóvedas')

    def allowed(self, path):
        path = Path(path).resolve()
        if path.suffix != '.md' or any(p in self.cfg['forbidden'] for p in path.parts):
            return False
        if not any(path.is_relative_to(v) for v in self.vaults):
            return False
        return str(path) in self.exact or any(path.is_relative_to(f) for f in self.folders)

    def snapshot(self):
        paths = set(self.exact)
        errors = []
        for folder in self.folders:
            if folder.exists():
                paths.update(str(p.resolve()) for p in folder.rglob('*.md') if self.allowed(p))
        result = {}
        for name in sorted(paths):
            path = Path(name)
            if not self.allowed(path):
                errors.append({'path':name,'error':'Fuente fuera del alcance permitido'})
                continue
            try:
                st1 = path.stat()
                data = path.read_bytes()
                st2 = path.stat()
                data.decode('utf-8-sig')
                if (st1.st_mtime_ns,st1.st_size) != (st2.st_mtime_ns,st2.st_size):
                    raise RuntimeError('La fuente cambió durante la lectura')
                result[name] = hash_bytes(data)
            except Exception as e:
                errors.append({'path':name,'error':str(e)})
        return result, errors

    def scan(self):
        state_sha = file_hash(self.state)
        previous = read_json(self.state) if self.state.exists() else {}
        now, errors = self.snapshot()
        old = previous.get('files',{})
        changed = sorted(path for path in now if now[path] != old.get(path))
        removed = sorted(set(old)-set(now))
        return {'version':1,'id':uuid.uuid4().hex,'at':madrid_time(),
                'config_sha':file_hash(self.config_path),'state_sha':state_sha,
                'files':now,'changed':changed,'removed':removed,'errors':errors}

    def verify_links(self, path, text, planned=()):
        text = re.sub(r'```[\s\S]*?```|`[^`\n]*`','',text)
        vault = next(v for v in self.vaults if Path(path).is_relative_to(v))
        planned = {str(Path(p).resolve()) for p in planned}
        files = [Path(p) for p in self.exact if Path(p).exists() and Path(p).is_relative_to(vault)]
        files += [p for folder in self.folders for p in folder.rglob('*.md') if self.allowed(p) and p.is_relative_to(vault)]
        files += [Path(p) for p in planned if Path(p).is_relative_to(vault)]
        for match in re.finditer(r'\[\[([^\]\n]+)\]\]',text):
            target = match.group(1).split('|')[0].split('#')[0]
            if not target:
                continue
            relative = vault / target
            candidates = [relative, relative.with_name(relative.name+'.md'), relative.with_name(relative.name+'.base')]
            if not any(p.is_file() or str(p.resolve()) in planned for p in candidates) and not any(p.stem == target or p.name == target for p in files):
                raise RuntimeError('Enlace interno sin destino: ' + target + ' en ' + str(path))
        for raw in re.findall(r'obsidian://open\?[^\s)>]+',text):
            params = parse_qs(urlparse(raw).query)
            name = params.get('vault',[''])[0]
            rel = params.get('file',[''])[0]
            matches = [v for v in self.vaults if v.name == name]
            if not matches or not rel or not ((matches[0]/rel).is_file() or str((matches[0]/rel).resolve()) in planned):
                raise RuntimeError('URI sin destino comprobable: ' + raw)

    def log(self, record):
        path = self.history / (record['id'] + '.json')
        atomic_json(path, record)
        return str(path)

    def apply(self, scan, plan):
        run = {'id':uuid.uuid4().hex,'at':madrid_time(),'scan':scan['id'],
               'status':'failed','reviewed':plan.get('reviewed',{}),
               'limits':plan.get('limits',[]),'summary':plan.get('summary',''), 'written':[]}
        lock = self.state.with_suffix('.lock')
        lock.parent.mkdir(parents=True,exist_ok=True)
        fd = None
        try:
            fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd,str(os.getpid()).encode())
            if scan['errors'] or plan.get('errors'):
                raise RuntimeError('Hay fuentes inaccesibles o errores sin resolver: ' + str(scan['errors'] or plan['errors']))
            if scan['config_sha'] != file_hash(self.config_path) or scan['state_sha'] != file_hash(self.state):
                raise RuntimeError('La configuración o el punto de revisión cambiaron; volver a leer')
            current, errors = self.snapshot()
            if errors or current != scan['files']:
                raise RuntimeError('Una fuente cambió desde la lectura; preservar edición manual y volver a leer')
            reviews = plan.get('reviewed',{})
            required = set(scan['changed']+scan['removed'])
            if not required.issubset(reviews):
                raise RuntimeError('Falta clasificar fuentes cambiadas: ' + str(sorted(required-set(reviews))))
            allowed_review = {'leida','indice','propia','retirada-confirmada'}
            if any(not isinstance(reviews[p],dict) or reviews[p].get('status') not in allowed_review or
                   not reviews[p].get('note') for p in required):
                raise RuntimeError('Cada novedad necesita estado y motivo de revisión; no avanzar sin lectura')
            previous = read_json(self.state) if self.state.exists() else {}
            applied = dict(previous.get('applied',{}))
            pending = {}
            before = {}
            identities = {}
            for op in plan.get('operations',[]):
                path = Path(op['path']).resolve()
                name = str(path)
                if not self.allowed(path):
                    raise RuntimeError('Destino fuera del alcance autorizado: '+name)
                ident = op['id']
                if not re.fullmatch(r'[a-zA-Z0-9_.:-]{4,150}',ident):
                    raise ValueError('Identificador inválido')
                fingerprint = hash_bytes(json.dumps(op,sort_keys=True,ensure_ascii=False).encode())
                if ident in applied:
                    if applied[ident] != fingerprint:
                        raise RuntimeError('Identificador reutilizado con contenido distinto: '+ident)
                    continue
                if ident in identities:
                    raise RuntimeError('Identificador duplicado en el plan: '+ident)
                identities[ident] = fingerprint
                if name not in before:
                    before[name] = path.read_bytes() if path.exists() else None
                    if file_hash(path) != scan['files'].get(name):
                        raise RuntimeError('El destino cambió desde la lectura: '+name)
                    pending[name] = (before[name] or b'').decode('utf-8-sig')
                marker = '<!-- memoria:' + ident + ' -->'
                if marker in pending[name]:
                    applied[ident] = fingerprint
                    continue
                if op.get('mode','append') == 'replace':
                    old = op['old']
                    if pending[name].count(old) != 1:
                        raise RuntimeError('El parche de corrección no coincide una sola vez: '+name)
                    pending[name] = pending[name].replace(old,op['text'],1).rstrip()+'\n\n'+marker+'\n'
                else:
                    if not pending[name] and path.parent == Path(self.cfg['central'])/'Notas diarias':
                        if path.stem != run['at'][:10]:
                            raise ValueError('Solo crear el diario de hoy en Madrid')
                        pending[name] = '---\ntipo: diario\nareas: [personal]\nestado: abierto\ncreado: '+path.stem+'\nverificado:\n---\n\n# '+path.stem+'\n\n## Mi registro\n'
                    if not pending[name]:
                        pending[name] = op['text'].rstrip()+'\n\n'+marker+'\n'
                    else:
                        pending[name] = pending[name].rstrip()+'\n\n'+marker+'\n'+op['text'].rstrip()+'\n'
                applied[ident] = fingerprint
            writes={p:t.encode('utf-8') for p,t in pending.items() if t.encode('utf-8') != before[p]}
            for p in writes:
                self.verify_links(p,pending[p],planned=writes)
            # Prevalidar todos los destinos antes de la primera escritura.
            backup_dir=self.backups/run['id']
            for name in writes:
                if before[name] is not None:
                    path=Path(name)
                    vault=next(v for v in self.vaults if path.is_relative_to(v))
                    dest=backup_dir/vault.name/(hash_bytes(name.encode())[:20]+path.suffix)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(before[name])
                    if file_hash(dest) != hash_bytes(before[name]):
                        raise RuntimeError('Copia no verificada: '+name)
                    run.setdefault('backups',[]).append({'path':name,'copy':str(dest),'sha256':file_hash(dest)})
            for name, data in writes.items():
                path=Path(name)
                if file_hash(path) != (hash_bytes(before[name]) if before[name] is not None else None):
                    raise RuntimeError('Edición concurrente antes de guardar: '+name)
                path.parent.mkdir(parents=True,exist_ok=True)
                tmp=path.with_name(path.name+'.'+run['id']+'.tmp')
                with tmp.open('xb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                if file_hash(path) != (hash_bytes(before[name]) if before[name] is not None else None):
                    raise RuntimeError('Edición concurrente durante el guardado: '+name)
                os.replace(tmp,path)
                if file_hash(path) != hash_bytes(data):
                    raise RuntimeError('Guardado no verificado: '+name)
                run['written'].append(name)
            expected=dict(scan['files'])
            expected.update({p:hash_bytes(b) for p,b in writes.items()})
            final, errors=self.snapshot()
            if errors or final != expected:
                raise RuntimeError('Una fuente cambió durante el guardado; punto no avanzado, revisar cambios y copias')
            checkpoint={'version':1,'last_success':run['at'],'timezone':'Europe/Madrid',
                        'files':final,'applied':applied,'last_run':run['id']}
            if file_hash(self.state) != scan['state_sha']:
                raise RuntimeError('Punto modificado por otra ejecución')
            # Registrar la revisión preparada antes de confirmar el punto.
            run['status']='saved' if writes else 'unchanged'
            run['source_count']=len(final)
            self.log(run)
            atomic_json(self.state,checkpoint)
            return run
        except Exception as e:
            run['status']='failed'
            run['error']=str(e)
            self.log(run)
            raise
        finally:
            if fd is not None:
                os.close(fd)
                lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sc=sub.add_parser('scan')
    sc.add_argument('--out',required=True)
    ap=sub.add_parser('apply')
    ap.add_argument('--scan',required=True)
    ap.add_argument('--plan',required=True)
    args=parser.parse_args()
    memory=Memory(args.config)
    if args.command=='scan':
        result=memory.scan()
        atomic_json(args.out,result)
        print(json.dumps({'scan':args.out,'at':result['at'],'changed':result['changed'],
                          'removed':result['removed'],'errors':result['errors']},ensure_ascii=False))
    else:
        result=memory.apply(read_json(args.scan),read_json(args.plan))
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except Exception as e:
        print(json.dumps({'status':'failed','error':str(e)},ensure_ascii=False))
        sys.exit(1)
