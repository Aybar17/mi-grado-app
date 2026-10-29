from pathlib import Path
import importlib.util
import tempfile
import unittest
import copy
import json
import shutil
import subprocess
import sys
from rutas import Path as FilePath

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('skill_bridge',ROOT/'skills/mi-grado-obsidian-ia/scripts/puente_obsidian.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.book={'kind':'mi-grado-notebook','version':1,'id':'book-demo01','subjects':[{'id':'subject-demo01','name':'Asignatura ficticia'}],'requests':[{'id':'session-demo01','subjectId':'subject-demo01','createdAt':'2026-10-14T10:00:00Z','goal':'Un caso'}]}
        self.result={'kind':'mi-grado-result','version':1,'notebookId':'book-demo01','subjectId':'subject-demo01','sessionId':'session-demo01','attempt':'Intenté con ayuda','help':'Una pista','result':'Caso guiado','nextStep':'Otro caso sin pistas'}

    def test_load_book_accepts_both_notebook_versions_and_rejects_future(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'cuaderno.json'
            for version in (1,2,3,4,5):
                book={**self.book,'version':version}
                path.write_text(bridge.json.dumps(book),encoding='utf-8')
                loaded=bridge.load_book(path)
                clean,request,subject=bridge.response(loaded,self.result)
                self.assertEqual(clean['sessionId'],self.result['sessionId'])
            path.write_text(bridge.json.dumps({**self.book,'version':6}),encoding='utf-8')
            with self.assertRaises(ValueError):bridge.load_book(path)

    def test_verified_idempotent_save_preserves_manual_edits(self):
        with tempfile.TemporaryDirectory() as td:
            vault=Path(td).resolve()
            result=bridge.save(self.book,self.result,vault)
            self.assertTrue(result['saved'] and result['noteVerified'] and result['journalLinked'])
            note=Path(result['note']);note.write_text(note.read_text(encoding='utf-8')+'\nMi edición manual\n',encoding='utf-8')
            diary=Path(result['diary']);diary.write_text(diary.read_text(encoding='utf-8')+'\nOtra tarea manual\n',encoding='utf-8')
            note_before,diary_before=note.read_bytes(),diary.read_bytes()
            repeated=bridge.save(self.book,self.result,vault)
            self.assertTrue(repeated['unchanged'])
            self.assertEqual(note.read_bytes(),note_before);self.assertEqual(diary.read_bytes(),diary_before)
            with self.assertRaisesRegex(ValueError,'otro contenido'):bridge.save(self.book,{**self.result,'attempt':'Cambio'},vault)
            self.assertEqual(note.read_bytes(),note_before)

    def test_wrong_identity_and_selected_paths_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault=Path(td).resolve()
            with self.assertRaises(ValueError):bridge.save(self.book,{**self.result,'notebookId':'book-otro01'},vault)
            with self.assertRaises(ValueError):bridge.within(vault,'../privada.md')
            with self.assertRaises(ValueError):bridge.within(vault,'.obsidian/config.md')
            self.assertEqual(list(vault.iterdir()),[])

    def test_partial_save_can_resume_diary_without_replacing_note(self):
        with tempfile.TemporaryDirectory() as td:
            vault=Path(td).resolve();clean,req,subject=bridge.response(self.book,self.result)
            scope,note,diary=bridge.layout(vault,self.book,req);note.parent.mkdir(parents=True)
            sha=bridge.digest(bridge.json.dumps(clean,ensure_ascii=False,sort_keys=True).encode('utf-8'))
            marker,content=bridge.render(clean,req,subject,sha);note.write_text(content,encoding='utf-8')
            before=note.read_bytes();result=bridge.save(self.book,self.result,vault)
            self.assertTrue(result['journalLinked']);self.assertEqual(before,note.read_bytes())

    def test_incomplete_note_never_claims_saved(self):
        with tempfile.TemporaryDirectory() as td:
            vault=Path(td).resolve();clean,req,subject=bridge.response(self.book,self.result)
            scope,note,diary=bridge.layout(vault,self.book,req);note.parent.mkdir(parents=True)
            sha=bridge.digest(bridge.json.dumps(clean,ensure_ascii=False,sort_keys=True).encode('utf-8'))
            marker,content=bridge.render(clean,req,subject,sha)
            note.write_text(marker+'\nGuardado interrumpido.',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'incompleto'):bridge.save(self.book,self.result,vault)
            self.assertFalse(diary.exists())

    def reference_book(self):
        book=copy.deepcopy(self.book);book['version']=5
        ref={'id':'reference-demo01','title':'Relación original','kind':'local-file','location':'Materiales/no-disponible.pdf','detail':'Página 2','archived':False}
        book['subjects'][0]['references']=[{**ref,'title':'Nombre cambiado después'}]
        book['requests'][0].update(referenceIds=[ref['id']],referenceSnapshot=[ref],minutes=40,exercise='Ejercicio 1',checkpoint='Repetir sin pistas')
        return book

    def test_historical_reference_is_saved_and_retries_cannot_replace_it(self):
        with tempfile.TemporaryDirectory() as td:
            book=self.reference_book();vault=Path(td).resolve()
            saved=bridge.save(book,self.result,vault);note=Path(saved['note']);before=note.read_bytes()
            self.assertIn('Relación original',before.decode());self.assertNotIn('Nombre cambiado después',before.decode())
            self.assertTrue(bridge.save(book,self.result,vault)['unchanged'])
            book['requests'][0]['referenceSnapshot'][0]['detail']='Otra página'
            with self.assertRaisesRegex(ValueError,'otro contenido'):bridge.save(book,self.result,vault)
            self.assertEqual(note.read_bytes(),before)

    def test_invalid_material_stops_before_any_vault_write(self):
        with tempfile.TemporaryDirectory() as td:
            book=self.reference_book();book['requests'][0]['referenceSnapshot'][0]['location']='../../privado.pdf'
            with self.assertRaises(ValueError):bridge.save(book,self.result,Path(td).resolve())
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_isolated_skill_cli_handles_deep_vault_context_and_verified_save(self):
        with tempfile.TemporaryDirectory(prefix='skill-autonoma-') as td:
            owned=FilePath(td).resolve();vault=owned/'Bóveda de prueba'
            while len(str(vault))<310:vault/='Carpeta con apuntes ficticios ñ'
            try:
                package=owned/'skill';shutil.copytree(ROOT/'skills/mi-grado-obsidian-ia',package)
                for name in ('rutas.py','validar_cuaderno.py'):
                    self.assertEqual((package/'scripts'/name).read_bytes(),(ROOT/name).read_bytes())
                script=package/'scripts/puente_obsidian.py';book=self.reference_book()
                (owned/'cuaderno.json').write_text(json.dumps(book),encoding='utf-8');(owned/'avance.json').write_text(json.dumps(self.result),encoding='utf-8')
                vault.mkdir(parents=True);(vault/'elegida.md').write_text('SOLO ESTA NOTA FICTICIA',encoding='utf-8')
                (vault/'no-elegida.md').write_text('SECRETO_FICTICIO_NO_COMPARTIR',encoding='utf-8')
                def run(*args):
                    return json.loads(subprocess.run([sys.executable,str(script),*args],cwd=owned,capture_output=True,text=True,encoding='utf-8',check=True).stdout)
                common=['--notebook',str(owned/'cuaderno.json'),'--vault',str(vault)]
                context=run('context',*common,'--session','session-demo01','--note','elegida.md','--out',str(owned/'contexto.md'))
                self.assertTrue(context['prepared']);body=(owned/'contexto.md').read_text(encoding='utf-8')
                for expected in ('SOLO ESTA NOTA FICTICIA','Relación original','Ejercicio 1','Repetir sin pistas','40'):
                    self.assertIn(expected,body)
                self.assertNotIn('SECRETO_FICTICIO_NO_COMPARTIR',body)
                self.assertNotIn('Nombre cambiado después',body)
                preview=run('preview',*common,'--result',str(owned/'avance.json'))
                self.assertFalse(preview['writes']);self.assertFalse((vault/'Mi grado').exists())
                saved=run('save',*common,'--result',str(owned/'avance.json'),'--confirm')
                self.assertTrue(saved['saved'] and saved['noteVerified'] and saved['journalLinked'])
                self.assertIn('Relación original',FilePath(saved['note']).read_text(encoding='utf-8'))
                self.assertTrue(run('save',*common,'--result',str(owned/'avance.json'),'--confirm')['unchanged'])
            finally:
                self.assertEqual(owned,FilePath(td).resolve());shutil.rmtree(owned)


if __name__=='__main__':unittest.main()
