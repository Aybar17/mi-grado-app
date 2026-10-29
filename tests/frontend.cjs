const fs=require('fs'),vm=require('vm'),assert=require('assert');
const template=fs.readFileSync('panel-template.html','utf8');
for(const match of template.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)){
  if(!match[1].includes('application/json')&&!match[2].startsWith('__'))new vm.Script(match[2]);
}
new vm.Script(fs.readFileSync('panel-extra.js','utf8'));
new vm.Script(fs.readFileSync('conexiones-ui.js','utf8'));
new vm.Script(fs.readFileSync('gestion-ui.js','utf8'));
new vm.Script(fs.readFileSync('intercambio-ui.js','utf8'));
new vm.Script(fs.readFileSync('materiales-ui.js','utf8'));
for(const name of ['app.js','core.js','storage.js'])new vm.Script(fs.readFileSync('web/app/'+name,'utf8'));
const core=template.match(/<script id="panel-core">([\s\S]*?)<\/script>/)[1];
const context={Intl,Date};vm.createContext(context);vm.runInContext(fs.readFileSync('flujo-estudio.js','utf8'),context);vm.runInContext(core+';this.core=PanelCore',context);
assert(!context.core.complete({saved:true,saveState:'pending',journalLinked:false}));
assert(context.core.complete({saved:true,saveState:'complete',journalLinked:true}));
const generated=context.core.sessionText({subject:{name:'Demo',id:'demo'},minutes:'-10',review:{},captures:[]});
assert(!generated.includes('-10 minutos'));assert(generated.includes('pendiente de indicar'));
const ui=require('../team-ui.js');
const handoff=ui.buildHandoff({id:'demo',instructions:[{title:'Privado',exportable:false}],memoryScope:[{title:'Secreto',exportable:false}],inputs:[{title:'Oculto',exportable:false}]});
assert(!handoff.includes('Privado'));assert(!handoff.includes('Secreto'));assert(!handoff.includes('Oculto'));
assert.equal(ui.safeHref('javascript:alert(1)'),'');
const dates=[{subject:'old',date:'2026-10-07',time:'12:00',source:{url:'https://example.org/old'}},{subject:'soon',date:'2026-10-11',time:'23:55',title:'Entrega',source:{url:'https://example.org/assignment'}},{subject:'forecast',date:'2026-10-09',title:'Semana prevista',source:'Cronograma'}];
assert.equal(context.core.nextPriority({deadlines:dates},'2026-10-08T10:00:00Z').subject,'soon');
assert.equal(context.core.nextPriority({deadlines:dates},'2026-10-01T10:00:00Z'),null);
assert.equal(context.core.nextPriority({deadlines:[dates[0],dates[2]]},'2026-10-08T10:00:00Z'),null);
assert(context.core.sessionText({subject:{name:'Demo'},review:{},captures:[]}).includes('confirmar el enunciado oficial antes de empezar'));
const shared=require('../flujo-estudio.js'),input={minutes:75,exercise:'Página 2, ejercicio 1',checkpoint:'Repetir el segundo caso'};
const localText=context.core.sessionText({subject:{name:'Demo'},review:{},captures:[],...input});
assert(localText.includes(shared.preparation(input)));assert(localText.includes(shared.closing));
const selectedNote=context.core.sessionText({subject:{name:'Demo'},review:{},captures:[],material:{title:'Tema elegido',webTopicId:'topic-demo01',noteText:'SOLO ESTE TEMA',noteModifiedAt:'2026-10-16'}});
assert(selectedNote.includes('SOLO ESTE TEMA'));
assert(!context.core.sessionText({subject:{name:'Demo',materials:[{noteText:'NO ELEGIDO'}]},review:{},captures:[]}).includes('NO ELEGIDO'));
console.log('Sintaxis, guardado, minutos, exportación, prioridad y enunciado ausente: OK');

// Casos ficticios de decisión: se comprueba la ayuda organizativa, no notas ni aprendizaje.
const recommendationInput={today:'2026-10-21',availableMinutes:20,
  subjects:[{id:'subject-a',archived:false},{id:'subject-b',archived:false},{id:'subject-hidden',archived:true}],
  tasks:[],sessions:[]};
