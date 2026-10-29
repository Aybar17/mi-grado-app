'use strict';
(async function () {
  const $=id=>document.getElementById(id), Core=GradeBook;
  let db, book, pendingNote, pendingResponse, pendingBackup, installPrompt, pendingAICheck, settingsDirty=false, daysOffset=0, setupStep=null, studySubjectId='', historicalReferences=[], resumedSession=null, availableMinutes=0;
  let pendingExamPlan=null,availabilityEditorFor='';
  const examAvailabilityDrafts=new Map();
  const selectedTopics=new Map(), exportInfos=new Map();let noteReviewSequence=0;
  const studyDrafts=new Map(), previousStudyDrafts=new Map();
  const referenceEditor=StudyReferences.mount($('webReferenceEditor'),{mode:'web',notify:message,onSave:async(subjectId,value,version)=>{
    if(book.rev!==version)throw Error('El cuaderno cambió mientras editabas el material. Conserva el texto y vuelve a abrir la referencia.');
    const reference=Core.reference(value);await change(next=>{const subject=next.subjects.find(s=>s.id===subjectId);subject.references=[...(subject.references||[]).filter(r=>r.id!==reference.id),reference];},'before-reference-update');
  }});
  const providerUrls={chatgpt:'https://chatgpt.com/',claude:'https://claude.ai/',gemini:'https://gemini.google.com/'};
  const days=['','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
  function element(tag,value,className) {const el=document.createElement(tag);if(value!==undefined)el.textContent=value;if(className)el.className=className;return el;}
  function message(value,error=false) {StudyUI.notify(value,error);}
  function show(view) {if(view==='study'&&!Core.connectionState(book).ready){view='setup';message('Completa primero los intercambios con Obsidian y tu IA.');}document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==view);document.querySelectorAll('[data-view]').forEach(x=>{x.classList.toggle('active',x.dataset.view===view);if(x.dataset.view===view)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current');});const heading=$(view)?.querySelector('h1');if(heading){heading.tabIndex=-1;heading.focus();}if(view==='setup')renderWizard();if(view==='topics')renderTopics();if(view==='study'){suggestResume();renderTopicSelection();renderResumeNotice();}}
  function action(label,run,secondary=true) {const btn=element('button',label,secondary?'secondary':'');btn.type='button';btn.addEventListener('click',()=>safe(run));return btn;}
  async function safe(run) {try {await run();} catch(e) {message(e.message || 'No se ha completado la operación.',true);}}
  function download(name,value,type='text/plain;charset=utf-8') {const blob=new Blob([value],{type}),url=URL.createObjectURL(blob),link=element('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
  async function fileText(file,max=Core.MAX) {if(!file || file.size>max)throw Error('El archivo falta o supera el tamaño permitido.');return file.text();}
  async function exportBook(value=book) {download(`mi-grado-${value.id}.json`,JSON.stringify(value,null,2),'application/json');if(value.id===book.id && value.rev===book.rev && value.version===book.version){const info=await BookStorage.markExport(db,value);exportInfos.set(value.id,info);renderBackupStatus();}}
  async function save(next,archive=false) {
    $('saveState').textContent='Guardando…';
    try {book=await BookStorage.save(db,next,book,archive);render();$('saveState').textContent='Guardado en este dispositivo';}
    catch(e) {$('saveState').textContent='Guardado pendiente';throw e;}
  }
  function change(fn,archive=false) {const next=structuredClone(book);fn(next);return save(next,archive);}
  function subjectName(id) {return book.subjects.find(s=>s.id===id)?.name || 'Asignatura';}
  function requireReady() {if(!Core.connectionState(book).ready)show('setup');Core.requireNotebook(book);}
  function renderConnections() {
    const state=Core.connectionState(book),steps=$('connectionSteps');steps.replaceChildren();
    for(const [i,name,done] of [[0,'Tu grado',state.profile],[1,'Obsidian',state.obsidian],[2,'Tu IA',state.ai]]){const li=element('li',undefined,done?'complete':'');const btn=action(`${i+1}. ${name} · ${done?'Listo':'Pendiente'}`,()=>{setupStep=i;renderWizard();});if(setupStep===i)btn.setAttribute('aria-current','step');li.append(btn);steps.append(li);}

    $('obsidianStatus').textContent=state.obsidian?`Archivo de comprobación verificado el ${new Date(book.connections.obsidian.checkedAt).toLocaleString('es')}.`:'Archivo de comprobación pendiente.';
    $('aiStatus').textContent=state.ai?`Respuesta compatible revisada el ${new Date(book.connections.ai.checkedAt).toLocaleString('es')}. IA declarada: ${book.settings.provider}.`:'Respuesta de comprobación pendiente.';
    $('prepareObsidian').disabled=!book.settings.vault.trim()||settingsDirty;$('prepareAI').disabled=settingsDirty;
    $('obsidianCheckBox').hidden=!book.connections.obsidian||state.obsidian;$('aiCheckBox').hidden=!book.connections.ai||state.ai;$('prepareObsidian').textContent=state.obsidian?'Repetir comprobación de Obsidian':'Preparar nota de comprobación';$('prepareAI').textContent=state.ai?'Repetir comprobación de mi IA':'Preparar comprobación de mi IA';
    if(book.connections.obsidian){const proof=book.connections.obsidian;$('openObsidianCheck').href=`obsidian://open?vault=${encodeURIComponent(book.settings.vault)}&file=${encodeURIComponent('Mi grado - comprobacion - '+proof.challenge)}`;}
    if(book.connections.ai){const prompt=Core.aiCheck(book);if($('aiCheckPrompt').value!==prompt){$('aiCheckInput').hidden=false;$('aiCheckPrompt').value=prompt;$('aiCheckResponse').value='';pendingAICheck=null;$('aiCheckReview').hidden=true;}}
    $('openAICheck').href=providerUrls[book.settings.provider];$('setupReady').hidden=!state.ready;$('finishSetup').disabled=!state.ready;$('connectionWarning').hidden=state.ready;
    $('progressWarning').hidden=state.ready;
    $('connectionSummary').textContent=state.connectionsReady?`Bóveda: ${book.settings.vault}. IA declarada: ${book.settings.provider}. Intercambios iniciales completados; las transferencias de cada sesión siguen siendo manuales.`:'Puedes organizar y registrar tu estudio sin conexiones. Obsidian y la IA son opcionales; sus intercambios se verifican por separado.';
    for(const id of ['sessionForm','responseForm'])for(const control of $(id).elements)control.disabled=!state.ready;
    if(!state.ready)$('contextBox').hidden=true;renderWizard();
  }
  function renderWizard() {
    if(!book)return;const state=Core.connectionState(book);
    if(setupStep===null)setupStep=0;
    document.querySelectorAll('[data-setup-step]').forEach(x=>x.hidden=Number(x.dataset.setupStep)!==setupStep);
    $('setupPosition').textContent=`Paso ${setupStep+1} de 3 · ${['Tu espacio de estudio','Un archivo de ida y vuelta','Tu chat habitual'][setupStep]}`;
    $('setupBack').disabled=setupStep===0;$('setupNext').hidden=setupStep===2;
    $('setupNext').disabled=settingsDirty;
    $('finishSetup').hidden=!state.ready;
    [...$('connectionSteps').querySelectorAll('button')].forEach((btn,i)=>{if(i===setupStep)btn.setAttribute('aria-current','step');else btn.removeAttribute('aria-current');});
  }
  function openResponse() {requireReady();$('importResponse').showModal();if(!$('responseInput').hidden)$('responseText').focus();}
  function draftForm(id,data) {const f=$(id);if(id==='taskForm'){f.reset();f.elements.id.value='';}for(const [key,value] of Object.entries(data))if(f.elements[key])f.elements[key].value=value;const panel=f.closest('details');if(panel)panel.open=true;f.querySelector('input:not([type=hidden]),select').focus();}
  function taskPreview(t) {
    const card=element('article',undefined,'task-preview'),body=element('div',undefined,'task-preview-body');
    body.append(element('small',subjectName(t.subjectId)),element('h3',t.title),element('p',t.day?(t.day<Core.localDay()?'Fecha pasada · ':t.dateStatus==='confirmed'?'Confirmada por ti · ':'Declarada · ')+t.day:'Sin fecha','task-date'));
    const details=element('details');details.append(element('summary','Ver detalle'),element('p',t.title));if(t.detail)details.append(element('p',t.detail));if(t.proposedDay)details.append(element('p','Cambio propuesto: '+t.proposedDay+'. La fecha vigente se conserva hasta que la edites tras confirmar el acuerdo.'));body.append(details);
    card.append(body,action('Preparar',()=>prepareTask(t)));return card;
  }
  function renderDashboard() {
    const data=Core.overview(book),state=Core.connectionState(book);
    $('sidebarDegree').textContent=book.settings.degree||book.label;$('planSubtitle').textContent=[book.settings.degree,book.settings.center].filter(Boolean).join(' · ')||'Configura tu grado y organiza tus próximos intentos.';
    const hero=$('nextAction');hero.replaceChildren();const body=element('div');body.append(element('div','Siguiente paso','eyebrow'));
    const recommendation=StudyFlow.recommend({subjects:book.subjects,tasks:book.tasks,sessions:book.sessions,today:Core.localDay(),availableMinutes}),next=recommendation.task,latest=recommendation.session,active=book.subjects.filter(s=>!s.archived);
    const firstTopic=active.find(s=>s.topics.some(t=>!t.archived));
    const firstStep=state.ready&&!latest&&!next?(!active.length?'subject':!firstTopic?'topic':null):null;
    body.append(element('h2',!state.ready?'Prepara tus herramientas':next?'Prepara tu siguiente tarea':latest?'Retoma tu estudio':'Elige tu próximo ejercicio'),element('p',!state.ready?'Completa el intercambio con Obsidian y tu IA.':recommendation.subjectId?subjectName(recommendation.subjectId):'Elige una asignatura y el ejercicio que vas a practicar.','next-subject'));
    if(state.ready&&recommendation.kind!=='empty'){body.append(element('p',next?next.title:'Una comprobación para continuar.','recommendation-title'),element('p',recommendation.reason,'recommendation-reason'));}
    const checkpoint=latest?.nextStep||book.subjects.find(s=>s.id===latest?.subjectId)?.nextPractice;
    if(state.ready&&checkpoint){const detail=element('details',undefined,'resume-detail');detail.append(element('summary','Ver el punto de reanudación'),element('p',checkpoint));body.append(detail);}
    hero.append(body,action(state.ready?(latest?'Retomar este intento →':'Preparar sesión →'):'Completar configuración →',()=>{if(!state.ready){show('setup');return;}if(next)prepareTask(next,recommendation.minutes||availableMinutes);else if(latest)resumeSession(latest,availableMinutes);else show('study');},false));
    if(firstStep){body.replaceChildren(element('div','Siguiente paso','eyebrow'),element('h2',firstStep==='subject'?'Crea tu primera asignatura':'Elige qué vas a practicar'),element('p',firstStep==='subject'?'Crea una asignatura. Después añade una tarea o registra tu primer intento, con o sin IA.':'Añade una tarea en Mis tareas, prepara un ejercicio o registra un intento. Mis notas y las conexiones son opcionales.'));hero.lastElementChild.remove();hero.append(action(firstStep==='subject'?'Añadir mi asignatura →':'Añadir una tarea →',()=>{if(firstStep==='subject'){$('guideSubject').click();}else{show('plan');draftForm('taskForm',{subjectId:active[0].id});}},false));}
    const stats=$('planStats');stats.replaceChildren();for(const [n,label] of [[data.subjects,'asignaturas'],[data.topics,'temas disponibles'],[data.pending.length,'tareas pendientes'],[book.sessions.length,'avances registrados']]){const box=element('div',undefined,'stat');box.append(element('b',String(n)),element('span',label));stats.append(box);}
    $('pendingTasks').replaceChildren();if(!data.pending.length)$('pendingTasks').append(element('p','No hay tareas pendientes.','muted'));for(const task of data.pending.slice(0,4))$('pendingTasks').append(taskPreview(task));
    $('taskOverviewCount').textContent=data.pending.length?`${Math.min(4,data.pending.length)} de ${data.pending.length}`:'Al día';
    $('allPendingTasks').textContent=data.pending.length>4?`Ver las ${data.pending.length} tareas`:'Revisar tareas';
    const calendar=$('upcomingDays');calendar.replaceChildren();for(let i=0;i<5;i++){const when=new Date();when.setDate(when.getDate()+daysOffset+i);const day=Core.localDay(when),card=element('article',undefined,'day');card.append(element('h3',when.toLocaleDateString('es',{weekday:'short',day:'numeric',month:'short'})));const tasks=data.pending.filter(t=>t.day===day);if(!tasks.length)card.append(element('p','Sin tareas','muted'));else{const detail=element('details');detail.append(element('summary',`${tasks.length} ${tasks.length===1?'tarea':'tareas'}`));for(const t of tasks)detail.append(element('p',`${subjectName(t.subjectId)} · ${t.title}`));card.append(detail);}calendar.append(card);}
    $('previousDays').disabled=daysOffset===0;$('nextDays').disabled=daysOffset>=28;
  }
  function invalidateExamPlan() {pendingExamPlan=null;$('examPlanPreview').hidden=true;}
  function renderExamAvailability() {
    const task=book.tasks.find(t=>t.id===$('examPlanTask').value);
    const day=$('examAvailableDay'),editorKey=book.id+':'+(task?.id||'');
    if(editorKey!==availabilityEditorFor){availabilityEditorFor=editorKey;day.value='';$('examAvailableMinutes').value='';invalidateExamPlan();}
    day.min=Core.localDay();
    if(task?.day){const end=new Date(task.day+'T12:00:00Z');end.setUTCDate(end.getUTCDate()-1);day.max=end.toISOString().slice(0,10);}else day.removeAttribute('max');
    const rows=examAvailabilityDrafts.get(task?.id)||[],list=$('examAvailableDays');list.replaceChildren();
    if(!rows.length)list.append(element('li','Todavía no has indicado días disponibles.'));
    for(const row of rows){const li=element('li'),label=new Date(row.day+'T12:00:00').toLocaleDateString('es',{weekday:'long',day:'numeric',month:'long'});
      li.append(element('span',label+' · '+(row.minutes?row.minutes+' min':'No puedo estudiar')),action('Cambiar',()=>{day.value=row.day;$('examAvailableMinutes').value=String(row.minutes);invalidateExamPlan();day.focus();}),action('Quitar',()=>{examAvailabilityDrafts.set(task.id,rows.filter(x=>x.day!==row.day));invalidateExamPlan();renderExamAvailability();}));list.append(li);
    }
    $('addExamDay').disabled=!task?.day;
  }
  function renderBackupStatus() {
    const info=exportInfos.get(book.id);
    $('returnLocalBox').hidden=!book.transfer;
    $('backupStatus').textContent=info?`Última copia preparada: ${new Date(info.at).toLocaleString('es')}. ${info.rev===book.rev?'Incluye la revisión actual.':'Hay cambios posteriores: prepara otra copia.'}`:'Todavía no has preparado una copia de este cuaderno.';
    $('backupReminder').hidden=!book.subjects.length || info?.rev===book.rev;
    $('guideBackup').textContent=info?.rev===book.rev?'Copia preparada':'Preparar mi copia';
  }
  function renderGuide() {
    const topics=book.subjects.filter(s=>!s.archived).reduce((n,s)=>n+s.topics.filter(t=>!t.archived).length,0);
    $('guideSubject').textContent=book.subjects.some(s=>!s.archived)?'Asignatura creada':'Añadir mi asignatura';
    $('guideTopics').textContent=topics?'Revisar mis tareas':'Añadir una tarea';
    $('guideStudy').textContent=book.sessions.length?'Retomar mi estudio':'Preparar mi primera sesión';
    $('guideProgress').textContent=book.sessions.length?'Ver mi último avance':'Registrar mi primer intento';
    renderBackupStatus();
  }
  function studyDraft() {
    const f=$('prepareForm');return {fields:Object.fromEntries(['goal','minutes','exercise','checkpoint'].map(key=>[key,f.elements[key].value])),referenceId:f.elements.referenceId.value,historicalReferences:structuredClone(historicalReferences),resumedSession:resumedSession?.id||null,topicIds:[...(selectedTopics.get(studySubjectId)||[])]};
  }
  function rememberStudyDraft() {if(studySubjectId)studyDrafts.set(studySubjectId,studyDraft());}
  function applyStudyDraft(draft) {
    const f=$('prepareForm');for(const key of ['goal','minutes','exercise','checkpoint'])f.elements[key].value=draft.fields[key]||'';
    historicalReferences=structuredClone(draft.historicalReferences||[]);resumedSession=book.sessions.find(s=>s.id===draft.resumedSession)||null;
    if(draft.topicIds)selectedTopics.set(studySubjectId,new Set(draft.topicIds));renderTopicSelection();f.elements.referenceId.value=draft.referenceId||'';renderResumeNotice();$('contextBox').hidden=true;
  }
  function suggestResume() {
    const f=$('prepareForm'),subjectId=f.elements.subjectId.value;if(subjectId===studySubjectId)return;
    rememberStudyDraft();studySubjectId=subjectId;const s=book.subjects.find(s=>s.id===subjectId),last=Core.latestSession(book,subjectId),checkpoint=last?.nextStep||s?.nextPractice||s?.checkpoint||'';
    applyStudyDraft(studyDrafts.get(subjectId)||{fields:{checkpoint:checkpoint.length<=2000?checkpoint:''}});
  }
  function replaceStudyDraft(update) {
    suggestResume();const previous=studyDraft();if(Object.values(previous.fields).some(Boolean)||previous.topicIds.length||previous.referenceId)previousStudyDrafts.set(studySubjectId,previous);
    update();rememberStudyDraft();renderTopicSelection();renderResumeNotice();$('contextBox').hidden=true;
  }
  function prepareTask(task,minutes=availableMinutes) {
    $('prepareForm').elements.subjectId.value=task.subjectId;suggestResume();replaceStudyDraft(()=>{const f=$('prepareForm');f.elements.goal.value=task.title;f.elements.exercise.value=task.detail;f.elements.minutes.value=minutes||'';f.elements.checkpoint.value='';selectedTopics.set(task.subjectId,new Set());historicalReferences=[];resumedSession=null;f.elements.referenceId.value='';});show('study');message('Tarea preparada. Elige los temas y el material que correspondan a este ejercicio.');
  }
  function resumeSession(session,minutes=availableMinutes) {
    $('prepareForm').elements.subjectId.value=session.subjectId;suggestResume();replaceStudyDraft(()=>{const f=$('prepareForm'),request=book.requests.find(r=>r.id===session.id),step=session.nextStep||'';
      f.elements.goal.value=step.length<=2000?step:'';f.elements.checkpoint.value=step.length<=2000?step:'';f.elements.exercise.value=request?.exercise||'';f.elements.minutes.value=minutes||'';
      selectedTopics.set(session.subjectId,new Set(session.topicIds||[]));historicalReferences=structuredClone(session.referenceSnapshot||[]);resumedSession=session;renderStudyReferences();f.elements.referenceId.value=historicalReferences.length?'__history__':'';
    });show('study');$('prepareForm').elements.goal.focus();
  }
  function renderResumeNotice() {
    const box=$('resumeNotice');box.replaceChildren();const last=Core.latestSession(book,studySubjectId),previous=previousStudyDrafts.get(studySubjectId);
    if(last&&!resumedSession)box.append(action('Retomar el último intento de esta asignatura',()=>resumeSession(last)));
    if(resumedSession){const details=element('details');details.append(element('summary','Intento que estás retomando'),element('p',`Registrado el ${new Date(resumedSession.createdAt).toLocaleString('es')}. La ayuda y el resultado siguen siendo los del registro anterior.`));for(const [label,key] of [['Lo que intenté','attempt'],['Ayuda recibida','help'],['Resultado observado','result'],['Próximo paso completo','nextStep']])details.append(element('strong',label),element('p',resumedSession[key]||'No indicado.','record-field'));box.append(details);
      if(resumedSession.nextStep.length>2000)box.append(element('p','El punto completo supera el espacio del formulario. Sigue íntegro en el registro y se compartirá como último intento; escribe un objetivo breve para esta sesión.','resume-warning'));
      const subject=book.subjects.find(s=>s.id===studySubjectId),archived=(resumedSession.topicIds||[]).filter(id=>subject?.topics.find(t=>t.id===id)?.archived);
      if(archived.length)box.append(element('p','Este intento incluía temas ahora archivados. Siguen seleccionados y señalados; puedes desmarcarlos. No se ha elegido otro tema.','resume-warning'));
      box.append(element('p','Los temas aportan su texto actual. Las referencias de material conservan la copia del intento original.','muted'));
    }
    if(historicalReferences.length){const details=element('details');details.append(element('summary','Material del intento original'));for(const reference of historicalReferences)details.append(element('p',[reference.title,reference.location,reference.link,reference.detail].filter(Boolean).join(' · '),'record-field'));details.append(element('p','Elige «Material del intento original» para conservarlo, o selecciona una referencia actual. Un archivo o enlace no se adjunta automáticamente.','muted'));box.append(details);}
    if(previous)box.append(action('Recuperar mi borrador anterior de esta asignatura',()=>{const current=studyDraft();applyStudyDraft(previous);previousStudyDrafts.set(studySubjectId,current);rememberStudyDraft();renderResumeNotice();message('Borrador recuperado en esta pestaña.');}));
    box.hidden=!box.children.length;
  }
  function renderTopicSelection() {
    renderStudyReferences();
    const s=book.subjects.find(s=>s.id===$('prepareForm').elements.subjectId.value),box=$('topicSelection');box.replaceChildren();
    const selectionBefore=selectedTopics.get(s?.id),topics=s?.topics.filter(t=>!t.archived||selectionBefore?.has(t.id)) || [];
    if(!s)return;
    if(!selectedTopics.has(s.id))selectedTopics.set(s.id,new Set(topics.slice(0,1).map(t=>t.id)));
    const selection=selectedTopics.get(s.id);
    for(const value of selection)if(!topics.some(t=>t.id===value))selection.delete(value);
    if(!topics.length)box.append(element('p','Todavía no hay temas en esta asignatura. Puedes añadirlos en Mis notas, o preparar solo tu objetivo.','muted'));
    for(const t of topics){const label=element('label',undefined,'topic-choice'),input=element('input');input.type='checkbox';input.value=t.id;input.checked=selection.has(t.id);input.addEventListener('change',()=>{if(input.checked)selection.add(t.id);else selection.delete(t.id);rememberStudyDraft();});label.append(input,document.createTextNode(t.title+(t.archived?' · archivado, conservado de este intento':'')));box.append(label);}
  }
  function renderStudyReferences(){
    const select=$('studyReference'),current=select.value,subject=book.subjects.find(s=>s.id===$('prepareForm').elements.subjectId.value);select.replaceChildren();const none=element('option','Aportaré el enunciado en mi chat');none.value='';select.append(none);
    if(historicalReferences.length){const option=element('option','Material del intento original · copia conservada');option.value='__history__';select.append(option);}
    for(const reference of subject?.references||[]){if(reference.archived)continue;const option=element('option',reference.title);option.value=reference.id;select.append(option);}
    if(current==='__history__'&&historicalReferences.length||(subject?.references||[]).some(r=>r.id===current&&!r.archived))select.value=current;
  }
  function renderTopics() {
    const s=book.subjects.find(s=>s.id===$('topicSubject').value),list=$('topicList');list.replaceChildren();
    $('topicForm').hidden=!s;
    if(!s){list.append(element('p','Crea una asignatura en Mi cuaderno para añadir sus temas.','muted'));return;}
    if(!s.topics.length)list.append(element('p','Añade un tema escrito o importa un archivo Markdown. Cada nota tendrá su propio lugar.','muted'));
    for(const t of s.topics){
      const card=element('article',undefined,'card');card.append(element('span',t.archived?'Tema archivado':'Tema','eyebrow'),element('h3',t.title),element('small',`${t.content.length.toLocaleString('es')} caracteres${t.filename?' · '+t.filename:''}`));
      const preview=element('details');preview.append(element('summary','Leer apuntes'),element('pre',t.content,'topic-content'));card.append(preview);
      card.append(element('p',t.origin?`Archivo: ${t.origin.name}. Copia inicial: ${new Date(t.origin.importedAt).toLocaleString('es')}. Última comparación: ${new Date(t.origin.checkedAt).toLocaleString('es')}.`:'Origen del archivo y fecha de copia sin registrar. Puedes elegir el archivo para comparar su contenido.','muted'));
      const buttons=element('div',undefined,'actions');buttons.append(action('Editar tema',()=>{const f=$('editTopicForm');f.elements.subjectId.value=s.id;f.elements.id.value=t.id;f.elements.title.value=t.title;f.elements.content.value=t.content;$('editTopic').showModal();}),action('Descargar .md',()=>download(`${t.title.replace(/[<>:"/\\|?*\x00-\x1f]/g,'-')}.md`,t.content,'text/markdown;charset=utf-8')),action(t.archived?'Reactivar tema':'Archivar tema',()=>change(b=>{b.subjects.find(x=>x.id===s.id).topics.find(x=>x.id===t.id).archived=!t.archived;})));
      if(!s.archived)buttons.append(action('Actualizar desde archivo',()=>{$('noteSubject').value=s.id;renderNoteTargets(t.id);show('connect');$('noteFile').focus();}));
      card.append(buttons);list.append(card);
    }
  }
  function renderNoteTargets(selected=$('noteTarget').value) {
    const subject=book.subjects.find(s=>s.id===$('noteSubject').value),target=$('noteTarget');target.replaceChildren();
    const fresh=element('option','Crear un tema nuevo');fresh.value='';target.append(fresh);
    for(const topic of subject?.topics||[]){const option=element('option','Actualizar: '+topic.title+(topic.archived?' (archivado)':''));option.value=topic.id;target.append(option);}
    if(subject?.topics.some(t=>t.id===selected))target.value=selected;
  }
  async function refreshNoteReview() {
    if(!pendingNote)return;
    const draft=pendingNote,sequence=++noteReviewSequence;$('applyNote').disabled=true;
    try{
      if(draft.topicId){
        draft.review=null;
        const review=await Core.reviewTopicUpdate(draft.originalBook,draft.subjectId,draft.topicId,$('noteTitle').value,$('noteText').value,draft.origin);
        if(pendingNote!==draft||sequence!==noteReviewSequence)return;
        draft.review=review;$('noteDecision').value=review.suggested||'';
        $('notePrevious').textContent=review.before.content;
        $('noteConflictNotice').textContent=review.empty?'El archivo está vacío. Elige expresamente si quieres conservar el tema o sustituir su texto.':review.conflict?'El archivo y tu tema han cambiado desde la copia anterior. Compara ambos y elige una versión.':review.suggested==='local'?'El archivo mantiene el texto anterior y tu tema tiene ediciones propias. Se propone conservar tu tema.':'El texto está preparado para comparar. Puedes conservar tu tema o incorporar el archivo revisado.';
      }
    }finally{if(pendingNote===draft&&sequence===noteReviewSequence)$('applyNote').disabled=false;}
  }
  function render() {
    $('bookTitle').textContent=book.label;$('profileForm').elements.label.value=book.label;
    const active=book.subjects.filter(s=>!s.archived);
    $('subjectCount').textContent=`${active.length} activas`;
    for(const select of document.querySelectorAll('.subject-select')) {
      const current=select.value;select.replaceChildren();
      if(!active.length) {const option=element('option','Añade una asignatura primero');option.value='';select.append(option);}
      for(const s of active) {const option=element('option',s.name);option.value=s.id;select.append(option);}
      if(active.some(s=>s.id===current))select.value=current;
    }
    renderNoteTargets();
    const list=$('subjectList');list.replaceChildren();
    if(!book.subjects.length)list.append(element('p','Empieza con una asignatura de prueba. Después podrás importar tu nota de Obsidian.','muted'));
    for(const s of book.subjects) {
      const card=element('article',undefined,'card');card.append(element('span',s.archived?'Archivada':'Asignatura','eyebrow'),element('h3',s.name));
      const latest=Core.latestSession(book,s.id);
      if(latest){for(const [title,key] of [['Último intento','attempt'],['Ayuda recibida','help'],['Resultado observado','result'],['Siguiente paso','nextStep']])card.append(element('strong',title),element('p',latest[key]||'No indicado.','record-field'));}else card.append(element('p',s.checkpoint||'Sin intento registrado. Elige un ejercicio concreto para empezar.','record-field'));if(s.nextPractice&&!latest)card.append(element('strong','Próximo paso del cuaderno local'),element('p',s.nextPractice));
      const buttons=element('div',undefined,'actions');buttons.append(action('Cambiar nombre',()=>{
        const f=$('editForm');f.elements.id.value=s.id;f.elements.name.value=s.name;$('editSubject').showModal();
      }),action(s.archived?'Reactivar':'Archivar',()=>change(b=>{b.subjects.find(x=>x.id===s.id).archived=!s.archived;})));
      if(!s.archived)buttons.append(action('Mis temas',()=>{$('topicSubject').value=s.id;show('topics');}),action('Preparar sesión',()=>{$('prepareForm').elements.subjectId.value=s.id;show('study');$('prepareForm').elements.goal.focus();},false));
      card.append(buttons);list.append(card);
    }
    const sessions=$('sessionList');sessions.replaceChildren();
    if(!book.sessions.length)sessions.append(element('p','Todavía no hay avances guardados.','muted'));
    for(const s of Core.orderedSessions(book).reverse().slice(0,30)) {
      const card=element('article',undefined,'card');card.append(element('small',new Date(s.createdAt).toLocaleString('es')),element('h3',subjectName(s.subjectId)));
      Core.fields.forEach((key,i)=>{card.append(element('strong',['Intento','Ayuda','Resultado','Próximo paso'][i]),element('p',s[key] || 'No indicado.','record-field'));});
      if(s.referenceSnapshot?.length){
        card.append(element('strong','Material de este intento'));
        for(const reference of s.referenceSnapshot)card.append(element('p',[reference.title,reference.location,reference.link,reference.detail].filter(Boolean).join(' · '),'record-field'));
        card.append(element('small','Referencia conservada al preparar la sesión; no confirma lectura del archivo.'));
      }
      card.append(element('small',s.source==='ai-reviewed'?'Resumen de IA revisado por ti.':'Declaración registrada por ti.'),action('Descargar esta nota',()=>download(`${s.id}.md`,Core.recordMarkdown(book,s),'text/markdown;charset=utf-8')));if(!book.subjects.find(subject=>subject.id===s.subjectId)?.archived)card.append(action('Retomar este intento',()=>resumeSession(s)));sessions.append(card);
    }
    $('taskList').replaceChildren();$('completedTaskList').replaceChildren();let closedTasks=0;
    for(const t of book.tasks) {
      const row=element('div',undefined,'task-row'),label=element('label'),input=element('input');input.type='checkbox';input.checked=t.done;input.disabled=t.archived;row.classList.toggle('archived',t.archived);
      input.addEventListener('change',()=>safe(async()=>{const checked=input.checked;try {await change(b=>{b.tasks.find(x=>x.id===t.id).done=checked;});}catch(e){input.checked=!checked;throw e;}}));
      label.append(input,document.createTextNode(t.title));row.append(label,element('small',`${subjectName(t.subjectId)} · ${t.day || 'Sin fecha'}${t.done?' · trabajo declarado':''}`));if(t.minutes)row.append(element('small',t.minutes+' min'));if(t.detail){const detail=element('details');detail.append(element('summary','Ver material y detalle'),element('p',t.detail));row.append(detail);}const actions=element('div',undefined,'task-actions');actions.append(action('Editar tarea',()=>draftForm('taskForm',t)),action(t.archived?'Reactivar tarea':'Archivar tarea',async()=>{await change(b=>{b.tasks.find(x=>x.id===t.id).archived=!t.archived;});message(t.archived?'Tarea reactivada.':'Tarea archivada. Puedes recuperarla con Reactivar tarea.');}));row.append(actions);const closed=t.done||t.archived||book.subjects.find(s=>s.id===t.subjectId)?.archived;if(closed)closedTasks++;$(closed?'completedTaskList':'taskList').append(row);
    }
    if(!$('taskList').children.length)$('taskList').append(element('p','Sin tareas pendientes.','muted'));$('completedTasks').hidden=!closedTasks;$('completedTaskCount').textContent=`Realizadas y archivadas (${closedTasks})`;
    $('classList').replaceChildren();
    for(let day=1;day<=7;day++){const classes=book.schedule.filter(s=>s.day===day).sort((a,b)=>a.start.localeCompare(b.start));if(!classes.length)continue;const card=element('article',undefined,'card');card.append(element('h2',days[day]));for(const s of classes){const row=element('div');row.append(element('p',`${s.start}–${s.end} · ${subjectName(s.subjectId)} · ${s.kind?s.kind+' · ':''}${s.room || 'Lugar pendiente'}`),action('Editar clase',()=>draftForm('classForm',s)));card.append(row);}$('classList').append(card);}
    if(!book.schedule.length)$('classList').append(element('p','Sin clases añadidas.','muted'));
    const examSelect=$('examPlanTask'),examSelection=examSelect.value;examSelect.replaceChildren();for(const t of book.tasks.filter(t=>t.kind==='exam'&&!t.done&&!t.archived&&!book.subjects.find(s=>s.id===t.subjectId)?.archived)){const option=element('option',subjectName(t.subjectId)+' · '+t.title+' · '+(t.day||'sin fecha'));option.value=t.id;examSelect.append(option);}if([...examSelect.options].some(o=>o.value===examSelection))examSelect.value=examSelection;renderExamAvailability();
    const settings=$('settingsForm');if(!settingsDirty)for(const key of ['provider','campus','vault','degree','center'])settings.elements[key].value=book.settings[key];
    $('openChat').href=providerUrls[book.settings.provider];$('openCampus').hidden=!book.settings.campus;if(book.settings.campus)$('openCampus').href=book.settings.campus;
    referenceEditor.render({version:book.rev,subjects:book.subjects,bySubject:Object.fromEntries(book.subjects.map(s=>[s.id,s.references||[]]))});
    renderTopics();suggestResume();renderTopicSelection();renderResumeNotice();renderGuide();renderConnections();renderDashboard();
  }
  function form(id,handler) {
    $(id).addEventListener('submit',event=>{event.preventDefault();const target=event.currentTarget;const data=Object.fromEntries(new FormData(target));const submit=target.querySelector('button[type=submit],button:not([type])');
      if(submit.disabled)return;submit.disabled=true;
      safe(()=>handler(data,target)).finally(()=>submit.disabled=false);
    });
  }
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>show(button.dataset.view)));
  $('settingsForm').addEventListener('input',()=>{settingsDirty=true;renderConnections();});
  $('previousDays').addEventListener('click',()=>{daysOffset=Math.max(0,daysOffset-3);renderDashboard();});
  $('nextDays').addEventListener('click',()=>{daysOffset=Math.min(28,daysOffset+3);renderDashboard();});
  $('availableTime').addEventListener('input',()=>{const input=$('availableTime'),value=Number(input.value)||0;availableMinutes=Number.isInteger(value)&&value>=5&&value<=480?value:0;input.setCustomValidity(input.value&&availableMinutes===0?'Indica entre 5 y 480 minutos, o deja el campo vacío.':'');$('availableTimeNotice').textContent=input.validationMessage||'La propuesta usa tu tiempo de hoy; las fechas siguen siendo planificación, no confirmación del campus.';renderDashboard();});
  $('setupBack').addEventListener('click',()=>{setupStep=Math.max(0,setupStep-1);renderWizard();});
  $('setupNext').addEventListener('click',()=>{setupStep=Math.min(2,setupStep+1);renderWizard();});
  $('finishSetup').addEventListener('click',()=>{if(Core.connectionState(book).ready)show('dashboard');});
  $('prepareObsidian').addEventListener('click',()=>safe(async()=>{await save(Core.startConnection(book,'obsidian'));message('Nota preparada. Descárgala y completa el recorrido en tu bóveda.');}));
  $('downloadObsidianCheck').addEventListener('click',()=>safe(()=>download('Mi grado - comprobacion - '+book.connections.obsidian.challenge+'.md',Core.obsidianCheck(book),'text/markdown;charset=utf-8')));
  $('obsidianCheckFile').addEventListener('change',event=>safe(async()=>{const file=event.target.files[0];if(!/\.md$/i.test(file?.name||''))throw Error('Elige la nota Markdown de comprobación.');const value=await fileText(file,10000);await save(Core.verifyObsidian(book,value));setupStep=2;renderWizard();event.target.value='';message('Archivo devuelto verificado. Completa también la respuesta de tu IA.');}));
  $('prepareAI').addEventListener('click',()=>safe(async()=>{await save(Core.startConnection(book,'ai'));message('Mensaje preparado. Pégalo en la IA elegida y revisa su respuesta al volver.');}));
  $('copyAICheck').addEventListener('click',()=>safe(async()=>{await navigator.clipboard.writeText($('aiCheckPrompt').value);message('Mensaje copiado. Pégalo en tu IA.');}));
  $('aiCheckResponse').addEventListener('input',()=>{pendingAICheck=null;$('aiCheckReview').hidden=true;$('confirmAIUsed').checked=false;});
  $('reviewAICheck').addEventListener('click',()=>safe(()=>{const raw=Core.parseResponseText($('aiCheckResponse').value);Core.verifyAI(book,raw);pendingAICheck=raw;$('aiCheckSummary').textContent=`Respuesta compatible para este cuaderno y la IA declarada ${book.settings.provider}. No concede acceso a archivos ni registra estudio.`;$('confirmAIUsed').checked=false;$('aiCheckReview').hidden=false;$('aiCheckInput').hidden=true;}));
  $('confirmAICheck').addEventListener('click',()=>safe(async()=>{if(!pendingAICheck||!$('confirmAIUsed').checked)throw Error('Revisa la respuesta y confirma que la obtuviste en tu IA.');await save(Core.verifyAI(book,pendingAICheck));pendingAICheck=null;$('aiCheckReview').hidden=true;$('aiCheckInput').hidden=false;$('aiCheckResponse').value='';$('confirmAIUsed').checked=false;message('Intercambio inicial con la IA completado. No se ha creado ningún avance de estudio.');}));
  $('changeAICheck').addEventListener('click',()=>{$('aiCheckInput').hidden=false;$('aiCheckReview').hidden=true;pendingAICheck=null;$('aiCheckResponse').focus();});
  $('guideSubject').addEventListener('click',()=>{show('home');$('subjectForm').closest('details').open=true;$('subjectForm').elements.name.focus();});
  $('guideTopics').addEventListener('click',()=>{show('plan');draftForm('taskForm',{});});
  $('guideStudy').addEventListener('click',()=>show('study'));
  $('guideProgress').addEventListener('click',()=>show('progress'));
  $('guideBackup').addEventListener('click',()=>show('copies'));
  $('importTopic').addEventListener('click',()=>{$('noteSubject').value=$('topicSubject').value;renderNoteTargets('');show('connect');$('noteFile').focus();});
  $('goResponse').addEventListener('click',()=>safe(openResponse));$('openResponse').addEventListener('click',()=>safe(openResponse));$('closeResponse').addEventListener('click',()=>$('importResponse').close());$('changeResponse').addEventListener('click',()=>{$('responseInput').hidden=false;$('responsePreview').hidden=true;pendingResponse=null;$('responseText').focus();});
  $('reloadApp').addEventListener('click',()=>window.location.reload());
  form('profileForm',async data=>{await change(b=>{b.label=data.label.trim() || 'Mi cuaderno';});message('Nombre guardado.');});
  form('subjectForm',async(data,target)=>{await change(b=>b.subjects.push({id:Core.uid('subject'),name:data.name.trim(),topics:data.note?[{id:Core.uid('topic'),title:'Apuntes iniciales',content:data.note,filename:'',archived:false}]:[],archived:false}));target.reset();message('Asignatura añadida. Organiza sus apuntes en Mis notas.');});
  form('editForm',async data=>{await change(b=>{b.subjects.find(x=>x.id===data.id).name=data.name.trim();});$('editSubject').close();message('Nombre de la asignatura guardado.');});
  $('cancelEdit').addEventListener('click',()=>$('editSubject').close());
  $('topicSubject').addEventListener('change',renderTopics);
  $('noteSubject').addEventListener('change',()=>renderNoteTargets(''));
  $('closeNoteReview').addEventListener('click',()=>$('importNoteReview').close());
  $('reopenNoteReview').addEventListener('click',()=>{if(pendingNote)$('importNoteReview').showModal();});
  for(const id of ['noteTitle','noteText'])$(id).addEventListener('input',()=>safe(refreshNoteReview));
  $('downloadNoteDraft').addEventListener('click',()=>download('revision-nota-mi-grado.md',$('noteText').value,'text/markdown;charset=utf-8'));
  $('prepareForm').elements.subjectId.addEventListener('change',()=>{suggestResume();renderTopicSelection();renderResumeNotice();$('contextBox').hidden=true;});
  $('prepareForm').addEventListener('input',event=>{if(event.target.name==='subjectId')return;rememberStudyDraft();$('contextBox').hidden=true;});
  $('studyReference').addEventListener('change',()=>{rememberStudyDraft();$('contextBox').hidden=true;});
  form('topicForm',async(data,target)=>{await save(Core.addTopic(book,$('topicSubject').value,data.title,data.content));target.reset();message('Tema guardado. Puedes seleccionarlo al preparar una sesión.');});
  form('editTopicForm',async data=>{await change(b=>{const t=b.subjects.find(s=>s.id===data.subjectId).topics.find(t=>t.id===data.id);t.title=data.title;t.content=data.content;});$('editTopic').close();message('Tema guardado en este dispositivo. El archivo original se conserva.');});
  $('cancelTopicEdit').addEventListener('click',()=>$('editTopic').close());
  $('cancelTaskEdit').addEventListener('click',()=>{$('taskForm').reset();$('taskForm').elements.id.value='';render();});
  $('cancelClassEdit').addEventListener('click',()=>{$('classForm').reset();$('classForm').elements.id.value='';render();});
  form('taskForm',async(data,target)=>{await change(b=>{const old=b.tasks.find(t=>t.id===data.id);const next={...old,id:data.id||Core.uid('task'),subjectId:data.subjectId,title:data.title.trim(),day:data.day,kind:data.kind,dateStatus:data.dateStatus,proposedDay:data.proposedDay,minutes:Number(data.minutes)||0,detail:data.detail,done:old?.done||false,archived:false};if(old)b.tasks[b.tasks.indexOf(old)]=next;else b.tasks.push(next);});target.reset();target.elements.id.value='';render();message('Tarea guardada.');});
  $('examPlanTask').addEventListener('change',()=>{invalidateExamPlan();$('examAvailableDay').value='';$('examAvailableMinutes').value='';renderExamAvailability();});
  for(const id of ['examAvailableDay','examAvailableMinutes'])$(id).addEventListener('input',invalidateExamPlan);
  $('addExamDay').addEventListener('click',()=>safe(()=>{
    const task=book.tasks.find(t=>t.id===$('examPlanTask').value);
    const day=$('examAvailableDay'),minutes=$('examAvailableMinutes');
    if(!task?.day)throw Error('Añade primero un examen con su fecha vigente.');
    if(!day.value||!minutes.value||!day.checkValidity()||!minutes.checkValidity())throw Error('Elige un día anterior al examen y 0 o entre 5 y 480 minutos.');
    const row={day:day.value,minutes:Number(minutes.value)};
    StudyFlow.preparationPlan({task,today:Core.localDay(),availability:[row]});
    const rows=examAvailabilityDrafts.get(task.id)||[];examAvailabilityDrafts.set(task.id,[...rows.filter(x=>x.day!==row.day),row].sort((a,b)=>a.day.localeCompare(b.day)));
    invalidateExamPlan();renderExamAvailability();day.value='';minutes.value='';
  }));
  form('examPlanForm',async data=>{
    const task=book.tasks.find(t=>t.id===$('examPlanTask').value);
    if($('examAvailableDay').value||$('examAvailableMinutes').value)throw Error('Pulsa Añadir día para incorporar el día que estás editando antes de revisar.');
    const availability=structuredClone(examAvailabilityDrafts.get(task?.id)||[]);
    const subject=book.subjects.find(s=>s.id===task?.subjectId);
    const proposal=StudyFlow.preparationPlan({task,today:Core.localDay(),availability,tasks:book.tasks.filter(t=>book.subjects.some(s=>s.id===t.subjectId&&!s.archived)),checkpoint:Core.latestSession(book,task?.subjectId)?.nextStep||subject?.nextPractice||''});
    pendingExamPlan={...proposal,rev:book.rev,bookId:book.id,subjectId:task.subjectId};
    $('examPlanSummary').textContent=[proposal.missing.join(' ')||'Propuesta pendiente de tu revisión. El examen y los bloques seguirán pendientes; esto no acredita estudio.',...proposal.warnings].join(' ');
    $('examPlanBlocks').replaceChildren(...proposal.blocks.map(b=>element('li',b.day+' · '+b.minutes+' min nuevos'+(b.plannedMinutes?' · '+b.plannedMinutes+' min ya planificados':'')+' · '+b.title+' · '+b.detail)));
    $('applyExamPlan').disabled=!proposal.blocks.length;$('examPlanPreview').hidden=false;
  });
  $('applyExamPlan').addEventListener('click',()=>safe(async()=>{
    if(!pendingExamPlan||pendingExamPlan.rev!==book.rev||pendingExamPlan.bookId!==book.id)throw Error('El cuaderno cambió. Vuelve a revisar la propuesta.');
    const proposal=pendingExamPlan;await change(b=>{for(const block of proposal.blocks)b.tasks.push({id:Core.uid('task'),subjectId:proposal.subjectId,title:block.title,day:block.day,minutes:block.minutes,detail:block.detail,done:false,archived:false});});
    pendingExamPlan=null;$('examPlanPreview').hidden=true;message('Bloques añadidos tras tu revisión. La fecha del examen se conserva.');
  }));
  form('classForm',async(data,target)=>{await change(b=>{const row={...data,id:data.id||Core.uid('class'),day:Number(data.day)},old=b.schedule.find(s=>s.id===data.id);if(old)b.schedule[b.schedule.indexOf(old)]=row;else b.schedule.push(row);});target.reset();target.elements.id.value='';render();message('Clase guardada.');});
  form('settingsForm',async data=>{await change(b=>{b.settings=data;});settingsDirty=false;setupStep=Core.connectionState(book).obsidian?2:1;render();pendingResponse=null;$('responsePreview').hidden=true;message('Configuración guardada. Ya puedes estudiar; las conexiones son opcionales.');});
  form('prepareForm',async data=>{
    requireReady();
    const original=data.referenceId==='__history__',req={id:Core.uid('session'),subjectId:data.subjectId,createdAt:new Date().toISOString(),goal:data.goal,minutes:Number(data.minutes)||0,exercise:data.exercise,checkpoint:data.checkpoint,topicIds:[...(selectedTopics.get(data.subjectId) || [])],referenceIds:original?historicalReferences.map(r=>r.id):data.referenceId?[data.referenceId]:[]};
    if(original)req.referenceSnapshot=structuredClone(historicalReferences);
    const resumedId=resumedSession?.id,preparedBookId=book.id,draftSignature=JSON.stringify(studyDraft());rememberStudyDraft();await change(b=>b.requests.push(req));if(book.id!==preparedBookId||studySubjectId!==data.subjectId||JSON.stringify(studyDraft())!==draftSignature){$('contextBox').hidden=true;message('El formulario cambió mientras se preparaba la sesión. Revisa la selección y prepara de nuevo el contexto.');return;}$('contextText').value=Core.context(book,data.subjectId,req,resumedId);$('contextBox').hidden=false;
    message('Contexto preparado. Revisa los apuntes antes de compartirlo con tu IA.');
  });
  form('sessionForm',async(data,target)=>{requireReady();await change(b=>b.sessions.push({id:Core.uid('session'),subjectId:data.subjectId,createdAt:new Date().toISOString(),source:'user',topicIds:[],...Object.fromEntries(Core.fields.map(k=>[k,data[k]]))}));target.reset();render();message('Avance guardado en este dispositivo. Puedes descargarlo como Markdown o conservar una copia JSON.');});
  $('copyContext').addEventListener('click',()=>safe(async()=>{if(!navigator.clipboard)throw Error('Selecciona y copia el texto del contexto.');await navigator.clipboard.writeText($('contextText').value);message('Contexto copiado. Pégalo en tu chat.');}));
  $('downloadContext').addEventListener('click',()=>download('contexto-mi-grado.md',$('contextText').value,'text/markdown;charset=utf-8'));
  $('noteFile').addEventListener('change',event=>safe(async()=>{
    const file=event.target.files[0];if(!file)return;
    if(!/\.(md|txt)$/i.test(file.name))throw Error('Elige una nota .md o .txt.');
    const originalBook=Core.validate(book),subjectId=$('noteSubject').value,topicId=$('noteTarget').value;
    const subject=originalBook.subjects.find(s=>s.id===subjectId);if(!subject)throw Error('Crea y elige una asignatura antes de traer apuntes.');
    $('noteFile').disabled=true;
    try{
      const content=await fileText(file,400000),now=new Date().toISOString();
      const source=Core.origin({kind:'markdown-file',name:file.name,contentHash:await Core.textHash(content),importedAt:now,checkedAt:now,fileModifiedAt:file.lastModified?new Date(file.lastModified).toISOString():''});
      pendingNote={filename:file.name,origin:source,originalBook,subjectId,topicId};
      $('noteText').value=content;$('noteTitle').value=subject.topics.find(t=>t.id===topicId)?.title||file.name.replace(/\.(md|txt)$/i,'').slice(0,160);
      $('noteImportScope').textContent=subject.name+' · '+(topicId?'Actualizar el tema elegido. Su versión anterior se conservará en las copias de este navegador.':'Crear un tema nuevo.');
      $('noteOriginInfo').textContent='Archivo elegido: '+file.name+' · leído el '+new Date(now).toLocaleString('es')+'.';
      $('noteComparison').hidden=!topicId;$('applyNote').textContent=topicId?'Confirmar la versión elegida':'Incorporar como tema';
      await refreshNoteReview();$('notePreview').hidden=false;$('reopenNoteReview').hidden=false;$('importNoteReview').showModal();
    }finally{$('noteFile').disabled=false;$('noteFile').value='';}
  }));
  $('applyNote').addEventListener('click',()=>safe(async()=>{
    if(!pendingNote)throw Error('Selecciona una nota primero.');
    const draft=pendingNote;
    if(draft.originalBook.id!==book.id||draft.originalBook.rev!==book.rev)throw Error('El cuaderno cambió durante la revisión. Conserva el texto y vuelve a seleccionar el archivo.');
    const controls=['applyNote','noteTitle','noteText','noteDecision','noteFile','noteSubject','noteTarget'];controls.forEach(id=>$(id).disabled=true);
    try{
      if(draft.topicId){
        if(!draft.review||draft.review.incoming.title!==$('noteTitle').value||draft.review.incoming.content!==$('noteText').value)throw Error('Revisa el título y el texto antes de confirmar la nota.');
        const result=Core.applyTopicUpdate(book,draft.review,$('noteDecision').value);
        if(result.changed)await save(result.book,'before-topic-update');
        message(result.changed?'Tema actualizado y versión anterior conservada en Copias e instalación. El archivo original no cambia.':'Tema actual conservado. No se ha incorporado el archivo.');
      }else{await save(Core.addTopic(book,draft.subjectId,$('noteTitle').value,$('noteText').value,draft.filename,draft.origin));message('Tema incorporado con su origen y fecha. Puedes elegirlo en Preparar sesión.');}
      $('importNoteReview').close();$('notePreview').hidden=true;$('reopenNoteReview').hidden=true;pendingNote=null;
      await renderHistory();
    }finally{controls.forEach(id=>$(id).disabled=false);}
  }));
  $('responseFile').addEventListener('change',event=>safe(async()=>{$('responsePreview').hidden=true;pendingResponse=null;$('responseText').value=await fileText(event.target.files[0],100000);}));
  $('responseText').addEventListener('input',()=>{pendingResponse=null;$('responsePreview').hidden=true;});
  $('reviewResponse').addEventListener('click',()=>safe(()=>{
    const raw=Core.parseResponseText($('responseText').value);Core.response(raw,book);pendingResponse=raw;
    for(const key of Core.fields)$('responseForm').elements[key].value=raw[key];$('responsePreview').hidden=false;$('responseInput').hidden=true;$('responseForm').elements.attempt.focus();
    message('Comprueba el resumen. Guardarlo conserva tu declaración, no confirma comprensión ni entrega.');
  }));
  form('responseForm',async data=>{
    requireReady();
    if(!pendingResponse)throw Error('Revisa primero la respuesta.');
    const result=Core.applyResponse({...pendingResponse,...data},book);
    if(!result.duplicate)await save(result.book);
    pendingResponse=null;$('responsePreview').hidden=true;$('responseInput').hidden=false;$('responseText').value='';$('responseFile').value='';$('responseForm').reset();$('importResponse').close();show('progress');
    message(result.duplicate?'Esta sesión ya estaba guardada; no se ha duplicado.':'Resumen revisado y guardado en este dispositivo. Puedes descargar su nota en Registrar avance.');
  });
  $('exportBook').addEventListener('click',()=>safe(async()=>{await exportBook();message('Copia preparada para descargar. Comprueba que está en Archivos o Descargas; el navegador no confirma que hayas conservado el archivo.');}));
  $('exportReturn').addEventListener('click',()=>safe(async()=>{await exportBook();message('Copia preparada. En el programa local, abre Mi cuaderno → Copias → Traer cambios desde la web y revisa las versiones antes de guardar.');}));
  document.querySelectorAll('.exportMarkdown').forEach(btn=>btn.addEventListener('click',()=>safe(()=>download(`mi-grado-${book.id}.md`,Core.markdown(book),'text/markdown;charset=utf-8'))));
  $('backupFile').addEventListener('change',event=>safe(async()=>{pendingBackup=null;$('backupPreview').hidden=true;pendingBackup=Core.parse(await fileText(event.target.files[0]));$('backupInfo').textContent=`${pendingBackup.label}: ${pendingBackup.subjects.length} asignaturas, ${pendingBackup.subjects.reduce((n,s)=>n+s.topics.length,0)} temas, ${pendingBackup.tasks.length} tareas, ${pendingBackup.schedule.length} clases y ${pendingBackup.sessions.length} registros. Se conservará el cuaderno actual en Cuadernos anteriores.`;$('backupPreview').hidden=false;}));
  $('restoreBook').addEventListener('click',()=>safe(async()=>{if(!pendingBackup)throw Error('Selecciona una copia primero.');settingsDirty=false;setupStep=null;await save(Core.resetConnections(pendingBackup),true);examAvailabilityDrafts.clear();invalidateExamPlan();studyDrafts.clear();previousStudyDrafts.clear();selectedTopics.clear();studySubjectId='';historicalReferences=[];resumedSession=null;for(const id of ['taskForm','classForm','prepareForm'])$(id).reset();studySubjectId='';pendingBackup=null;suggestResume();renderTopicSelection();renderResumeNotice();exportInfos.set(book.id,await BookStorage.exportInfo(db,book.id));renderBackupStatus();$('backupPreview').hidden=true;$('contextBox').hidden=true;$('responsePreview').hidden=true;pendingResponse=null;await renderHistory();show('setup');message('Cuaderno recuperado y anterior conservado. Verifica los intercambios en este dispositivo; no se heredan como conexiones activas.');}));
  async function renderHistory() {$('historyList').replaceChildren();for(const entry of (await BookStorage.history(db)).sort((a,b)=>b.createdAt.localeCompare(a.createdAt))){$('historyList').append(action(`${entry.book.label} · ${entry.reason==='before-upgrade'?'antes de actualizar':entry.reason==='before-topic-update'?'antes de actualizar un tema':entry.reason==='before-reference-update'?'antes de modificar material':'cuaderno anterior'} · ${new Date(entry.createdAt).toLocaleString('es')} · descargar copia`,()=>exportBook(entry.book)));}}
  $('persist').addEventListener('click',()=>safe(async()=>{const granted=await navigator.storage?.persist?.();message(granted?'El navegador ha concedido almacenamiento persistente. Conserva también copias descargadas.':'El navegador no ha garantizado la conservación. Descarga copias; no dependas únicamente de este dispositivo.');}));
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('install').hidden=false;});
  $('install').addEventListener('click',()=>safe(async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('install').hidden=true;}}));
  try {
    db=await BookStorage.open();book=await BookStorage.load(db);
    if(!book)book=await BookStorage.save(db,Core.newBook(),null);
    exportInfos.set(book.id,await BookStorage.exportInfo(db,book.id));render();show(Core.connectionState(book).ready?'dashboard':'setup');await renderHistory();$('saveState').textContent='Guardado en este dispositivo';
  } catch(e) {message(e.message,true);$('saveState').textContent='Sin guardado disponible';document.querySelectorAll('main button').forEach(b=>b.disabled=true);return;}
  if('serviceWorker' in navigator && window.isSecureContext) {
    const hadController=!!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener('controllerchange',()=>{if(hadController)$('updateNotice').hidden=false;});
    navigator.serviceWorker.register('sw.js').then(()=>navigator.serviceWorker.ready).then(()=>{$('offlineState').textContent='Aplicación preparada para abrirse sin conexión en este navegador. Las descargas y la IA externa tienen sus propios requisitos.';}).catch(()=>{$('offlineState').textContent='El modo sin conexión no está disponible. Usa conexión y conserva tus copias.';});
  } else $('offlineState').textContent='Esta dirección no permite instalación ni modo sin conexión. Usa HTTPS o una vista previa local.';
})();
