/* Revisión local del regreso desde la web. El contenido recibido siempre se presenta como texto. */
document.addEventListener('DOMContentLoaded',()=>{
  'use strict';
  const pane=document.querySelector('[data-notebook-pane="backup"] .notebook-layout');if(!pane)return;
  const make=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  const card=make('article',undefined,'card');card.append(make('div','Revisar antes de incorporar','eyebrow'),make('h2','Traer cambios desde la web'),make('p','Selecciona la copia JSON que descargaste después de estudiar. Compararemos la salida original, tu cuaderno local actual y lo que vuelve de la web.'));
  const label=make('label','Cuaderno JSON que vuelve de la web'),input=make('input');input.type='file';input.accept='.json,application/json';label.append(input);
  const status=make('p',undefined,'statusline');status.setAttribute('role','status');
  const reopen=make('button','Volver a la revisión','btn');reopen.type='button';reopen.hidden=true;
  card.append(label,status,reopen,make('p','Los conflictos necesitan una elección. Las notas se guardan con copia anterior y los avances con su diario verificado. No se cambian tus cuentas ni se activa sincronización.','muted'));pane.append(card);
  const dialog=make('dialog',undefined,'roundtrip-dialog');dialog.setAttribute('aria-labelledby','roundtripTitle');
  const heading=make('h2','Cambios que vuelven de la web');heading.id='roundtripTitle';
  const close=make('button','Cerrar revisión','btn');close.type='button';const header=make('div',undefined,'roundtrip-heading');header.append(heading,close);
  const intro=make('p'),warnings=make('ul'),form=make('form'),changes=make('div');
  const keep=make('button','Conservar mi versión local en todos los conflictos','btn');keep.type='button';
  const confirm=make('button','Incorporar los cambios elegidos','btn primary');confirm.type='submit';
  const actions=make('div',undefined,'roundtrip-actions');actions.append(confirm);form.append(keep,changes,actions);dialog.append(header,intro,warnings,form);document.body.append(dialog);
  let review=null,busy=false,started=false;const selections=new Map();
  async function post(route,value){const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});const result=await response.json();if(!response.ok)throw Error(result.error||'No se confirmó la operación.');return result;}
  function readable(value,kind){
    if(value===null)return 'No existe en esta versión.';
    if(typeof value==='string')return value;
    if(typeof value==='boolean')return value?'Archivada':'Activa';
    const names=review.subjectNames||{},duration=minutes=>minutes?`${minutes} minutos`:'Duración por indicar';
    if(kind==='note')return value.content+'\n\n'+(Array.isArray(value.topics)?'Temas: '+value.topics.map(t=>t.title+(t.archived?' (archivado)':'')).join(', '):
      'Tema: '+value.title+(value.archived?' (archivado)':'')+(value.filename?'\nArchivo: '+value.filename:''));
    const task=t=>[t.title,'Asignatura: '+(names[t.subject||t.subjectId]||'Por revisar'),'Fecha: '+(t.date||t.day||'Sin fecha'),duration(t.minutes),
      'Estado: '+(t.status||(t.archived?'archivada':t.done?'realizada':'pendiente')),t.detail||''].filter(Boolean).join('\n');
    if(kind==='task')return task(value);
    if(kind==='reference')return [value.title,value.kind==='web'?'Enlace web':value.kind==='local-file'?'Archivo referenciado':'Descripción',value.location,value.link,value.detail,value.archived?'Archivada':'Activa'].filter(Boolean).join('\n');
    if(kind==='legacy')return value.length?value.map(task).join('\n\n'):'Sin tareas.';
    if(kind==='schedule')return value.length?value.map(c=>[names[c.subjectId]||'Asignatura por revisar',['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'][c.day-1],c.start+'–'+c.end,c.kind,c.room].filter(Boolean).join(' · ')).join('\n'):'Sin clases.';
    const labels=kind==='session'?{attempt:'Lo que intenté',help:'Ayuda recibida',result:'Resultado observado',nextStep:'Próximo paso'}:
      {name:'Asignatura',archived:'Estado',checkpoint:'Punto de reanudación',nextPractice:'Próxima práctica'};
    return Object.entries(labels).filter(([key])=>key in value).map(([key,label])=>label+': '+(typeof value[key]==='boolean'?(value[key]?'Archivada':'Activa'):value[key]||'No indicado.')).join('\n\n');
  }
  function show(){if(review&&!dialog.open)dialog.showModal();}
  function render(){
    changes.replaceChildren();warnings.replaceChildren();selections.clear();started=false;
    intro.textContent=`${review.label}: ${review.changes.length} ${review.changes.length===1?'cambio':'cambios'}; ${review.conflicts} con conflicto. ${review.notice}`;
    for(const text of review.warnings)warnings.append(make('li',text));
    keep.hidden=!review.conflicts;keep.disabled=false;
    for(const row of review.changes){
      const article=make('article',undefined,'roundtrip-change');article.append(make('h3',row.label),make('p',row.conflict?'Cambió en ambos sitios: elige la versión que conservarás.':'Cambio de la web disponible para revisar.',row.conflict?'review-warning':'muted'));
      const versions=make('details');versions.append(make('summary','Comparar el contenido'));
      const grid=make('div',undefined,'roundtrip-versions');for(const [title,value] of [['Mi cuaderno local',row.local],['La copia web',row.web]]){const column=make('div');column.append(make('strong',title),make('pre',readable(value,row.kind)));grid.append(column);}versions.append(grid);article.append(versions);
      const label=make('label','Qué hacer con '+row.label),select=make('select');select.required=true;select.name=row.id;
      for(const [value,text] of [['','Elige una versión…'],['local','Conservar la versión local'],['web','Incorporar la versión web']]){const option=make('option',text);option.value=value;select.append(option);}
      select.value=row.suggested||'';label.append(select);article.append(label);changes.append(article);selections.set(row.id,select);
    }
    confirm.disabled=!review.changes.length;confirm.textContent='Incorporar los cambios elegidos';
  }
  close.addEventListener('click',()=>dialog.close());reopen.addEventListener('click',show);
  keep.addEventListener('click',()=>{if(started)return;for(const row of review.changes)if(row.conflict)selections.get(row.id).value='local';});
  input.addEventListener('change',async()=>{
    review=null;reopen.hidden=true;const file=input.files[0];if(!file)return;input.disabled=true;status.textContent='Comparando la copia y tus archivos locales…';
    try{
      if(file.size>4*1024*1024)throw Error('Selecciona un cuaderno JSON de hasta 4 MB.');
      let book;try{book=JSON.parse(await file.text());}catch{throw Error('No se pudo leer el JSON. Descarga una copia del cuaderno desde la web.');}
      review=await post('/api/notebook/web/preview',{book});render();status.textContent=review.changes.length?'Revisión preparada. Tus apuntes todavía no han cambiado.':'La copia no trae cambios pendientes. Tus archivos están conservados.';reopen.hidden=false;show();
    }catch(error){input.value='';status.textContent=error.message;toast(error.message,true);}finally{input.disabled=false;}
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy||!review||!review.changes.length)return;
    const choices=Object.fromEntries([...selections].map(([id,select])=>[id,select.value]));
    if(Object.values(choices).some(value=>!value)){toast('Elige una versión para todos los cambios con conflicto.',true);return;}
    busy=true;input.disabled=true;confirm.disabled=true;keep.disabled=true;for(const select of selections.values())select.disabled=true;
    status.textContent=started?'Reintentando el mismo guardado…':'Guardando las elecciones y comprobando los archivos…';started=true;
    try{
      const result=await post('/api/notebook/web/apply',{token:review.token,choices});
      if(!result.saved)throw Error('No se ha confirmado el guardado. Conserva la copia JSON.');
      status.textContent=result.duplicate?'Este guardado ya estaba completo. No se han duplicado notas ni avances.':`Cambios incorporados: ${result.files} archivos actualizados y ${result.sessions} ${result.sessions===1?'avance':'avances'} con nota y diario comprobados.`;
      dialog.close();reopen.hidden=true;review=null;input.value='';toast(status.textContent);
      document.dispatchEvent(new Event('mi-grado:cuaderno-cambiado'));await syncLive();
    }catch(error){status.textContent=error.message;confirm.textContent='Reintentar el mismo guardado';toast(error.message,true);}
    finally{busy=false;input.disabled=false;confirm.disabled=false;}
  });
});