const task=(id,day,minutes,subjectId='subject-a')=>({id,subjectId,title:'Ejercicio ficticio '+id,day,minutes,done:false,archived:false});
const attempt=(id,createdAt,subjectId='subject-a')=>({id,subjectId,createdAt,attempt:'Intento ficticio',help:'Una pista',result:'Con guía',nextStep:'Repetir una variante sin pistas'});
const recommend=patch=>shared.recommend({...recommendationInput,...patch});
assert.equal(recommend({}).kind,'empty');
const dueTomorrow=task('task-near','2026-10-22',90),recent=attempt('session-recent','2026-10-21T08:00:00Z');
let suggestion=recommend({tasks:[dueTomorrow],sessions:[recent]});
assert.equal(suggestion.kind,'task');assert.equal(suggestion.task.id,dueTomorrow.id);
assert.equal(suggestion.minutes,20);assert.equal(suggestion.partial,true);assert.equal(suggestion.task.minutes,90);
assert.equal(suggestion.requiresReview,false);
suggestion=recommend({tasks:[task('task-old','2026-10-18',90),dueTomorrow]});
assert.equal(suggestion.task.id,'task-old');assert.equal(suggestion.requiresReview,true);
assert.equal(suggestion.minutes,20); // No acumula varios bloques atrasados en una sesión.
suggestion=recommend({tasks:[task('task-long','2026-10-22',90),task('task-fit','2026-10-22',15)]});
assert.equal(suggestion.task.id,'task-fit');assert.equal(suggestion.partial,false);assert.equal(suggestion.minutes,15);
const future=task('task-future','2026-10-25',15),older=attempt('session-older','2026-10-18T08:00:00Z');
suggestion=recommend({tasks:[future],sessions:[recent,older]});
assert.equal(suggestion.kind,'resume');assert.equal(suggestion.session.id,recent.id);
suggestion=recommend({tasks:[task('task-none-long','',90),task('task-none-fit','',15)]});
assert.equal(suggestion.task.id,'task-none-fit');
suggestion=recommend({tasks:[{...dueTomorrow,done:true},{...dueTomorrow,id:'task-archived',archived:true},task('task-hidden','2026-10-21',10,'subject-hidden')],sessions:[attempt('session-hidden','2026-10-22T08:00:00Z','subject-hidden')]});
assert.equal(suggestion.kind,'empty');
suggestion=recommend({tasks:[task('task-no-duration','2026-10-22',0)]});
assert.equal(suggestion.unknownDuration,true);assert.equal(suggestion.partial,false);assert.equal(suggestion.minutes,0);
suggestion=recommend({tasks:[dueTomorrow],availableMinutes:0});
assert.equal(suggestion.partial,false);assert.equal(suggestion.minutes,0);
for(const availableMinutes of [-1,1,4,481,1.5,'20'])assert.throws(()=>recommend({availableMinutes}));
for(const availableMinutes of [5,480])assert.equal(recommend({tasks:[task('task-long','2026-10-22',90)],availableMinutes}).kind,'task');
// Fechas de calendario cercanas a los cambios horarios; no se usan horas UTC para el plazo.
for(const [today,near,far] of [['2026-10-24','2026-10-27','2026-10-28'],['2026-03-28','2026-03-31','2026-04-01']]){
  assert.equal(recommend({today,tasks:[task('task-dst-near',near,20)],sessions:[recent]}).kind,'task');
  assert.equal(recommend({today,tasks:[task('task-dst-far',far,20)],sessions:[recent]}).kind,'resume');
}
const immutableInput={...recommendationInput,tasks:[dueTomorrow],sessions:[older,recent]},snapshot=JSON.stringify(immutableInput);
assert.deepEqual(shared.recommend(immutableInput),shared.recommend(immutableInput));assert.equal(JSON.stringify(immutableInput),snapshot);
assert.equal(typeof suggestion.reason,'string');
console.log('Recomendación ficticia: plazos, disponibilidad, reanudación, archivo y conservación: OK');

// El panel local normaliza su plan sin perder las marcas ni el texto de una tarea larga.
const localCore=context.core,localAt='2026-10-21T10:00:00Z';
const localPlan={subjects:[{id:'subject-local',name:'Asignatura ficticia',archived:false}],
  pendingTasks:[{id:'task-shared',subject:'subject-local',title:'Tarea conservada',date:'2026-10-22',duration:'35 min',detail:'Detalle íntegro'},
    {subject:'subject-local',title:'Tarea sin fecha',duration:'sin estimar'},
    {id:'task-invalid-day',subject:'subject-local',title:'Fecha imposible',date:'2026-02-30',minutes:90}],
  week:[{date:'2026-10-22',slots:[{id:'task-shared',subject:'subject-local',title:'Duplicado del resumen',minutes:35},
    {subject:'subject-local',title:'Tarea semanal',duration:'15 minutos'},
    {id:'task-closed',subject:'subject-local',title:'Trabajo declarado',minutes:20,status:'realizada'}]}],deadlines:[]};
