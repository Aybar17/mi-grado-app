"""Arranque con doble clic, asistente inicial y servicio con cierre explícito."""
from rutas import Path
import argparse
import hashlib
import json
import os
import sys
import threading
import webbrowser
from urllib.request import build_opener, ProxyHandler

from configuracion import ROOT, load_config
from perfiles import default_profile, create_profile, add_subject
from puente_memoria import create_server


def profile_port(config):
    return 20000 + int(hashlib.sha256(str(config['path']).encode()).hexdigest()[:8], 16) % 10000


def already_running(config, port):
    try:
        with build_opener(ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            value = json.load(response)
        expected = hashlib.sha256(str(config['path']).encode()).hexdigest()[:16]
        return value.get('service') == 'mi-grado-memoria' and value.get('instance') == expected
    except (OSError, ValueError):
        return False


def style_window(root):
    import tkinter as tk
    from tkinter import ttk
    root.configure(background='#f6f5f0')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background='#f6f5f0', foreground='#20352d')
    style.configure('TEntry', fieldbackground='#fffefa', padding=6)
    style.configure('TCombobox', fieldbackground='#fffefa', padding=6)
    style.configure('TButton', background='#fffefa', foreground='#173e33', padding=(12, 8))
    style.map('TButton', background=[('active', '#eaf0e7')])
    style.configure('Action.TButton', background='#173e33', foreground='#fffefa', padding=(12, 10))
    style.map('Action.TButton', background=[('active', '#244f40')])
    logo = ROOT / 'assets' / 'mi-grado.png'
    if logo.exists():
        root._brand_image = tk.PhotoImage(file=str(logo))
        root.iconphoto(True, root._brand_image)
    if os.name == 'nt' and (ROOT / 'assets' / 'mi-grado.ico').exists():
        root.iconbitmap(default=str(ROOT / 'assets' / 'mi-grado.ico'))


def wizard(root, destination):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root.title('Mi grado · Crea tu espacio')
    height = min(750, root.winfo_screenheight() - 100)
    root.geometry(f'720x{height}')
    root.minsize(650, min(640, height))
    footer = ttk.Frame(root, padding=(24, 12))
    footer.pack(side='bottom', fill='x')
    outer = ttk.Frame(root); outer.pack(fill='both', expand=True)
    canvas = tk.Canvas(outer, background='#f6f5f0', highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    frame = ttk.Frame(canvas, padding=24)
    frame_id = canvas.create_window((0, 0), window=frame, anchor='nw')
    frame.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(frame_id, width=event.width))
    root.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units'))
    ttk.Label(frame, text='Prepara tu cuaderno', font=('Georgia', 23)).pack(anchor='w')
    ttk.Label(frame, text='Elige tus apuntes y asignaturas. El campus y el chat se configuran después en Conexiones.', wraplength=650).pack(anchor='w', pady=(6, 18))
    values = {key: tk.StringVar(value=value) for key, value in {
        'label': 'Mi cuaderno',
        'degree': str(Path.home() / 'Documents' / 'Mi grado' / 'Apuntes'),
        'center': 'Otro centro', 'campus': ''}.items()}
    for label, key in [('Nombre de tu espacio', 'label'), ('Carpeta de apuntes (bóveda Obsidian)', 'degree')]:
        ttk.Label(frame, text=label).pack(anchor='w', pady=(8, 2))
        row = ttk.Frame(frame); row.pack(fill='x')
        ttk.Entry(row, textvariable=values[key]).pack(side='left', fill='x', expand=True)
        if key == 'degree':
            def select_folder():
                folder = filedialog.askdirectory(parent=root, title='Elige tu carpeta de apuntes')
                if folder: values['degree'].set(folder)
            ttk.Button(row, text='Elegir carpeta…', command=select_folder).pack(side='right', padx=(8, 0))
    ttk.Label(frame, text='Centro de estudios').pack(anchor='w', pady=(12, 2))
    ttk.Combobox(frame, textvariable=values['center'], state='readonly',
                 values=['UGR', 'Otra universidad', 'FP', 'Otro centro']).pack(fill='x')
    ttk.Label(frame, text='Dirección de tu campus (opcional)').pack(anchor='w', pady=(12, 2))
    ttk.Entry(frame, textvariable=values['campus']).pack(fill='x')
    values['center'].trace_add('write', lambda *_: values['campus'].set('https://pradogrado.ugr.es/')
                               if values['center'].get() == 'UGR' and not values['campus'].get() else None)
    ttk.Label(frame, text='Asignaturas: escribe una por línea o elige fichas existentes', wraplength=650).pack(anchor='w', pady=(12, 4))
    names = tk.Text(frame, height=4, font=('Segoe UI', 11), background='#fffefa', foreground='#20352d', relief='flat', highlightthickness=1, highlightbackground='#cbd6c9', highlightcolor='#173e33', padx=10, pady=6); names.pack(fill='x')
    selected = []
    selected_status = tk.StringVar(value='Ninguna ficha seleccionada. Se crean solo las asignaturas que escribas.')
    def choose_notes():
        files = filedialog.askopenfilenames(parent=root, title='Fichas dentro de la carpeta de apuntes',
                    initialdir=values['degree'].get(), filetypes=[('Notas Markdown', '*.md')])
        if files:
            selected[:] = files
            selected_status.set(f'{len(selected)} fichas elegidas; su contenido se conserva.')
    ttk.Button(frame, text='Elegir mis fichas Markdown…', command=choose_notes).pack(anchor='w', pady=8)
    ttk.Label(frame, textvariable=selected_status, wraplength=650).pack(anchor='w')
    ttk.Label(frame, text='Se crea un seguimiento separado para el diario. El campus se abre en tu navegador; '
              'sus datos se importan de forma explícita. La IA web se usa copiando el contexto.', wraplength=650).pack(anchor='w', pady=14)
    result = []
    def finish():
        try:
            config = create_profile(destination, values['degree'].get(), names.get('1.0', 'end').splitlines(),
                       label=values['label'].get(), center=values['center'].get(),
                       campus=values['campus'].get(), existing_notes=selected)
        except Exception as error:
            messagebox.showerror('Revisa tu configuración', str(error), parent=root)
            return
        result.append(config)
        root.unbind('<MouseWheel>')
        footer.destroy(); outer.destroy()
        root.quit()
    ttk.Button(footer, text='Crear cuaderno y abrir Mi grado', style='Action.TButton', command=finish).pack(anchor='e')
    root.protocol('WM_DELETE_WINDOW', lambda: (root.quit(), root.destroy()))
    root.mainloop()
    return result[0] if result else None


