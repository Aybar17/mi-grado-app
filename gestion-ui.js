/* Gestión explícita del cuaderno. Los guardados se confirman en la fuente local. */
document.addEventListener('DOMContentLoaded', () => {
  const q = id => document.getElementById(id);
  viewMeta.cuaderno = ['Tu espacio de estudio', 'Mi cuaderno', 'Asignaturas, tareas, horario y copias de seguridad.'];
  const nav = document.createElement('button'); nav.dataset.view = 'cuaderno';
  nav.innerHTML = '<span class="ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 3h14v18H5zM9 7h6M9 11h6M9 15h4"/></svg></span>Mi cuaderno';
  nav.addEventListener('click', () => showView('cuaderno'));
  document.querySelector('.nav').insertBefore(nav, document.querySelector('.nav details'));
  const section = document.createElement('section'); section.id = 'cuaderno'; section.className = 'view';
  section.innerHTML = `
    <div class="notebook-tabs" role="group" aria-label="Gestión del cuaderno">
      <button class="btn" data-notebook="subjects" aria-pressed="true">Asignaturas</button>
      <button class="btn" data-notebook="tasks" aria-pressed="false">Tareas</button>
      <button class="btn" data-notebook="schedule" aria-pressed="false">Horario</button>
      <button class="btn" data-notebook="references" aria-pressed="false">Materiales</button>
      <button class="btn" data-notebook="backup" aria-pressed="false">Copias</button>
    </div><p id="notebookStatus" class="statusline" role="status">Cargando tu cuaderno…</p>
    <div data-notebook-pane="subjects"><div class="notebook-layout">
      <div class="card"><h2 id="subjectEditorTitle">Añadir una asignatura</h2>
        <form id="subjectEditor" class="formgrid">
        <label class="wide">Nombre<input name="name" maxlength="120" required autocomplete="off"></label>
        <label class="wide" id="existingNoteLabel">Ficha existente (opcional)<input name="note" maxlength="400" placeholder="01 Asignaturas/Matemáticas.md"><small>Ruta relativa a tus apuntes. Déjala vacía para crear una ficha.</small></label>
        <label class="wide" id="checkpointLabel" hidden>Último intento<textarea name="checkpoint" rows="3" maxlength="2000"></textarea></label>
        <label class="wide" id="nextPracticeLabel" hidden>Próximo paso<textarea name="nextPractice" rows="3" maxlength="2000"></textarea></label>
        <label class="wide" id="archiveSubjectLabel" hidden><span><input name="archived" type="checkbox"> Archivar asignatura conservando apuntes y registros</span></label>
        <div class="actions wide"><button class="btn primary" type="submit">Guardar asignatura</button><button class="btn" type="button" id="newSubject">Nueva asignatura</button></div>
        </form><p id="subjectEditorStatus" class="statusline" role="status"></p>
      </div><div><h2>Tus asignaturas</h2><div id="managedSubjects" class="notebook-list"></div></div>
    </div></div>
    <div data-notebook-pane="tasks" hidden><div class="notebook-layout">
      <div class="card"><h2 id="taskEditorTitle">Planificar una tarea</h2>
        <form id="taskEditor" class="formgrid">
        <label class="wide">Qué vas a hacer<input name="title" maxlength="300" required placeholder="Resolver el ejercicio 2 sin mirar la solución"></label>
        <label>Asignatura<select name="subject" required></select></label>
        <label>Tipo<select name="kind"><option value="task">Tarea</option><option value="exam">Examen</option></select></label><label>Origen de la fecha<select name="dateStatus"><option value="declared">Declarada</option><option value="confirmed">Confirmada por mí</option></select></label><label>Otra fecha propuesta<input name="proposedDay" type="date"></label><label>Duración (minutos, opcional)<input name="minutes" type="number" min="5" max="480" value="60"></label>
        <label>Día (opcional)<input name="date" type="date"></label>
        <label>Estado declarado<select name="status"><option value="pendiente">Pendiente</option><option value="realizada">Trabajo realizado por mí</option><option value="archivada">Archivada</option></select></label>
        <label class="wide">Objetivo y material<textarea name="detail" rows="3" maxlength="2000" placeholder="Enunciado, página y qué quieres comprobar"></textarea></label>
        <div class="actions wide"><button type="submit" class="btn primary">Guardar tarea</button><button type="button" class="btn" id="newTask">Nueva tarea</button></div>
        </form><p id="taskEditorStatus" role="status" class="statusline"></p>
        <p class="muted">Una tarea sin fecha o vencida sigue pendiente. Declarar trabajo realizado no confirma entrega ni comprensión.</p>
      </div><div><h2>Tareas de este cuaderno</h2><div id="managedTasks" class="notebook-list"></div><p class="muted">Las tareas procedentes de otras notas se mantienen en el Plan de estudio y se revisan en su fuente.</p></div>
    </div></div>
    <div data-notebook-pane="schedule" hidden><div class="card"><h2>Editar mi horario</h2>
      <form id="scheduleEditor"><div class="formgrid"><label>Grupo<input name="group" maxlength="100"></label><label>Periodo<input name="period" maxlength="100" placeholder="Primer semestre"></label></div>
      <div id="scheduleRows" class="schedule-editor-rows"></div>
      <div class="actions"><button type="button" id="addClass" class="btn">Añadir clase</button><button type="submit" class="btn primary">Guardar horario</button></div></form>
      <p id="scheduleEditorStatus" class="statusline" role="status"></p><p class="muted">El horario se guarda en tus apuntes. Editarlo deja pendiente su contraste con el centro y conserva el texto que rodea la tabla.</p>
    </div></div>
    <div data-notebook-pane="references" hidden><div id="localReferenceEditor"></div></div>
    <div data-notebook-pane="backup" hidden><div class="notebook-layout">
      <div class="card"><div class="eyebrow">Conservar tu trabajo</div><h2>Crear una copia</h2>
      <p>Descarga tus fichas de asignatura, plan, horario, capturas y diarios vinculados, junto con la configuración de campus y chat.</p>
      <p class="muted">No incluye adjuntos, otras notas de la bóveda ni borradores pendientes del navegador. Máximo 32 MB. La copia contiene tus datos privados: guárdala para ti.</p>
      <button id="downloadNotebook" class="btn primary">Descargar copia del cuaderno</button><p id="backupDownloadStatus" class="statusline" role="status"></p>
      <h3>Llevar mi cuaderno a la web</h3><p>Prepara una copia de tus fichas, tareas, horario y capturas completas. Revisa qué contiene antes de descargarla. El programa local conserva sus archivos.</p><button id="previewWebNotebook" class="btn">Revisar traslado a la web</button><p id="webNotebookStatus" role="status"></p><ul id="webNotebookWarnings"></ul><button id="downloadWebNotebook" class="btn primary" hidden>Descargar cuaderno para la web</button><p class="muted">Después, en la web: Copias e instalación → Recuperar una copia JSON. Es un traslado manual; no sincroniza futuras ediciones. Esta copia contiene tus notas privadas: no la envíes a otros usuarios.</p></div>
      <div class="card"><div class="eyebrow">Recuperar o trasladar</div><h2>Restaurar una copia</h2>
      <p>Revisa la copia y recupérala en un cuaderno separado. El actual conserva sus archivos.</p>
      <label>Archivo de copia ZIP<input id="restoreNotebookFile" type="file" accept=".zip,application/zip"></label>
      <div id="restorePreview"></div><p id="backupRestoreStatus" class="statusline" role="status"></p>
      <button id="restoreNotebook" class="btn primary" hidden>Crear cuaderno restaurado</button>
      <button id="openRestoredNotebook" class="btn" hidden>Abrir cuaderno restaurado</button>
      </div></div></div>`;
  const main = document.querySelector('main'); main.insertBefore(section, main.querySelector('.footer'));
  let state = null, subjectId = '', taskId = '', subjectSha = null, taskSha = null, scheduleSha = null;
  const referenceEditor=StudyReferences.mount(q('localReferenceEditor'),{notify:toast,onSave:async(subject,reference,version)=>{
    state=await post('/api/manage/reference',{subject,reference,panelSha:version});renderLists();await syncLive();
  }});
  let backupData = '', backupPreview = null, restoreToken = '';
  const e = value => esc(value);
  function pane(id) {
    section.querySelectorAll('[data-notebook-pane]').forEach(el => el.hidden = el.dataset.notebookPane !== id);
    section.querySelectorAll('[data-notebook]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.notebook === id)));
  }
  function shortcut(parent, label, target) {
    const button = document.createElement('button'); button.type='button'; button.className='btn small'; button.textContent=label;
    button.addEventListener('click', () => {pane(target); showView('cuaderno');}); parent.appendChild(button);
  }
  section.querySelectorAll('[data-notebook]').forEach(button => button.addEventListener('click', () => pane(button.dataset.notebook)));
  shortcut(document.querySelector('#asignaturas .callout'), 'Gestionar asignaturas', 'subjects');
  shortcut(document.querySelector('.pending-heading'), 'Añadir o editar tareas', 'tasks');
  shortcut(document.querySelector('#horario .card'), 'Editar horario', 'schedule');
  async function post(route, body) {
    const response = await fetch(route, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json(); if(!response.ok) throw Error(result.error || 'No se confirmó el guardado.');if(route.startsWith('/api/manage/'))invalidateWebNotebook(); return result;
  }
  function renderLists() {
    referenceEditor.render({version:state.panelSha,subjects:state.subjects,bySubject:state.references||{}});
    q('managedSubjects').innerHTML = state.subjects.map(s => `<article class="record"><h3>${e(s.name)}</h3><span class="badge">${s.archived?'Archivada':'Activa'}</span><p>${e(s.nextPractice||'Indica el próximo ejercicio.')}</p><div class="actions"><button class="btn small" data-edit-subject="${e(s.id)}">Editar</button>${!s.archived?`<button class="btn small" data-prepare="${e(s.id)}">Continuar sesión</button>`:''}</div></article>`).join('');
    const selected = q('taskEditor').elements.subject.value;
    q('taskEditor').elements.subject.innerHTML = [...state.subjects].sort((a,b)=>Number(Boolean(a.archived))-Number(Boolean(b.archived))).map(s=>`<option value="${e(s.id)}">${e(s.name)}${s.archived?' (archivada)':''}</option>`).join('');
    if (state.subjects.some(s=>s.id===selected)) q('taskEditor').elements.subject.value=selected;
    q('managedTasks').innerHTML = state.tasks.length ? [...state.tasks].reverse().map(t=>`<article class="record"><h3>${e(t.title)}</h3><p>${e(state.subjects.find(s=>s.id===t.subject)?.name||t.subject)} · ${e(t.date||'Sin día asignado')} · ${t.minutes?e(t.minutes)+' min':'Duración por indicar'}</p><span class="badge">${e(t.status==='realizada'?'Trabajo declarado realizado':t.status)}</span><p>${e(t.detail)}</p><button class="btn small" data-edit-task="${e(t.id)}">Editar tarea</button></article>`).join('') : '<div class="empty">Empieza con el ejercicio que quieres resolver hoy. Puedes dejar la fecha pendiente.</div>';
  }
  function resetSubject() {
    subjectId=''; subjectSha=state.panelSha; q('subjectEditor').reset();
    q('subjectEditorTitle').textContent='Añadir una asignatura';
    q('existingNoteLabel').hidden=false;
    ['checkpointLabel','nextPracticeLabel','archiveSubjectLabel'].forEach(id=>q(id).hidden=true);
  }
  function resetTask() {taskId=''; taskSha=state.planSha; q('taskEditor').reset(); q('taskEditorTitle').textContent='Planificar una tarea';}
  function classRow(item={day:'Lunes',start:'09:00',end:'10:00',subject:'',kind:'Teoría',room:''}) {
    const row = document.createElement('div'); row.className='schedule-editor-row';
    row.innerHTML = `<label>Día<select data-class-field="day">${['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'].map(d=>`<option>${d}</option>`).join('')}</select></label><label>Inicio<input data-class-field="start" type="time" required></label><label>Fin<input data-class-field="end" type="time" required></label><label>Asignatura<input data-class-field="subject" maxlength="150" required></label><label>Tipo<input data-class-field="kind" maxlength="150"></label><label>Aula<input data-class-field="room" maxlength="150"></label><button type="button" class="btn small" aria-label="Quitar esta clase">Quitar</button>`;
    row.querySelectorAll('[data-class-field]').forEach(input=>input.value=item[input.dataset.classField]);
    row.querySelector('button').addEventListener('click',()=>row.remove()); q('scheduleRows').appendChild(row);
  }
  async function submit(event, statusId, route, payload, after) {
    event.preventDefault(); const button=event.currentTarget.querySelector('button[type="submit"]'), status=q(statusId);
    button.disabled=true; status.className='statusline'; status.textContent='Guardando…';
    try {state=await post(route,payload()); renderLists(); after(); await syncLive(); status.textContent='Guardado en este cuaderno.';}
    catch(error) {status.className='statusline error'; status.textContent=error.message;}
    finally {button.disabled=false;}
  }
  q('subjectEditor').addEventListener('submit',event=>submit(event,'subjectEditorStatus','/api/manage/subject',()=>{
    const f=event.currentTarget.elements;
    return {action:subjectId?'edit':'add',panelSha:subjectSha,subject:subjectId?
      {id:subjectId,name:f.name.value,checkpoint:f.checkpoint.value,nextPractice:f.nextPractice.value,archived:f.archived.checked}:
      {name:f.name.value,note:f.note.value}};
  },resetSubject));
  q('taskEditor').addEventListener('submit',event=>submit(event,'taskEditorStatus','/api/manage/task',()=>{
    const f=event.currentTarget.elements;
    return {planSha:taskSha,task:{id:taskId,subject:f.subject.value,title:f.title.value,date:f.date.value,minutes:Number(f.minutes.value),detail:f.detail.value,kind:f.kind.value,dateStatus:f.dateStatus.value,proposedDay:f.proposedDay.value,status:f.status.value}};
  },resetTask));
  q('scheduleEditor').addEventListener('submit',event=>submit(event,'scheduleEditorStatus','/api/manage/schedule',()=>({
    scheduleSha,group:event.currentTarget.elements.group.value,period:event.currentTarget.elements.period.value,
    classes:[...q('scheduleRows').children].map(row=>Object.fromEntries([...row.querySelectorAll('[data-class-field]')].map(input=>[input.dataset.classField,input.value])))
  }),()=>{scheduleSha=state.scheduleSha;}));
  q('newSubject').addEventListener('click',resetSubject); q('newTask').addEventListener('click',resetTask);
  document.addEventListener('change',async event=>{
    const input=event.target.closest('[data-managed-task]'); if(!input||!state)return;
    const item=state.tasks.find(t=>t.id===input.dataset.managedTask); if(!item)return;
    input.disabled=true;
    try {state=await post('/api/manage/task',{planSha:state.planSha,task:{...item,status:input.checked?'realizada':'pendiente'}}); renderLists(); await syncLive(); toast('Trabajo declarado guardado en tus apuntes; no confirma entrega ni dominio.');}
    catch(error){input.checked=false; toast(error.message);} finally{input.disabled=false;}
  });
  q('addClass').addEventListener('click',()=>classRow());
  section.addEventListener('click',event=>{
    const subjectButton=event.target.closest('[data-edit-subject]'), taskButton=event.target.closest('[data-edit-task]');
    if(subjectButton){const s=state.subjects.find(s=>s.id===subjectButton.dataset.editSubject),f=q('subjectEditor'); subjectId=s.id; subjectSha=state.panelSha;
      for(const key of ['name','checkpoint','nextPractice']) f.elements[key].value=s[key]||'';
      f.elements.archived.checked=Boolean(s.archived); q('subjectEditorTitle').textContent='Editar '+s.name;
      q('existingNoteLabel').hidden=true; ['checkpointLabel','nextPracticeLabel','archiveSubjectLabel'].forEach(id=>q(id).hidden=false); f.elements.name.focus();
    }
    if(taskButton){const t=state.tasks.find(t=>t.id===taskButton.dataset.editTask),f=q('taskEditor'); taskId=t.id; taskSha=state.planSha;
      for(const key of ['title','subject','minutes','date','status','detail','kind','dateStatus','proposedDay']) f.elements[key].value=t[key]??(key==='kind'?'task':key==='dateStatus'?'declared':'');
      q('taskEditorTitle').textContent='Editar tarea'; f.elements.title.focus();
    }
  });
  q('downloadNotebook').addEventListener('click',async()=>{
    const button=q('downloadNotebook'),status=q('backupDownloadStatus'); button.disabled=true; status.textContent='Preparando tu copia…';
    try {const response=await fetch('/api/backup/download'); if(!response.ok) throw Error((await response.json()).error);
      const url=URL.createObjectURL(await response.blob()),link=document.createElement('a'); link.href=url; link.download='Mi-grado-copia-'+today()+'.zip'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),3000);
      status.textContent='Copia preparada y descarga solicitada. Comprueba el archivo en tus descargas.';
      toast(status.textContent);
    } catch(error){status.textContent=error.message;toast(error.message,true);} finally{button.disabled=false;}
  });
  let webNotebook=null;
  function invalidateWebNotebook(){if(!webNotebook)return;webNotebook=null;q('downloadWebNotebook').hidden=true;q('webNotebookStatus').textContent='El cuaderno cambió. Vuelve a revisar el traslado para incluir las últimas notas y avances.';}
  q('previewWebNotebook').addEventListener('click',async()=>{
    const btn=q('previewWebNotebook');btn.disabled=true;webNotebook=null;q('downloadWebNotebook').hidden=true;
    try{const value=await post('/api/notebook/web/prepare',{});
      webNotebook=value.book;q('webNotebookStatus').textContent=`${value.book.subjects.length} asignaturas · ${value.book.subjects.reduce((n,s)=>n+(s.references||[]).length,0)} referencias de material · ${value.book.tasks.length} tareas · ${value.book.schedule.length} clases · ${value.book.sessions.length} capturas. ${value.notice}`;
      q('webNotebookWarnings').replaceChildren();for(const warning of value.warnings){const li=document.createElement('li');li.textContent=warning;q('webNotebookWarnings').append(li);}q('downloadWebNotebook').hidden=false;
    }catch(error){q('webNotebookStatus').textContent=error.message;toast(error.message);}finally{btn.disabled=false;}
  });
  q('downloadWebNotebook').addEventListener('click',async()=>{
    if(!webNotebook)return;const button=q('downloadWebNotebook');button.disabled=true;
    try{const result=await post('/api/notebook/web/download',{exchangeId:webNotebook.transfer.exchangeId});const url=URL.createObjectURL(new Blob([JSON.stringify(result.book,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='Mi-grado-para-web.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('Copia para la web preparada. Comprueba la descarga y ábrela en Copias e instalación de la web.');}
    catch(error){invalidateWebNotebook();q('webNotebookStatus').textContent=error.message;toast(error.message,true);}finally{button.disabled=false;}
  });
  q('restoreNotebookFile').addEventListener('change',async event=>{
    backupData=''; backupPreview=null; restoreToken=''; q('restoreNotebook').hidden=true; q('openRestoredNotebook').hidden=true; q('restorePreview').replaceChildren();
    const file=event.target.files[0]; if(!file)return; const status=q('backupRestoreStatus'); status.textContent='Comprobando la copia…';
    try {if(file.size>32*1024*1024)throw Error('La copia debe ocupar como máximo 32 MB.');
      backupData=await new Promise((resolve,reject)=>{const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result).split(',')[1]); reader.onerror=()=>reject(Error('No se pudo leer el archivo.')); reader.readAsDataURL(file);});
      backupPreview=await post('/api/backup/preview',{archive:backupData});
      q('restorePreview').innerHTML=`<div class="review-warning"><strong>${e(backupPreview.label)}</strong><p>${e(backupPreview.subjects.join(' · '))}</p><p>${e(backupPreview.files)} archivos · ${e(backupPreview.notice)}</p></div>`;
      status.textContent='Copia comprobada. Aún no se ha restaurado.'; q('restoreNotebook').hidden=false;
      toast(status.textContent);
    }catch(error){status.textContent=error.message;toast(error.message,true);}
  });
  q('restoreNotebook').addEventListener('click',async()=>{
    if(!backupPreview)return; const button=q('restoreNotebook'), status=q('backupRestoreStatus'); button.disabled=true;
    q('restoreNotebookFile').disabled=true; status.textContent='Restaurando y comprobando los registros…';
    try {const result=await post('/api/backup/restore',{archive:backupData,sha:backupPreview.sha}); restoreToken=result.token;
      status.textContent=`Cuaderno recuperado: ${result.subjects} asignaturas y ${result.captures} capturas. Carpeta: ${result.folder}`;
      toast('Copia recuperada en un cuaderno separado. Tus apuntes originales se conservan.');
      button.hidden=true; q('openRestoredNotebook').hidden=false;
    }catch(error){status.textContent=error.message;toast(error.message,true);} finally{button.disabled=false; q('restoreNotebookFile').disabled=false;}
  });
  q('openRestoredNotebook').addEventListener('click',async()=>{
    try {await post('/api/backup/open',{token:restoreToken}); q('backupRestoreStatus').textContent='Se ha solicitado abrir el cuaderno restaurado en su propia ventana.';}
    catch(error){q('backupRestoreStatus').textContent=error.message;}
  });
  fetch('/api/manage',{cache:'no-store'}).then(async response=>{
    const value=await response.json(); if(!response.ok)throw Error(value.error); state=value;
    renderLists(); resetSubject(); resetTask(); scheduleSha=state.scheduleSha;
    if(state.planIssue){q('taskEditorStatus').textContent='Revisa la nota Plan de Mi grado: '+state.planIssue; q('taskEditor').querySelector('button[type="submit"]').disabled=true;}
    q('scheduleEditor').elements.group.value=state.schedule.group||''; q('scheduleEditor').elements.period.value=state.schedule.period||'';
    state.schedule.classes.forEach(classRow); q('notebookStatus').textContent='Los cambios se guardan en este ordenador.';
    if(location.hash==='#cuaderno')showView('cuaderno');
  }).catch(error=>{q('notebookStatus').textContent='No se pudo abrir la gestión: '+error.message; section.querySelectorAll('form button').forEach(b=>b.disabled=true);});
  document.addEventListener('mi-grado:cuaderno-cambiado',async()=>{
    invalidateWebNotebook();
    try{const response=await fetch('/api/manage',{cache:'no-store'}),value=await response.json();if(!response.ok)throw Error(value.error);state=value;renderLists();q('notebookStatus').textContent='Cuaderno actualizado. Reabre el editor si tenías cambios pendientes antes del traslado.';}
    catch(error){q('notebookStatus').textContent=error.message;}
  });
});
