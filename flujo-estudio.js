(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudyFlow=api;})(globalThis,function(){
  'use strict';
  const fields=['attempt','help','result','nextStep'];
  const labels=['Lo que intenté','Ayuda recibida','Resultado observado','Próximo paso'];
  // Stable date order also covers an old result imported after a newer attempt.
  function orderedSessions(sessions,subjectId) {
    return sessions.filter(s=>!subjectId||s.subjectId===subjectId).map((s,index)=>({s,index}))
      .sort((a,b)=>(Date.parse(a.s.createdAt)||0)-(Date.parse(b.s.createdAt)||0)||a.index-b.index).map(x=>x.s);
  }
  function recommend({subjects=[],tasks=[],sessions=[],today,availableMinutes=0}) {
    if(!Number.isInteger(availableMinutes)||availableMinutes<0||availableMinutes>480||(availableMinutes>0&&availableMinutes<5))
      throw Error('Indica entre 5 y 480 minutos, o deja el tiempo vacío.');
    if(typeof today!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(today)||!Number.isFinite(Date.parse(today+'T12:00:00Z'))||new Date(today+'T12:00:00Z').toISOString().slice(0,10)!==today)
      throw Error('Indica un día válido para revisar el plan.');
    const active=new Set(subjects.filter(s=>!s.archived).map(s=>s.id));
    const pending=tasks.filter(t=>active.has(t.subjectId)&&!t.done&&!t.archived);
    const horizon=new Date(Date.parse(today+'T12:00:00Z')+3*86400000).toISOString().slice(0,10);
    const fits=t=>availableMinutes>0&&Number.isInteger(t.minutes)&&t.minutes>=5&&t.minutes<=availableMinutes;
    const dated=pending.filter(t=>t.day&&t.day<=horizon).slice().sort((a,b)=>a.day.localeCompare(b.day)||Number(fits(b))-Number(fits(a)));
    const examHorizon=new Date(Date.parse(today+'T12:00:00Z')+14*86400000).toISOString().slice(0,10);
    const exam=pending.filter(t=>t.kind==='exam'&&t.day&&t.day>=today&&t.day<=examHorizon).slice().sort((a,b)=>a.day.localeCompare(b.day))[0];
    const latest=orderedSessions(sessions.filter(s=>active.has(s.subjectId))).at(-1)||null;
    const task=dated[0]||exam||(!latest?(pending.find(fits)||pending[0]):null);
    if(task) {
      const duration=Number.isInteger(task.minutes)&&task.minutes>=5?task.minutes:0;
      const partial=!!(duration&&availableMinutes&&duration>availableMinutes),requiresReview=!!(task.day&&task.day<today);
      let reason=task===exam&&!requiresReview?'Prepara el examen del '+task.day+' antes del día de la prueba. '+(task.dateStatus==='confirmed'?'Fecha confirmada por ti; revisa posibles cambios.':'Fecha declarada, pendiente de contraste.')+(task.proposedDay?' Hay un cambio propuesto al '+task.proposedDay+'; la fecha vigente se conserva.':''):requiresReview?'La fecha prevista ya pasó: revisa si sigue pendiente; no confirma incumplimiento.':task.day&&task.day<=horizon?'Está prevista en el plan para los próximos tres días. La fecha no confirma un plazo oficial.':fits(task)?'La duración prevista cabe en el tiempo que has indicado.':'Es una tarea pendiente del plan; confirma qué parte vas a intentar.';
      if(partial)reason+=' Empieza por un bloque de '+availableMinutes+' minutos; la tarea completa sigue pendiente.';
      else if(!duration)reason+=' Su duración está sin estimar.';
      if(!availableMinutes)reason+=' Indica el tiempo disponible antes de fijar el bloque.';
      return {kind:'task',task,session:null,subjectId:task.subjectId,reason,minutes:availableMinutes&&duration?Math.min(duration,availableMinutes):0,partial,unknownDuration:!duration,requiresReview};
    }
    if(latest)return {kind:'resume',task:null,session:latest,subjectId:latest.subjectId,reason:'Retoma el intento más reciente de una asignatura activa y haz una comprobación propia antes de avanzar.'+(!availableMinutes?' Indica cuánto tiempo tienes hoy.':''),minutes:availableMinutes,partial:false,unknownDuration:true,requiresReview:false};
    return {kind:'empty',task:null,session:null,subjectId:null,reason:'Elige una asignatura, un ejercicio concreto y el tiempo disponible.',minutes:availableMinutes,partial:false,unknownDuration:true,requiresReview:false};
  }
  function preparation({minutes=0,exercise='',checkpoint=''}) {
    return `Tiempo disponible: ${minutes?minutes+' minutos':'pendiente de indicar; pregúntamelo antes de fijar el bloque.'}\nEnunciado o sección: ${exercise||'pendiente de aportar; pídelo antes de resolver.'}\nPunto de reanudación: ${checkpoint||'Recuperar el último intento propio y elegir una comprobación.'}\nAl retomar, empieza con una sola comprobación breve sobre este punto y espera mi respuesta antes de explicar o dar la solución. Si entiendo las partes pero me pierdo al unirlas, usa una traza pequeña o un ejemplo con menos datos y comprueba después el conjunto. Si el bloque queda a medias, conserva el punto exacto y no marques la tarea completa.`;
  }
  const closing='Al cerrar, registra lo que hice yo, la ayuda recibida, el resultado observado y el siguiente intento. Deja como desconocido lo que no se haya comprobado. Distingue declaración, práctica guiada y resolución autónoma; una casilla no confirma entrega ni dominio. No declares guardado en Obsidian sin acceso y verificación.';
  function preparationPlan({task,today,availability=[],checkpoint='',tasks=[]}) {
    if(!task||task.kind!=='exam'||!task.day)throw Error('Elige un examen con fecha vigente.');
    if(typeof today!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(today)||!Number.isFinite(Date.parse(today+'T12:00:00Z'))||new Date(today+'T12:00:00Z').toISOString().slice(0,10)!==today||new Set(availability.map(a=>a.day)).size!==availability.length)throw Error('Revisa los días disponibles: no pueden repetirse.');
    for(const a of availability)if(typeof a.day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(a.day)||!Number.isFinite(Date.parse(a.day+'T12:00:00Z'))||new Date(a.day+'T12:00:00Z').toISOString().slice(0,10)!==a.day||!Number.isInteger(a.minutes)||a.minutes<0||a.minutes>480||(a.minutes>0&&a.minutes<5))throw Error('Indica un día válido y 0 o entre 5 y 480 minutos.');
    const rows=availability.filter(a=>a.day>=today&&a.day<task.day&&Number.isInteger(a.minutes)&&a.minutes>=5&&a.minutes<=480).sort((a,b)=>a.day.localeCompare(b.day));
    const blocks=[],warnings=[];
    for(const row of rows){
      const planned=tasks.filter(t=>t.id!==task.id&&!t.done&&!t.archived&&t.day===row.day);
      const unknown=planned.filter(t=>!Number.isInteger(t.minutes)||t.minutes<5);
      if(unknown.length){warnings.push(row.day+': hay tareas sin duración estimada. Revisa su tiempo antes de añadir preparación ese día.');continue;}
      const used=planned.reduce((sum,t)=>sum+t.minutes,0),remaining=Math.max(0,row.minutes-used);
      if(used)warnings.push(row.day+': '+used+' min ya planificados de '+row.minutes+' min disponibles.'+(used>row.minutes?' Tu plan supera el tiempo que has indicado.':''));
      if(remaining<5)continue;
      blocks.push({day:row.day,minutes:remaining,plannedMinutes:used,title:blocks.length===0?'Diagnóstico y próximo intento':'Práctica y comprobación propia',detail:checkpoint||'Elige un ejercicio concreto y registra qué ayuda necesitas.'});
    }
    return {examId:task.id,requiresReview:true,warnings,missing:blocks.length?[]:[availability.length?'No hay tiempo libre estimado para nuevos bloques en los días indicados.':'Indica los días y minutos que tienes disponibles.'],blocks};
  }
  return {preparationPlan,fields,labels,preparation,closing,orderedSessions,recommend};
});
