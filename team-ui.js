/* Propuesta aislada. No ejecuta agentes ni modifica Obsidian.
 * Integración: PanelTeamUI.mount(document.querySelector('#equipo'), {team, goals}, {singleView:true,onRefresh}).
 * Objetivos: patchHTML('#objetivosContenido', PanelTeamUI.goalsHTML(D.goals)).
 * Los datos deben proceder del registro real y contener solo resúmenes aprobados para este panel.
 */
(function (global) {
  'use strict';
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
  const text = value => typeof value === 'string' ? value : value?.title || value?.text || value?.name || '';
  const safeHref = value => {
    const url = String(value || '').trim();
    return /^(https?:|obsidian:|file:)/i.test(url) ? url : '';
  };
  const statusNames = {active:'En curso',complete:'Completado',blocked:'Pendiente de resolver',proposed:'Propuesto',prepared:'Encargo preparado',idle:'Sin trabajo en curso',paused:'Pausado',unknown:'Estado sin confirmar'};
  const groupNames = {head:'Cabeza de dominio',reviewer:'Revisor del dominio',support:'Apoyo especializado',cabeza:'Cabeza de dominio',revisor:'Revisor del dominio',secundario:'Apoyo especializado'};
  const knownStatus = status => Object.hasOwn(statusNames, status) ? status : 'unknown';
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
  const firstCount = (...values) => values.map(count).find(value=>value!==null) ?? null;
  const totalTokens = usage => firstCount(usage?.tokens,usage?.total,usage?.total_tokens);
  const tokenLabel = usage => totalTokens(usage)!==null ? totalTokens(usage).toLocaleString('es-ES')+' tokens registrados' : 'Tokens no disponibles';
  const referenceLabel = entry => typeof entry === 'string' ? entry : [entry?.title || entry?.name, entry?.source || entry?.path].filter(Boolean).join(' · ');
  const link = (label, url, extra = '') => safeHref(url) ? '<a href="'+esc(safeHref(url))+'" '+extra+'>'+esc(label)+'</a>' : '<span>'+esc(label)+'</span>';
  const paragraphs = value => list(value).filter(x => text(x)).map(x => '<p>'+esc(text(x))+'</p>').join('');
  function buildHandoff(role) {
    // No exporta literales de instrucciones, memoria ni entradas. Solo las referencias seleccionadas.
    const instructions = list(role.instructions).filter(x=>typeof x==='string'||x.exportable!==false).map(referenceLabel).filter(Boolean);
    const memory = list(role.memoryScope).filter(x=>typeof x==='string'||x.exportable!==false).map(referenceLabel).filter(Boolean);
    const inputs = list(role.inputs).filter(x => typeof x === 'string' || x.exportable !== false).map(referenceLabel).filter(Boolean);
    return [
      'Encargo preparado para '+(role.name || role.id)+'.',
      'Rol: '+(groupNames[role.group] || 'Rol registrado')+' · dominio: '+(role.domain || 'sin indicar')+'.',
      'Tarea: '+(role.task || 'Concretar la tarea con el usuario antes de actuar.'),
      'Resultado esperado: '+(role.expectedOutcome || 'Un resultado revisable con su evidencia y pendientes.'),
      'Entradas autorizadas: '+(inputs.join('; ') || 'pendiente de seleccionar.'),
      'Instrucciones registradas: '+(instructions.join('; ') || 'sin lectura registrada.'),
      'Memoria pertinente: '+(memory.join('; ') || 'sin consulta registrada; recuperar solo lo necesario.'),
      'Revisión: '+(role.reviewer || 'pendiente de asignar un revisor del mismo dominio')+'.',
      'Comprueba que esas fuentes están disponibles y vigentes. Conserva el alcance de la evidencia.',
      'Distingue propuesta, acción realizada, resultado comprobado y objeciones pendientes.',
      'No incluyas credenciales ni contenidos privados en el resultado o el registro de uso.'
    ].join('\n');
  }
  const css = `
    .team-shell{min-width:0}.team-tabs{display:flex;gap:6px;border-bottom:1px solid var(--line,#dce3d9);margin-bottom:22px}.team-tabs button{padding:11px 16px;min-height:44px;border:0;border-bottom:3px solid transparent;background:transparent;color:var(--sub,#637168);font-weight:650}.team-tabs button[aria-selected=true]{border-bottom-color:var(--green,#235b45);color:var(--green,#235b45)}.team-shell [hidden]{display:none!important}.team-overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}.team-overview .card{padding:16px}.team-overview b{display:block;font-size:25px;line-height:1.3}.team-overview span{font-size:12px;color:var(--sub,#637168)}.team-tools{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin:18px 0}.team-tools label{display:grid;gap:5px;font-size:12px;min-width:180px}.team-tools select{min-height:44px}.team-source{font-size:12px;color:var(--sub,#637168);overflow-wrap:anywhere}.team-domain{margin:25px 0}.team-domain>h2{font-size:20px;margin:0 0 12px}.team-roles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.team-role{min-width:0}.team-role h3{font-size:17px;margin:0}.team-role .row{align-items:start;flex-wrap:wrap}.team-role .team-task{margin:14px 0;font-size:14px}.team-role .badge{font-size:11px}.team-role dl{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;font-size:12px;margin:12px 0}.team-role dt{color:var(--sub,#637168)}.team-role dd{margin:0;overflow-wrap:anywhere}.team-role details{border-top:1px solid var(--line,#dce3d9);padding-top:10px}.team-role ul{padding-left:20px;font-size:13px}.team-role li{margin:8px 0;overflow-wrap:anywhere}.team-role .team-empty{font-size:12px;color:var(--sub,#637168)}.team-review{border-left:3px solid #d6b258;padding-left:12px;margin-top:10px}.team-review b{font-size:13px}.team-review p{font-size:12px;margin:6px 0}.team-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.team-actions .btn{min-height:44px}.team-composer{margin:18px 0}.team-composer textarea{width:100%;min-height:220px;resize:vertical;font-size:13px}.team-composer .team-edited{font-size:12px;color:var(--sub,#637168)}.team-goals{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px}.team-goal h3{margin:0 0 8px}.team-goal .team-next{padding:12px;background:var(--mint,#e4efe4);border-radius:8px;font-size:13px;margin-top:14px}.team-goal .team-next.proposed{background:var(--amber,#fcf1d7)}.team-goal .team-next b{display:block;margin-bottom:5px}.team-role button:focus-visible,.team-tabs button:focus-visible,.team-shell a:focus-visible,.team-shell select:focus-visible,.team-shell textarea:focus-visible{outline:3px solid #80a46c;outline-offset:3px}.team-unavailable{padding:17px;border:1px dashed #ced7c8;border-radius:10px;color:var(--sub,#637168);font-size:13px}.team-meta{font-size:12px;color:var(--sub,#637168)}
    @media(max-width:1100px){.team-roles{grid-template-columns:1fr}}
    @media(max-width:700px){.team-overview{grid-template-columns:1fr;gap:10px}.team-overview .card{display:flex;align-items:center;gap:12px}.team-overview b{font-size:23px}.team-tools{align-items:stretch;gap:10px}.team-tools label{width:100%}.team-goals{grid-template-columns:1fr}.team-role dl{grid-template-columns:1fr;gap:2px}.team-role dd{margin-bottom:7px}.team-tabs{overflow:auto}.team-tabs button{white-space:nowrap;padding:11px 13px}.team-composer textarea{min-height:280px}}
    @media print{.team-tabs,.team-tools,.team-actions,.team-composer{display:none}.team-roles,.team-goals{grid-template-columns:1fr}.team-role{break-inside:avoid}}
  `;
  function instructionsHTML(role) {
    const entries = list(role.instructions);
    const memory = list(role.memoryScope);
    return '<details data-team-detail="instructions-'+esc(role.id)+'"><summary>Ver instrucciones y memoria usadas</summary>'+
      '<p class="team-meta">Lecturas registradas para este encargo. La disponibilidad de un archivo no confirma su lectura.</p>'+
      '<h4>Instrucciones</h4>'+(entries.length ? '<ul>'+entries.map(item => '<li>'+link(referenceLabel(item), item?.url)+(typeof item==='object'?'<br><span class="team-meta">'+esc(item.applied || 'Aplicación sin registrar')+'</span>':'')+'</li>').join('')+'</ul>' : '<p class="team-empty">Sin instrucciones consultadas registradas.</p>')+
      '<h4>Memoria pertinente</h4>'+(memory.length ? '<ul>'+memory.map(item => '<li>'+link(referenceLabel(item),item?.url)+(typeof item==='object'?'<br><span class="team-meta">'+esc(item.scope || 'Alcance sin indicar')+'</span>':'')+'</li>').join('')+'</ul>' : '<p class="team-empty">Sin consulta de memoria registrada.</p>')+'</details>';
  }
  function activityHTML(role) {
    const actions = list(role.actions), artifacts = list(role.artifacts);
    return '<details data-team-detail="activity-'+esc(role.id)+'"><summary>Acciones y resultados · '+actions.length+' acciones registradas</summary>'+
      (actions.length ? '<ul>'+actions.map(item => '<li><strong>'+esc(text(item))+'</strong>'+ (typeof item === 'object' ? '<br><span class="team-meta">'+esc([item.status || 'estado sin indicar',item.at,item.source].filter(Boolean).join(' · '))+'</span>'+paragraphs(item.result) : '')+'</li>').join('')+'</ul>' : '<p class="team-empty">Todavía no hay acciones realizadas en el registro.</p>')+
      '<h4>Resultados revisables</h4>'+(artifacts.length ? '<ul>'+artifacts.map(item => '<li>'+link(text(item) || 'Abrir resultado',item?.url)+'<br><span class="team-meta">'+esc(item?.validation || 'Validación pendiente de registrar')+'</span></li>').join('')+'</ul>' : '<p class="team-empty">Sin resultados publicados en el registro.</p>')+'</details>';
  }
  function reviewsHTML(role, roles) {
    const reviewer = roles.find(item => item.id === role.reviewer);
    const rebuttals = list(role.rebuttals);
    const sameDomain = reviewer && reviewer.domain === role.domain && ['reviewer','revisor'].includes(reviewer.group);
    return '<details data-team-detail="reviews-'+esc(role.id)+'"><summary>Revisión y objeciones · '+rebuttals.length+'</summary>'+
      '<p class="team-meta">'+esc(reviewer ? (sameDomain ? 'Revisor del mismo dominio: ' : 'Asignación pendiente de corregir: ')+(reviewer.name || reviewer.id) : 'Sin revisor del mismo dominio registrado.')+'</p>'+
      (rebuttals.length ? rebuttals.map(item => '<div class="team-review"><b>'+esc(item.title || text(item))+'</b><p>'+esc(item.critique || '')+'</p><p class="team-meta">'+esc([item.status || 'Respuesta pendiente',item.author,item.at].filter(Boolean).join(' · '))+'</p>'+(item.response?'<p><strong>Respuesta:</strong> '+esc(item.response)+'</p>':'')+(item.resolution?'<p><strong>Resolución:</strong> '+esc(item.resolution)+'</p>':'')+(item.evidence?'<p>'+link('Ver evidencia de la resolución',item.evidence)+'</p>':'')+'</div>').join('') : '<p class="team-empty">Sin revisión realizada registrada. Asignar revisor no confirma una revisión.</p>')+'</details>';
  }
  function roleHTML(role, roles) {
    const status = knownStatus(role.status);
    const cls = status === 'complete' ? 'ok' : status === 'blocked' || status === 'unknown' ? 'warn' : '';
    const usage = role.usage || {};
    const counters=[['Entrada total',firstCount(usage.input,usage.input_tokens)],['De ella, en caché',firstCount(usage.cache,usage.cached_input_tokens)],['Salida total',firstCount(usage.output,usage.output_tokens)],['De ella, razonamiento',firstCount(usage.reasoningTokens,usage.reasoning_output_tokens)]];
    return '<article data-team-group="'+esc(role.group)+'" class="card team-role"><div class="row"><div><span class="team-meta">'+esc(groupNames[role.group] || 'Rol registrado')+'</span><h3>'+esc(role.name || role.id)+'</h3></div><span class="badge '+cls+'">'+esc(statusNames[status])+'</span></div>'+
      '<p class="team-task"><strong>Encargo:</strong> '+esc(role.task || 'Sin encargo registrado.')+'</p>'+
      '<dl><dt>Modelo</dt><dd>'+esc(usage.model || 'Sin dato verificable')+'</dd><dt>Razonamiento</dt><dd>'+esc(usage.reasoning || 'heredado')+'</dd><dt>Uso total</dt><dd>'+esc(tokenLabel(usage))+'</dd>'+counters.filter(([,value])=>value!==null).map(([label,value])=>'<dt>'+esc(label)+'</dt><dd>'+value.toLocaleString('es-ES')+'</dd>').join('')+'</dl>'+
      '<p class="team-meta">'+esc(usage.source ? 'Fuente del uso: '+usage.source : 'El uso se muestra solo cuando existe un registro verificable.')+'</p>'+
      (counters.some(([,value])=>value!==null)?'<p class="team-meta">La caché está incluida en la entrada. Los tokens de razonamiento están incluidos en la salida. Contadores acumulados de esta sesión, sin convertirlos en coste.</p>':'')+
      activityHTML(role)+reviewsHTML(role,roles)+instructionsHTML(role)+
      '<div class="team-actions"><button type="button" class="btn small" data-team-prepare="'+esc(role.id)+'">Preparar encargo</button></div></article>';
  }
  function goalsHTML(goals) {
    const data = goals || {}, items = list(data.items), note = data.note || data.source || {};
    const sourceAvailable = Boolean(note.url || note.path);
    return '<div class="card"><div class="row"><h2 class="sectiontitle" style="margin:0">Objetivos en Obsidian</h2>'+(safeHref(note.url)?link('Editar objetivos en Obsidian ↗',note.url,'class="btn small"'):'')+'</div>'+
      '<p>La nota canónica conserva tus decisiones. El panel muestra lo que se ha podido leer con fecha y fuente.</p>'+
      '<p class="team-source">'+esc(sourceAvailable ? 'Nota: '+(note.title || note.path || note.url)+' · '+(data.available?'fuente recuperada · ':'')+'lectura: '+(data.readAt || 'fecha sin registrar') : 'La nota de objetivos todavía no está disponible para esta vista.')+'</p>'+
      (note.modifiedAt?'<p class="team-meta">Edición del archivo: '+esc(note.modifiedAt)+'. Esta fecha no confirma un avance.</p>':'')+
      (data.unavailableReason?'<p class="team-meta">'+esc(data.unavailableReason)+'</p>':'')+(list(data.issues).length?'<ul class="team-meta">'+list(data.issues).map(issue=>'<li>'+esc(text(issue))+'</li>').join('')+'</ul>':'')+'</div>'+
      (items.length ? '<div class="team-goals">'+items.map(goal => {
        const next=goal.nextStep || {text:goal.next,kind:'proposed'}, done=next.kind==='done';
        return '<article class="card team-goal"><div class="row"><h3>'+esc(goal.title || 'Objetivo sin título')+'</h3><span class="badge">'+esc(goal.status || 'Estado sin confirmar')+'</span></div>'+paragraphs(goal.description || goal.purpose)+
          '<p class="team-meta">'+esc([goal.area,goal.priority?'Prioridad: '+goal.priority:''].filter(Boolean).join(' · '))+'</p>'+
          '<p class="team-source">Origen registrado: '+esc(goal.statementSource || goal.origin || 'sin aportar')+(goal.date?' · '+esc(goal.date):'')+'</p>'+
          (goal.evidence?'<details data-team-detail="goal-'+esc(goal.id)+'"><summary>Evidencia y alcance</summary>'+paragraphs(goal.evidence)+'</details>':'')+
          (next.text?'<div class="team-next '+(done?'':'proposed')+'"><b>'+(done?'Paso realizado registrado':'Siguiente paso propuesto')+'</b>'+esc(next.text)+(done?'<p class="team-meta">'+esc(next.evidence || 'Falta aportar evidencia del resultado.')+'</p>':'')+'</div>':'<p class="team-meta">Siguiente paso pendiente de concretar.</p>')+
          (goal.indicator?'<p class="team-meta">Indicador registrado: '+esc(goal.indicator)+'</p>':'')+
          (list(goal.milestones).length?'<details data-team-detail="milestones-'+esc(goal.id)+'" data-detail-key="goal-milestones-'+esc(goal.id)+'"><summary>Pasos de la nota · '+list(goal.milestones).length+'</summary><ul>'+list(goal.milestones).map(step=>'<li>'+esc(step.title)+'<br><span class="team-meta">'+(step.done?'Marcado como realizado en la nota; alcance por contrastar.':'Pendiente en la nota.')+'</span></li>').join('')+'</ul></details>':'')+
          (goal.dueAt || goal.deadline?'<p class="team-meta">Plazo registrado: '+esc(goal.dueAt || goal.deadline)+(goal.dueSource?' · '+esc(goal.dueSource):'')+'</p>':'')+'</article>';
      }).join('')+'</div>' : '<div class="team-unavailable" style="margin-top:18px">'+esc(data.emptyMessage || 'No hay objetivos recuperados. Abre la nota canónica y concreta solo lo que quieras mantener como compromiso.')+'</div>');
  }
  function mount(root, initialData, options) {
    if (!root) throw Error('Falta el contenedor de la vista Equipo IA.');
    const lifecycle=new AbortController(); const listen=(type,callback)=>root.addEventListener(type,callback,{signal:lifecycle.signal});
    const opts=options || {}, state={data:initialData || {},tab:'agents',domain:'',group:'',drafts:new Map(),role:null};
    const teamData=data=>data?.team || data || {};
    const signature=data=>JSON.stringify({team:teamData(data),goals:opts.singleView?null:data?.goals});
    let lastDataSignature=signature(state.data);
    let style=document.getElementById('panel-team-ui-style');
    if(!style){style=document.createElement('style');style.id='panel-team-ui-style';style.textContent=css+(global.PanelDesignCSS||'');document.head.appendChild(style);}
    root.classList.add('team-shell');
    function announce(message) {const node=root.querySelector('[data-team-status]');if(node)node.textContent=message;}
    function render() {
      const open=new Set(Array.from(root.querySelectorAll('[data-team-detail][open]')).map(node=>node.dataset.teamDetail));
      const active=document.activeElement, focusKey=root.contains(active)?active.id || active.dataset.teamPrepare:null;
      const selection=active?.tagName==='TEXTAREA'?{start:active.selectionStart,end:active.selectionEnd,scroll:active.scrollTop}:null;
      const team=teamData(state.data),roles=list(team.roles),domains=[...new Set(roles.map(role=>role.domain || 'Sin dominio'))];
      if(state.domain && !domains.includes(state.domain))state.domain='';
      const filtered=roles.filter(role=>(!state.domain || (role.domain || 'Sin dominio')===state.domain)&&(!state.group || role.group===state.group));
      const actions=roles.flatMap(role=>list(role.actions));
      const unresolved=roles.flatMap(role=>list(role.rebuttals)).filter(item=>!(['resolved','resuelta','descartada'].includes(item.status)&&Boolean(item.resolution)&&Boolean(item.evidence))).length;
      const source=team.source || state.data.source || {};
      root.innerHTML=(opts.singleView?'':'<div class="team-tabs" role="tablist" aria-label="Equipo y objetivos"><button type="button" id="teamTabAgents" role="tab" aria-controls="teamAgentsPanel" aria-selected="'+(state.tab==='agents')+'" tabindex="'+(state.tab==='agents'?'0':'-1')+'" data-team-tab="agents">Equipo IA</button><button type="button" id="teamTabGoals" role="tab" aria-controls="teamGoalsPanel" aria-selected="'+(state.tab==='goals')+'" tabindex="'+(state.tab==='goals'?'0':'-1')+'" data-team-tab="goals">Objetivos de Obsidian</button></div>')+
        '<div id="teamAgentsPanel" '+(opts.singleView?'':'role="tabpanel" aria-labelledby="teamTabAgents" tabindex="0"')+' '+(state.tab==='agents'?'':'hidden')+'><p class="sub">Cada dominio reúne a su responsable, un revisor que pueda objetar y los apoyos utilizados. El registro conserva encargos, acciones, resultados y pendientes.</p><p class="team-source">'+esc([typeof source==='string'?source:source.label || 'Registro de trabajo',(source.updatedAt || team.snapshot)? 'actualizado '+(source.updatedAt || team.snapshot):'fecha de actualización sin confirmar',source.scope || team.scope].filter(Boolean).join(' · '))+'</p>'+
        (list(team.issues).length?'<ul class="team-meta">'+list(team.issues).map(issue=>'<li>'+esc(text(issue))+'</li>').join('')+'</ul>':'')+
        '<div class="team-overview"><div class="card"><b>'+roles.length+'</b><span>roles registrados</span></div><div class="card"><b>'+actions.length+'</b><span>acciones en el registro</span></div><div class="card"><b>'+unresolved+'</b><span>objeciones pendientes de resolver</span></div></div>'+
        '<div class="team-tools"><label>Filtrar por dominio<select id="teamDomain"><option value="">Todos los dominios</option>'+domains.map(domain=>'<option value="'+esc(domain)+'" '+(domain===state.domain?'selected':'')+'>'+esc(domain)+'</option>').join('')+'</select></label><label>Tipo de agente<select id="teamGroup"><option value="">Cabezas, revisores y apoyos</option>'+Object.entries(groupNames).filter(([id])=>['head','reviewer','support'].includes(id)).map(([id,label])=>'<option value="'+esc(id)+'" '+(id===state.group?'selected':'')+'>'+esc(label)+'</option>').join('')+'</select></label>'+(typeof opts.onRefresh==='function'?'<button type="button" class="btn small" id="teamRefresh">Actualizar registro</button>':'')+'</div><div id="teamComposer" class="card team-composer" '+(state.role?'':'hidden')+'></div>'+
        (filtered.length ? domains.filter(domain=>!state.domain || domain===state.domain).map(domain=>'<section class="team-domain"><h2>'+esc(domain)+'</h2><div class="team-roles">'+filtered.filter(role=>(role.domain || 'Sin dominio')===domain).map(role=>roleHTML(role,roles)).join('')+'</div></section>').join('') : '<div class="team-unavailable">No hay agentes con trabajo registrado en este ámbito. Un encargo preparado aparecerá como propuesta hasta que exista actividad verificable.</div>')+'</div>'+
        (opts.singleView?'':'<div id="teamGoalsPanel" role="tabpanel" aria-labelledby="teamTabGoals" tabindex="0" '+(state.tab==='goals'?'':'hidden')+'>'+goalsHTML(state.data.goals)+'</div>')+'<p class="statusline" role="status" data-team-status></p>';
      root.querySelectorAll('[data-team-detail]').forEach(node=>{if(open.has(node.dataset.teamDetail))node.open=true;});
      if(state.role)renderComposer(false);
      if(focusKey){const node=Array.from(root.querySelectorAll('[id],[data-team-prepare]')).find(el=>el.id===focusKey || el.dataset.teamPrepare===focusKey);if(node){node.focus({preventScroll:true});if(selection && node.tagName==='TEXTAREA'){node.setSelectionRange(selection.start,selection.end);node.scrollTop=selection.scroll;}}}
    }
    function renderComposer(focus) {
      const role=list(teamData(state.data).roles).find(item=>item.id===state.role),container=root.querySelector('#teamComposer');
      if(!role || !container)return;
      const existing=state.drafts.get(role.id);const draft=existing?.edited?existing:{text:buildHandoff(role),edited:false};state.drafts.set(role.id,draft);
      container.hidden=false;
      container.innerHTML='<h3>Encargo para '+esc(role.name || role.id)+'</h3><p class="muted">Revisa este resumen antes de copiarlo al chat. Prepararlo no inicia ni reanuda agentes.</p><label for="teamHandoff" class="team-meta">Texto del encargo</label><textarea id="teamHandoff">'+esc(draft.text)+'</textarea><p class="team-edited">'+(draft.edited?'Tu edición se conserva para este rol.':'Se incluyen referencias y resúmenes; no se exportan literales de memoria.')+'</p><div class="team-actions"><button type="button" class="btn primary" id="teamCopy">Copiar encargo</button><button type="button" class="btn" id="teamCloseComposer">Cerrar</button></div>';
      if(focus)container.querySelector('textarea').focus({preventScroll:true});
    }
    listen('input',event=>{if(event.target.id==='teamHandoff' && state.role){state.drafts.set(state.role,{text:event.target.value,edited:true});root.querySelector('.team-edited').textContent='Tu edición se conserva para este rol.';}});
    listen('change',event=>{if(event.target.id==='teamDomain'){state.domain=event.target.value;render();}else if(event.target.id==='teamGroup'){state.group=event.target.value;render();}});
    listen('keydown',event=>{
      const tab=event.target.closest('[data-team-tab]');if(!tab)return;
      const keys=['ArrowLeft','ArrowRight','Home','End'];if(!keys.includes(event.key))return;event.preventDefault();
      const target=event.key==='Home'?'agents':event.key==='End'?'goals':state.tab==='agents'?'goals':'agents';state.tab=target;render();root.querySelector('[data-team-tab="'+target+'"]').focus();
    });
    listen('click',async event=>{
      const tab=event.target.closest('[data-team-tab]'),prepare=event.target.closest('[data-team-prepare]');
      if(tab){state.tab=tab.dataset.teamTab;render();root.querySelector('[data-team-tab="'+state.tab+'"]').focus();}
      else if(prepare){state.role=prepare.dataset.teamPrepare;renderComposer(true);}
      else if(event.target.id==='teamCloseComposer'){const former=state.role;state.role=null;render();root.querySelectorAll('[data-team-prepare]').forEach(node=>{if(node.dataset.teamPrepare===former)node.focus({preventScroll:true});});}
      else if(event.target.id==='teamCopy'){const field=root.querySelector('#teamHandoff');try{await navigator.clipboard.writeText(field.value);announce('Encargo copiado. Revísalo y pégalo en el chat.');}catch(error){field.focus();field.select();announce('Texto seleccionado. Copia con Ctrl+C o la opción Copiar de tu dispositivo.');}}
      else if(event.target.id==='teamRefresh'){const button=event.target;button.disabled=true;announce('Consultando el registro…');try{const fresh=await opts.onRefresh();if(fresh)state.data=fresh;render();announce('Registro consultado. Los borradores preparados se conservan.');}catch(error){announce('La lectura no se ha confirmado. Se conserva el registro anterior.');}finally{const current=root.querySelector('#teamRefresh');if(current)current.disabled=false;}}
    });
    render();
    return {update(data){const next=data || {},nextSignature=signature(next);if(nextSignature===lastDataSignature)return;state.data=next;lastDataSignature=nextSignature;render();},destroy(){lifecycle.abort();root.replaceChildren();}};
  }
  const api={mount,goalsHTML,buildHandoff,tokenLabel,safeHref,css};
  global.PanelTeamUI=api;
  if(typeof module!=='undefined' && module.exports)module.exports=api;
})(typeof window==='undefined'?globalThis:window);
