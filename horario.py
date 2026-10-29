"""Horario desde una única nota académica editable, sin copiar datos personales."""
import hashlib
import re
from urllib.parse import quote

DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

def load_schedule(degree):
    path = degree / '00 Dashboard/Horario de clase.md'
    result = {'days': DAYS, 'classes': [], 'issues': []}
    if not path.exists():
        return result
    if not path.resolve().is_relative_to(degree.resolve()):
        result['issues'].append('La fuente del horario está fuera de la bóveda del grado.')
        return result
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    result.update(sha=hashlib.sha256(raw).hexdigest(),
                  url='obsidian://open?vault='+quote(degree.name)+'&file='+quote(path.relative_to(degree).as_posix()))
    for key, label in [('group','Grupo'), ('period','Periodo'), ('checked','Contraste'), ('source','Fuente'), ('note','Nota')]:
        match = re.search(r'^'+label+r':\s*(.+)$', text, re.M)
        result[key] = match.group(1).strip() if match else ''
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if not cells or cells[0] == 'Día' or all(re.fullmatch(r'[: -]+', c) for c in cells):
            continue
        if (len(cells) != 6 or cells[0] not in DAYS or
                not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in cells[1:3]) or
                cells[1] >= cells[2] or not cells[3]):
            result['issues'].append('Hay una fila del horario que necesita revisión.')
            continue
        result['classes'].append(dict(zip(['day','start','end','subject','kind','room'], cells)))
    result['classes'].sort(key=lambda c: (DAYS.index(c['day']), c['start']))
    return result
