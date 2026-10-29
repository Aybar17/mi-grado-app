/* El mismo editor de referencias para web y programa local. No lee los archivos enlazados. */
(function(root){'use strict';
  const kinds={'web':'Enlace web','local-file':'Archivo de mis apuntes','description':'Descripción del material'};
  function mount(container,options){
    const web=options.mode==='web';
    const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
    const layout=make('div');layout.className='reference-layout';const editor=make('article'),list=make('div');editor.className='card';list.className='reference-list';
    editor.append(make('h2','Materiales y enunciados'),make('p',web?'Opcional: apunta qué PDF, enlace o ejercicio vas a utilizar. Para incorporar el texto de tus apuntes, importa un tema Markdown en Mis notas.':'Guarda una referencia y el apartado que necesitas. Los archivos nuevos se buscan dentro de la bóveda configurada en Mi grado.'));
    editor.append(make('p','Guardar una referencia no importa el archivo ni lo adjunta a tu IA. Aporta el enunciado o PDF a tu chat cuando lo necesites.'));
    const form=make('form'),inputs={},locationTitle=make('span');
    for(const [name,title,tag,max] of [['subject','Asignatura del material','select'],['title','Título del material','input',160],['kind','Tipo de material','select'],['location','Enlace o ruta relativa del archivo','input',2000],['link','Enlace adicional del material, opcional','input',2000],['detail','Ejercicio, sección o indicaciones','textarea',2000]]){
      const label=make('label',name==='location'?undefined:title),input=make(tag);input.name=name;if(max)input.maxLength=max;if(tag==='textarea')input.rows=3;if(name==='title')input.required=true;if(name==='location')label.append(locationTitle);label.append(input);form.append(label);inputs[name]=input;
    }
    const locationHelp=make('p');locationHelp.className='muted';locationHelp.id='material-help-'+crypto.randomUUID();inputs.location.setAttribute('aria-describedby',locationHelp.id);inputs.location.parentElement.after(locationHelp);
    for(const [value,title] of Object.entries(kinds)){const option=make('option',title);option.value=value;inputs.kind.append(option);}
    const save=make('button','Guardar referencia');save.type='submit';const fresh=make('button','Nueva referencia');fresh.type='button';fresh.className='secondary';
    const actions=make('div');actions.className='actions';actions.append(save,fresh);form.append(actions);const status=make('p');status.setAttribute('role','status');editor.append(form,status);layout.append(editor,list);container.append(layout);
    let state=null,editing=null,expected=null,dirty=false,busy=false;
    function type(){
      const kind=inputs.kind.value,description=kind==='description';inputs.location.disabled=description||busy;inputs.location.required=!description;inputs.location.parentElement.hidden=description;locationHelp.hidden=description;
      locationTitle.textContent=kind==='web'?'Enlace al material':web?'Nombre del archivo o carpeta (solo referencia)':'Ruta desde la carpeta de tu bóveda';
      inputs.location.placeholder=kind==='web'?'https://campus.example/material':web?'tema-1.pdf o Materiales/tema-1.pdf':'Materiales/tema-1.pdf';
      locationHelp.textContent=kind==='web'?'Pega la dirección de la página o del documento. Comprueba en tu chat si la IA puede abrirlo.':web?'Puedes escribir solo tema-1.pdf. Si lo organizas en Obsidian: Mis apuntes → Materiales → tema-1.pdf se anota como Materiales/tema-1.pdf. La web no busca ese archivo en tu ordenador.':'Empieza dentro de la bóveda que elegiste. Ejemplo: Mis apuntes → Materiales → tema-1.pdf se escribe Materiales/tema-1.pdf. No incluyas C:\\ ni el nombre de la bóveda.';
    }
    function reset(){editing=null;dirty=false;expected=state?.version;for(const field of ['title','location','detail','link'])inputs[field].value='';inputs.kind.value='web';type();save.textContent='Guardar referencia';status.textContent='';}
    function notify(value,error=false){status.textContent=value;options.notify?.(value,error);}
    function paintList(){
      list.replaceChildren();const refs=state?.bySubject[inputs.subject.value]||[];
      list.append(make('h2','Referencias de esta asignatura'));
      if(!refs.length)list.append(make('p','Todavía no has añadido referencias a esta asignatura.'));
      for(const ref of refs){const card=make('article');card.className='card';card.append(make('h3',ref.title),make('p',kinds[ref.kind]+(ref.archived?' · archivada':'')),make('p',ref.location||ref.detail||'Sin ubicación adicional.'));if(ref.link)card.append(make('p',ref.link));if(ref.detail&&ref.location)card.append(make('p',ref.detail));
        const edit=make('button','Editar referencia');edit.type='button';edit.className='secondary';edit.addEventListener('click',()=>{if(busy)return;editing=ref;expected=state.version;dirty=true;for(const key of ['title','kind','location','detail','link'])inputs[key].value=ref[key]||'';save.textContent='Guardar cambios del material';type();inputs.title.focus();});
        const toggle=make('button',ref.archived?'Reactivar referencia':'Archivar referencia');toggle.type='button';toggle.className='secondary';toggle.addEventListener('click',async()=>{if(busy)return;toggle.disabled=true;try{await options.onSave(inputs.subject.value,{...ref,archived:!ref.archived},state.version);notify(ref.archived?'Referencia reactivada.':'Referencia archivada; sus sesiones anteriores se conservan.');}catch(error){notify(error.message,true);}finally{toggle.disabled=false;}});
        const buttons=make('div');buttons.className='actions';buttons.append(edit,toggle);card.append(buttons);list.append(card);
      }
    }
    form.addEventListener('input',()=>{if(!dirty){expected=state.version;dirty=true;}type();});inputs.kind.addEventListener('change',type);
    inputs.subject.addEventListener('change',()=>{reset();paintList();});fresh.addEventListener('click',reset);
    form.addEventListener('submit',async event=>{event.preventDefault();if(busy||!state)return;const subject=inputs.subject.value;if(!subject){notify('Añade una asignatura activa antes de guardar material.',true);return;}
      const value={id:editing?.id||'reference-'+crypto.randomUUID(),title:inputs.title.value,kind:inputs.kind.value,location:inputs.location.value,link:inputs.link.value,detail:inputs.detail.value,archived:editing?.archived||false};
      if(value.kind==='local-file'&&/^(?:[a-z]:|[\\/]|file:)/i.test(value.location.trim())){notify(web?'Aquí guarda solo el nombre, por ejemplo tema-1.pdf, o Materiales/tema-1.pdf dentro de tu bóveda. La web no abre rutas como C:\\…; para traer los apuntes usa Importar un tema Markdown.':'Escribe la ruta desde dentro de tu bóveda: Materiales/tema-1.pdf. No incluyas C:\\ ni la carpeta anterior a la bóveda.',true);inputs.location.focus();return;}
      busy=true;for(const input of form.elements)input.disabled=true;
      try{await options.onSave(subject,value,dirty?expected:state.version);reset();notify('Referencia guardada. Elige este material al preparar la sesión.');}
      catch(error){notify(error.message,true);}finally{busy=false;for(const input of form.elements)input.disabled=false;type();}
    });
    function render(next){state=next;const selected=inputs.subject.value,active=state.subjects.filter(s=>!s.archived);inputs.subject.replaceChildren();for(const subject of active){const option=make('option',subject.name);option.value=subject.id;inputs.subject.append(option);}if(active.some(s=>s.id===selected))inputs.subject.value=selected;if(!dirty)expected=state.version;paintList();save.disabled=!active.length||busy;}
    type();return {render};
  }
  root.StudyReferences={mount};
})(typeof window==='undefined'?globalThis:window);
