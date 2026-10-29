/* Vista local: registros verificados y estimaciones etiquetadas. Sin llamadas a IA. */
const PanelExtra=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=value=>Number.isFinite(value)?value.toLocaleString('es-ES'):'Sin registro';
  const safe=value=>/^(https?:|obsidian:)/i.test(String(value||''))?value:'';
  let teamInstance=null,modelData=null;
  function tokenUsage(d){
    const rows=(d.team?.roles||[]).filter(r=>r.usage&&Number.isSafeInteger(r.usage.input));
    const total=rows.reduce((v,r)=>{for(const key of ['input','cache','output','reasoningTokens'])v[key]+=(r.usage[key]||0);return v;},{input:0,cache:0,output:0,reasoningTokens:0});
    const max=Math.max(1,...rows.map(r=>r.usage.input));
    return '<details class="card" data-detail-key="token-usage"><summary><strong>Uso real de esta revisión · '+num(total.input)+' tokens de entrada</strong></summary><p>Contadores acumulados de las sesiones registradas. Entrada cacheada: '+num(total.cache)+' (incluida en entrada). Salida: '+num(total.output)+'; razonamiento: '+num(total.reasoningTokens)+' (incluido en salida).</p><p class="muted">La entrada incluye instrucciones y contexto enviados de nuevo en los pasos del agente. Estos contadores no son palabras nuevas ni equivalen al gasto de tu plan Plus. Corte: '+esc(d.team?.usageAt||'sin fecha')+'. El chat principal queda fuera de esta suma.</p><div class="usage-list">'+(rows.length?rows.map(r=>'<div class="usage-row"><strong>'+esc(r.name)+'</strong><div class="usage-track" aria-hidden="true"><span style="width:'+Math.max(1,100*r.usage.input/max).toFixed(2)+'%"><i style="width:'+Math.min(100,100*r.usage.cache/Math.max(1,r.usage.input)).toFixed(2)+'%"></i></span></div><small>'+num(r.usage.input)+' entrada · '+num(r.usage.cache)+' reutilizada · '+num(r.usage.output)+' salida</small></div>').join(''):'<p>No hay contadores por agente disponibles. No se presentan como cero.</p>')+'</div><p class="muted">La parte clara representa entrada reutilizada dentro de cada barra de entrada. El modelo y la intensidad efectivos figuran en cada tarjeta.</p></details>';
  }
  function modelHTML(models){
    return '<div class="card"><h2>Elegir el modelo para cada trabajo</h2><p>'+esc(models.scope)+'</p><label for="modelPurpose">Qué quieres hacer<select id="modelPurpose">'+models.recommendations.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.task)+'</option>').join('')+'</select></label><div id="modelRecommendation" class="review-warning" style="margin:15px 0"></div><details data-detail-key="api-estimate"><summary>Comparar un escenario de API · estimación</summary><p>'+esc(models.rateScope)+'</p><div class="formgrid"><label>Entrada total de una solicitud<input id="apiInput" type="number" min="0" max="272000" value="10000"></label><label>Entrada cacheada, incluida en total<input id="apiCached" type="number" min="0" max="272000" value="0"></label><label>Salida total, incluido razonamiento<input id="apiOutput" type="number" min="0" max="128000" value="2000"></label></div><div id="apiEstimate" role="status"></div></details><p class="muted">Más intensidad suele aumentar el trabajo y puede consumir más uso. No existe un multiplicador fijo por nivel. Reserva Max/Ultra para tareas difíciles; para estudiar un ejercicio no hace falta convocar al equipo completo.</p><p>'+models.sources.map(s=>'<a href="'+esc(safe(s.url))+'">'+esc(s.title)+'</a>').join(' · ')+'</p></div>';
  }
  function updateRecommendation(){
    const choice=modelData?.recommendations.find(r=>r.id===document.querySelector('#modelPurpose')?.value);if(!choice)return;
    document.querySelector('#modelRecommendation').innerHTML='<strong>'+esc(choice.model)+' · '+esc(choice.effort)+'</strong><p>'+esc(choice.why)+'</p>';
  }
  function estimate(){
    const values=['apiInput','apiCached','apiOutput'].map(id=>Number(document.querySelector('#'+id).value));
    const [input,cache,output]=values,node=document.querySelector('#apiEstimate');
    if(!values.every(x=>Number.isSafeInteger(x)&&x>=0)||input>272000||output>128000||cache>input){node.textContent='Usa enteros válidos; la entrada reutilizada no puede superar la entrada total. Este escenario admite hasta 272K de entrada y 128K de salida.';return;}
    node.innerHTML='<div class="grid2">'+modelData.rates.map(rate=>'<p><strong>'+esc(rate.model)+'</strong><br>'+new Intl.NumberFormat('es-ES',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4}).format(((input-cache)*rate.input+cache*rate.cached+output*rate.output)/1000000)+' por esta solicitud ficticia<br><a href="'+esc(safe(rate.url))+'">Tarifas oficiales ↗</a></p>').join('')+'</div>';
  }
  function feedback(d){
    const data=d.team||{},items=data.feedback||[];
    return '<div class="card"><h2>Qué mejorar después</h2><p>Decisiones de la revisión. Una propuesta no se presenta como función terminada ni como mejora de notas demostrada.</p>'+items.map(item=>'<details data-detail-key="feedback-'+esc(item.id)+'"><summary>'+esc(item.title)+' · '+esc(item.status)+'</summary><p>'+esc(item.detail)+'</p><p class="muted">Próxima comprobación: '+esc(item.check||'por definir')+'</p></details>').join('')+'<h3>Referentes consultados</h3><div class="reference-grid">'+(data.references||[]).map(item=>'<article><a href="'+esc(safe(item.url))+'">'+esc(item.title)+'</a><p>'+esc(item.transfer)+'</p><small>'+esc(item.verification)+'</small></article>').join('')+'</div><p class="muted">'+esc(data.researchLimit||'No hay investigación incorporada todavía.')+'</p><details data-detail-key="skills"><summary>Skills guardadas y uso real</summary><ul>'+(data.skills||[]).map(item=>'<li><strong>'+esc(item.name)+'</strong> · '+esc(item.use)+'<br><a href="'+esc(safe(item.url))+'">Procedencia ↗</a></li>').join('')+'</ul></details></div>';
  }
  function render(d){
    if(!teamInstance)teamInstance=PanelTeamUI.mount(document.querySelector('#teamRoot'),{team:d.team},{singleView:true});else teamInstance.update({team:d.team});
    const snapshot=document.querySelector('#teamSnapshot');snapshot.textContent=d.team?.snapshot?'Revisión registrada: '+d.team.snapshot+' · no es un monitor de agentes en segundo plano.':'No hay una ejecución del equipo registrada en esta instalación.';
    patchHTML('#goalsRoot',PanelTeamUI.goalsHTML(d.goals));patchHTML('#teamUsage',tokenUsage(d));patchHTML('#projectFeedback',feedback(d));
    if(!modelData&&d.models){modelData=d.models;patchHTML('#modelGuide',modelHTML(modelData));document.querySelector('#modelPurpose').addEventListener('change',updateRecommendation);['apiInput','apiCached','apiOutput'].forEach(id=>document.querySelector('#'+id).addEventListener('input',estimate));updateRecommendation();estimate();}
  }
  return {render};
})();