const localSnapshot=JSON.stringify(localPlan),weekSlot=localPlan.week[0].slots[1];
assert.equal(localCore.taskKey(weekSlot,'2026-10-22'),'2026-10-22|subject-local|Tarea semanal');
assert.equal(localCore.taskKey(localPlan.pendingTasks[0]),'task-shared');
const localTasks=localCore.planTasks(localPlan,{'2026-10-22|subject-local|Tarea semanal':true});
assert.equal(localTasks.length,5);assert.equal(localTasks.filter(t=>t.id==='task-shared').length,1);
assert.equal(localTasks.find(t=>t.id==='task-shared').minutes,35);
assert.equal(localTasks.find(t=>t.id==='task-shared').detail,'Detalle íntegro');
assert(localTasks.find(t=>t.title==='Tarea semanal').done);assert(localTasks.find(t=>t.id==='task-closed').done);
assert.equal(localTasks.find(t=>t.id==='task-invalid-day').day,'');
assert.equal(localTasks.find(t=>t.title==='Tarea sin fecha').minutes,0);
const localChoice=localCore.recommendation(localPlan,{'2026-10-22|subject-local|Tarea semanal':true},20,localAt);
assert.equal(localChoice.task.id,'task-shared');assert.equal(localChoice.partial,true);assert.equal(localChoice.minutes,20);
const officialDue={subject:'subject-local',date:'2026-10-22',time:'23:55',title:'Entrega ficticia',source:{title:'Campus ficticio',url:'https://example.org/assignment'}};
const dueChoice=localCore.recommendation({...localPlan,deadlines:[officialDue]}, {},20,localAt);
assert.equal(dueChoice.kind,'deadline');assert.equal(dueChoice.task.title,officialDue.title);
assert.equal(dueChoice.minutes,20);assert(dueChoice.task.detail.includes(officialDue.source.url));
assert(dueChoice.task.detail.includes('2026-10-22'));assert(dueChoice.task.detail.includes('23:55'));assert(dueChoice.task.detail.includes('Europe/Madrid'));
const fullTitle='Título completo '+ 'á'.repeat(500),fullDetail='Material completo '+ '🧪'.repeat(1500)+' FIN ÍNTEGRO';
const prepared=localCore.taskPreparation({title:fullTitle,detail:fullDetail,day:'2026-10-22'},20,localChoice.reason);
assert.equal(prepared.goal.length,300);assert.equal(prepared.exercise.length,250);assert(prepared.shortened);
assert(prepared.taskContext.includes(fullTitle));assert(prepared.taskContext.includes(fullDetail));assert.equal(prepared.minutes,20);
const preparedContext=localCore.sessionText({subject:{id:'subject-local',name:'Asignatura ficticia'},review:{},captures:[],...prepared});
assert(preparedContext.includes(fullTitle));assert(preparedContext.includes(fullDetail));
const editedPreview='Mi contexto editado a mano. Tiempo anterior: 90 minutos.';
const firstAvailability=localCore.availabilityPreview(editedPreview,20),newAvailability=localCore.availabilityPreview(firstAvailability,45);
assert(newAvailability.startsWith('DISPONIBILIDAD DE HOY: 45 minutos'));
assert.equal((newAvailability.match(/DISPONIBILIDAD DE HOY:/g)||[]).length,1);
assert(newAvailability.includes(editedPreview));assert(localCore.availabilityPreview(newAvailability,0).startsWith('DISPONIBILIDAD DE HOY: pendiente de indicar'));
assert.equal(JSON.stringify(localPlan),localSnapshot);
console.log('Panel local: plan mixto, marcas, entrega, texto íntegro y disponibilidad actual: OK');

