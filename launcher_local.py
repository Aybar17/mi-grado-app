"""Lanzador local independiente; no configura el inicio de Windows."""
from rutas import Path
import argparse, hashlib, json, os, subprocess, sys, time, webbrowser
from urllib.request import urlopen
from configuracion import ROOT, add_options, load_config

def main():
    parser=add_options(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--port',type=int,default=None)
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args();config=load_config(args.config,args.demo)
    args.port=args.port if args.port is not None else (8770 if args.demo else 8769)
    if not 1<=args.port<=65535:parser.error('El puerto debe estar entre 1 y 65535.')
    url=f'http://127.0.0.1:{args.port}'
    expected=hashlib.sha256(str(config['path']).encode()).hexdigest()[:16]
    def health():
        try:
            with urlopen(url+'/api/health',timeout=1) as r:result=json.load(r)
            return result.get('service')=='mi-grado-memoria' and result.get('instance')==expected
        except (OSError,ValueError):return False
    if not health():
        if os.name=='nt' and not args.worker:
            pythonw=Path(sys.executable).with_name('pythonw.exe')
            command=subprocess.list2cmdline([str(pythonw),str(ROOT/'launcher_local.py'),'--config',str(config['path']),'--port',str(args.port),'--no-open','--worker'])
            literal="'"+command.replace("'","''")+"'"
            script='$taskPanelCreate=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='+literal+'};if($taskPanelCreate.ReturnValue -ne 0){throw "No se pudo iniciar el panel"}'
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],check=True,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            config['runtime'].mkdir(parents=True,exist_ok=True)
            with (config['runtime']/'puente-salida.log').open('a',encoding='utf-8') as out,(config['runtime']/'puente-errores.log').open('a',encoding='utf-8') as err:
                subprocess.Popen([sys.executable,str(ROOT/'puente_memoria.py'),'--config',str(config['path']),'--port',str(args.port)],stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
        for _ in range(40):
            if health():break
            time.sleep(.2)
        else:raise RuntimeError('No se pudo abrir el panel. Comprueba el puerto y el registro local de errores.')
    if not args.no_open:webbrowser.open(url+'/panel.html')

if __name__=='__main__':main()