def run_gui(args):
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog, filedialog
    root = tk.Tk()
    style_window(root)
    try:
        selected = args.config or (ROOT / 'config.local.json' if not getattr(sys, 'frozen', False)
                                   and (ROOT / 'config.local.json').exists() else default_profile())
        if args.demo:
            config = load_config(demo=True)
        elif Path(selected).exists():
            config = load_config(selected)
        else:
            config = wizard(root, selected)
            if config is None: return
        port = args.port if args.port is not None else profile_port(config)
        if already_running(config, port):
            if not args.no_browser: webbrowser.open(f'http://127.0.0.1:{port}/panel.html')
            root.destroy()
            return
        server = create_server(config, port)
    except Exception as error:
        messagebox.showerror('No se pudo abrir Mi grado', str(error), parent=root)
        root.destroy()
        return
    url = f'http://127.0.0.1:{server.server_port}/panel.html'
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    root.title('Mi grado'); root.geometry('560x450'); root.minsize(520, 440)
    frame = ttk.Frame(root, padding=24); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text=config.get('profile_label', 'Mi grado'), font=('Georgia', 22)).pack(anchor='w')
    ttk.Label(frame, text='Mi grado está en marcha. Mantén esta ventana abierta mientras estudias en el navegador.', wraplength=500).pack(anchor='w', pady=12)
    ttk.Button(frame, text='Abrir cuaderno de estudio', style='Action.TButton', command=lambda: webbrowser.open(url)).pack(fill='x', pady=4)
    def add():
        name = simpledialog.askstring('Nueva asignatura', 'Nombre de la asignatura:', parent=root)
        if not name: return
        note = None
        if messagebox.askyesno('Ficha', '¿Quieres elegir una ficha existente? Si no, se crea una ficha vacía.', parent=root):
            note = filedialog.askopenfilename(parent=root, initialdir=str(config['vaults']['degree']), filetypes=[('Markdown', '*.md')])
            if not note: return
        try:
            with server.app.lock:
                add_subject(config, name, note)
                server.app.state()
            messagebox.showinfo('Asignatura añadida', 'La ficha se conserva. El panel incorporará la asignatura en unos segundos.', parent=root)
        except Exception as error:
            messagebox.showerror('No se pudo añadir', str(error), parent=root)
    ttk.Button(frame, text='Añadir una asignatura…', command=add).pack(fill='x', pady=4)
    ttk.Button(frame, text='Configurar campus y chat', command=lambda: webbrowser.open(url + '#conexiones')).pack(fill='x', pady=4)
    def open_other():
        selected = filedialog.askopenfilename(parent=root, initialdir=str(default_profile().parent.parent),
                                             title='Elegir el config.json de otro cuaderno', filetypes=[('Configuración de cuaderno', '*.json')])
        if not selected: return
        try:
            from configuracion import read_panel, subject_source
            other = load_config(Path(selected))
            for subject in read_panel(other)['subjects']: subject_source(other, subject)
            import subprocess
            command = [sys.executable] + ([] if getattr(sys, 'frozen', False) else [str(ROOT/'escritorio.py')]) + ['--config', str(other['path'])]
            subprocess.Popen(command, cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as error:
            messagebox.showerror('No se pudo abrir el cuaderno', str(error), parent=root)
    ttk.Button(frame, text='Abrir otro cuaderno…', command=open_other).pack(fill='x', pady=4)
    def close():
        server.shutdown(); server.server_close(); root.destroy()
    ttk.Button(frame, text='Cerrar Mi grado', command=close).pack(fill='x', pady=4)
    root.protocol('WM_DELETE_WINDOW', close)
    if not args.no_browser: webbrowser.open(url)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--headless', action='store_true', help='Verificación sin ventana')
    parser.add_argument('--ready-file', type=Path, help='Estado de arranque para una prueba aislada')
    args = parser.parse_args()
    if args.port is not None and not 0 <= args.port <= 65535: parser.error('Puerto no válido')
    if args.headless:
        config = load_config(args.config, args.demo)
        with create_server(config, args.port if args.port is not None else profile_port(config)) as server:
            if args.ready_file:
                args.ready_file.write_text(json.dumps({'pid': os.getpid(), 'url': f'http://127.0.0.1:{server.server_port}',
                                                       'demo': server.app.config['demo']}), encoding='utf-8')
            server.serve_forever()
    else:
        run_gui(args)


if __name__ == '__main__':
    main()