// Cambiar de tarea conserva el borrador anterior completo y permite volver a intercambiarlos.
const originalDraft={values:{sessionGoal:'Objetivo manual anterior',sessionPreview:'Texto manual '+fullDetail,sessionExercise:'Ejercicio A',sessionMinutes:'90'},captures:['capture-original'],taskContext:fullTitle,dirty:true,edited:true};
const otherDraft={values:{sessionGoal:'Otra asignatura intacta'},captures:[],taskContext:'',dirty:false};
const nextDraft={values:{sessionGoal:'Nueva tarea recomendada',sessionPreview:'Contexto de B',sessionExercise:'Ejercicio B',sessionMinutes:'20'},captures:['capture-new'],taskContext:'Tarea B',dirty:false,edited:true};
const originalState={drafts:{'subject-local':originalDraft,'subject-other':otherDraft},previous:{}},originalStateText=JSON.stringify(originalState),nextDraftText=JSON.stringify(nextDraft);
const changedDraft=localCore.replaceDraft(originalState,'subject-local',nextDraft);
assert.equal(JSON.stringify(originalState),originalStateText);assert.equal(JSON.stringify(nextDraft),nextDraftText);
assert.deepEqual(changedDraft.drafts['subject-local'],nextDraft);
assert.deepEqual(changedDraft.previous['subject-local'],originalDraft);
assert.deepEqual(changedDraft.drafts['subject-other'],otherDraft);
const restoredDraft=localCore.replaceDraft(changedDraft,'subject-local');
assert.deepEqual(restoredDraft.drafts['subject-local'],originalDraft);
assert.deepEqual(restoredDraft.previous['subject-local'],nextDraft);
assert.deepEqual(localCore.replaceDraft(restoredDraft,'subject-local'),changedDraft);
const clonedDraft=localCore.replaceDraft(originalState,'subject-local',nextDraft);clonedDraft.drafts['subject-local'].values.sessionGoal='Edición posterior';
assert.equal(nextDraft.values.sessionGoal,'Nueva tarea recomendada');assert.equal(JSON.stringify(originalState),originalStateText);
const firstDraft=localCore.replaceDraft({drafts:{},previous:{}},'subject-new',nextDraft);
assert(!Object.hasOwn(firstDraft.previous,'subject-new'));
assert.throws(()=>localCore.replaceDraft(originalState,'subject-local'),/No hay un borrador/);
const previousReferenceContext=localCore.sessionText({subject:{id:'subject-local',name:'Asignatura ficticia'},review:{},captures:[],goal:'Objetivo actual',taskContext:'REFERENCIA ANTERIOR: objetivo anterior\n'+fullTitle});
assert(previousReferenceContext.includes('el objetivo y ejercicio actuales prevalecen'));assert(previousReferenceContext.includes(fullTitle));
console.log('Borradores locales: reemplazo explícito, copia íntegra, recuperación reversible y referencia anterior: OK');

// An exam declared without an official URL or time still needs preparation.
const examData={subjects:[{id:'math-demo',nextPractice:'Retry an exercise on paper'},{id:'other-demo'}],
 deadlines:[{kind:'exam',subject:'math-demo',title:'Fictional exam',date:'2026-11-16',evidence:'declarado',source:{url:'obsidian://example'},preparationDays:14}],
 week:[{date:'2026-11-11',slots:[{id:'other-task',subject:'other-demo',title:'Other practice',minutes:45},{id:'math-diagnostic',subject:'math-demo',title:'Diagnostic, three topics'}]}]};
const examSnapshot=JSON.stringify(examData);
let examChoice=context.core.recommendation(examData,{},0,'2026-11-11T10:00:00Z');
assert.equal(examChoice.kind,'exam-preparation');assert.equal(examChoice.subjectId,'math-demo');assert.equal(examChoice.task.id,'math-diagnostic');assert.equal(examChoice.minutes,0);
assert(examChoice.reason.includes('5 días'));assert(examChoice.reason.includes('Hora pendiente'));assert(examChoice.reason.includes('confirmación docente pendiente'));
assert.equal(context.core.nextPriority(examData,'2026-11-11T10:00:00Z'),null);
assert.equal(context.core.examPreparation(examData,'2026-11-01T10:00:00Z'),null);
assert.equal(context.core.examPreparation(examData,'2026-11-17T10:00:00Z'),null);
assert.equal(context.core.recommendation(examData,{},20,'2026-11-13T10:00:00Z').minutes,20);
assert.equal(context.core.examPreparation({...examData,deadlines:[{...examData.deadlines[0],completed:true}]},'2026-11-11T10:00:00Z'),null);
assert.equal(context.core.examPreparation({...examData,subjects:[{id:'math-demo',archived:true}]},'2026-11-11T10:00:00Z'),null);
const untyped={...examData,deadlines:[{...examData.deadlines[0],kind:'note'}]};assert.equal(context.core.examPreparation(untyped,'2026-11-11T10:00:00Z'),null);
const urgent={subject:'other-demo',date:'2026-11-12',time:'12:00',title:'Fictional deadline',source:{url:'https://example.org/due'}};
assert.equal(context.core.recommendation({...examData,deadlines:[...examData.deadlines,urgent]}, {},20,'2026-11-11T10:00:00Z').kind,'deadline');
assert.equal(JSON.stringify(examData),examSnapshot);
console.log('Exam preparation: declared date without time, five-day horizon, subject context and pending status: OK');

assert.equal(context.core.upcomingDays({week:[{date:'2026-11-10'},{date:'2026-11-11'},{date:'2026-11-12'}]},'2026-11-11T09:00:00Z').map(d=>d.date).join(','),'2026-11-11,2026-11-12');
assert.equal(context.core.upcomingDays({week:[{date:'2026-11-10'},{date:'2026-11-11'}]},'2026-11-10T23:30:00Z')[0].date,'2026-11-11');
