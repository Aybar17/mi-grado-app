"""E/S en carpetas profundas sin cambiar rutas públicas ni ajustes de Windows."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path as StandardPath

from rutas import Path, PREFIX


class PathTests(unittest.TestCase):
    def test_logical_identity_survives_filesystem_roundtrip(self):
        path = Path('carpeta ficticia')/'..'/'otra carpeta'
        resolved = path.resolve()
        self.assertEqual(str(Path(os.fspath(resolved))), str(resolved))
        self.assertFalse(str(resolved).startswith(PREFIX))
        self.assertEqual(resolved, Path(StandardPath(str(resolved))))
        self.assertEqual(resolved.parent/path.name, resolved)

    @unittest.skipUnless(os.name == 'nt', 'Protocolo extendido de Windows')
    def test_extended_unc_keeps_normal_identity(self):
        value = r'\\servidor-ficticio\carpeta\archivo.md'
        path = Path(PREFIX+'UNC\\'+value[2:])
        self.assertEqual(str(path), value)
        self.assertEqual(os.fspath(path), PREFIX+'UNC\\'+value[2:])

    def test_deep_unicode_file_can_be_written_replaced_and_discovered(self):
        with tempfile.TemporaryDirectory(prefix='ruta-ficticia-') as temporary:
            root = Path(temporary).resolve()
            deep = root
            while len(str(deep)) < 310:
                deep /= 'Carpeta de prueba con apuntes áéñ'
            try:
                deep.mkdir(parents=True)
                draft = deep/'borrador.md'
                draft.write_text('Intento ficticio 🧪\n', encoding='utf-8')
                saved = draft.replace(deep/'guardado.md')
                self.assertEqual(saved.read_text(encoding='utf-8'), 'Intento ficticio 🧪\n')
                self.assertIn(saved, list(root.rglob('*.md')))
                self.assertEqual(saved.resolve(strict=True), saved)
                self.assertTrue(saved.is_relative_to(root))
            finally:
                # Solo el directorio temporal creado por esta prueba.
                self.assertEqual(str(root), str(Path(temporary).resolve()))
                shutil.rmtree(root)


if __name__ == '__main__': unittest.main()
