"""Rutas lógicas normales; E/S Windows extendida sin cambiar el registro del sistema."""
import os
import sys
from pathlib import Path as _Path

SEP=chr(92)
PREFIX=SEP*2+'?'+SEP


def logical(value):
    if value.startswith(PREFIX+'UNC'+SEP):return SEP*2+value[len(PREFIX+'UNC'+SEP):]
    return value[len(PREFIX):] if value.startswith(PREFIX) else value


if os.name=='nt':
    import ntpath

    class Path(type(_Path())):
        def __new__(cls,*parts):
            return super().__new__(cls,*(logical(str(p)) if isinstance(p,_Path) else logical(os.fsdecode(p)) for p in parts))

        def __init__(self,*parts):
            # Desde Python 3.12 PurePath guarda los segmentos en __init__.
            # Normalizar solo en __new__ deja escapar el prefijo a JSON e IDs.
            if sys.version_info >= (3,12):
                super().__init__(*(logical(str(p)) if isinstance(p,_Path) else logical(os.fsdecode(p)) for p in parts))

        def __fspath__(self):
            value=ntpath.abspath(str(self))
            if value.startswith(PREFIX):return value
            return PREFIX+'UNC'+SEP+value[2:] if value.startswith(SEP*2) else PREFIX+value

        def resolve(self,strict=False):
            return type(self)(logical(str(super().resolve(strict=strict))))

        def absolute(self):
            return type(self)(ntpath.abspath(str(self)))
else:
    Path=_Path
