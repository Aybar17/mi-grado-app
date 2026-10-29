/* Configuración explícita: ninguna nota ni consulta sale del equipo automáticamente. */
document.addEventListener('DOMContentLoaded', () => {
  viewMeta.conexiones = ['Herramientas para estudiar', 'Campus y chat', 'Elige dónde consultar tus clases y con qué chat preparar los ejercicios.'];
  const nav = document.querySelector('.nav'), button = document.createElement('button');
  button.dataset.view = 'conexiones'; button.innerHTML = '<span class="ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="15" cy="17" r="3" fill="currentColor"/></svg></span>Conexiones';
  button.addEventListener('click', () => showView('conexiones'));
  nav.insertBefore(button, nav.querySelector('details'));
  const view = document.createElement('section'); view.className = 'view'; view.id = 'conexiones';
  const style = document.createElement('style'); style.textContent = '[hidden]{display:none!important}#conexiones input,#conexiones select{max-width:100%;box-sizing:border-box}#conexiones .record select{margin-top:8px;width:100%}'; document.head.appendChild(style);
  view.innerHTML = `<div class="card"><h2>Configurar campus y chat</h2>
    <form id="connectionsForm" class="formgrid">
    <label>Centro de estudios<select id="connectionCenter" name="center"><option>UGR</option><option>Otra universidad</option><option>FP</option><option>Otro centro</option></select></label>
    <label>Chat para estudiar<select id="connectionChat" name="chat"><option value="chatgpt">ChatGPT</option><option value="claude">Claude</option><option value="gemini">Gemini</option></select></label>
    <label class="wide">Dirección del campus<input id="connectionCampus" name="campus_url" class="field" type="url" autocomplete="off" spellcheck="false" maxlength="1000" placeholder="https://campus.tu-centro.es…"></label>
    <button type="submit" class="btn primary">Guardar configuración</button></form>
    <p id="connectionsStatus" class="statusline" role="status"></p>
    <div class="actions"><a id="openCampus" class="btn" target="_blank" rel="noopener noreferrer" hidden>Abrir campus</a><a id="openChat" class="btn" target="_blank" rel="noopener noreferrer">Abrir chat</a></div>
    <p class="muted">Inicia sesión en la web de tu centro o de tu chat. Mi grado no solicita sus contraseñas. El chat se usa copiando el contexto desde Preparar sesión; su acceso gratuito tiene los límites del proveedor.</p></div>
    <div class="card" style="margin-top:20px"><h2>Importar fechas del campus</h2>
    <p>Descarga el calendario .ics de tu centro. Revisa sus fechas y elige la asignatura de cada evento antes de guardarlo.</p>
    <label>Archivo de calendario (hasta 65 KB)<input id="campusCalendar" name="calendar" type="file" accept=".ics,text/calendar"></label>
    <p id="calendarStatus" role="status" class="statusline"></p><div id="calendarPreview" class="history"></div>
    <button id="saveCalendar" class="btn primary" hidden>Guardar fechas seleccionadas</button>
    <p class="muted">Importación desde el archivo que aportas; no es sincronización automática ni confirma entregas realizadas. Los eventos recurrentes o sin fecha interpretable se señalan para revisión.</p></div>
    <div class="card" style="margin-top:20px"><h2>Responder con IA local</h2>
    <p>Opción adicional: Ollama abierto con un modelo ya descargado. Mi grado solo consulta el servidor local y excluye modelos cloud.</p>
    <button id="findLocalModels" class="btn">Comprobar modelos locales</button>
    <p id="localModelStatus" class="statusline" role="status">Puedes seguir usando el chat externo sin instalar Ollama.</p>
    <a href="https://ollama.com/download/windows" target="_blank" rel="noopener noreferrer">Página oficial de Ollama</a></div>`;
  const main = document.querySelector('main'); main.insertBefore(view, main.querySelector('.footer'));
  const session = document.querySelector('#sesion .session-layout');
  const study = document.createElement('div'); study.className = 'card'; study.style.marginTop = '20px';
  study.innerHTML = `<h2>Usar mi contexto</h2><div class="actions"><button id="copyOpenChat" class="btn primary">Copiar contexto y abrir mi chat</button></div>
    <details><summary>Consultar un modelo local dentro del panel</summary>
    <form id="localAIForm" class="formgrid"><label class="wide">Modelo descargado<select id="localModel"><option value="">Comprueba los modelos en Mis conexiones</option></select></label>
    <label class="wide">Mi pregunta<textarea id="localQuestion" maxlength="8000" rows="3" required></textarea></label>
    <label class="wide"><span><input id="localConsent" type="checkbox" required> Enviar el contexto visible y esta pregunta al modelo de este ordenador</span></label>
    <button class="btn primary" type="submit">Preguntar a mi IA local</button></form>
    <p id="localAIStatus" class="statusline" role="status"></p><pre id="localAIResponse" aria-live="polite"></pre>
    <p class="muted">La respuesta no se guarda como un intento propio. Registra después qué hiciste tú y qué ayuda recibiste.</p></details>`;
  session.parentNode.appendChild(study);
  let settings = D.connections || {}, calendar = null, calendarText = '', localModels = [];
  function fillSettings(value) {
    settings = value;
    document.getElementById('connectionCenter').value = value.center || 'Otro centro';
    document.getElementById('connectionChat').value = value.chat || 'chatgpt';
    document.getElementById('connectionCampus').value = value.campus_url || '';
    const campus = document.getElementById('openCampus');
    campus.hidden = !value.campus_url; campus.href = PanelCore.safeHref(value.campus_url) || '#';
    document.getElementById('openChat').href = (value.chats || {})[value.chat] || 'https://chatgpt.com/';
  }
  async function post(route, value, timeout = 30000) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(route, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(value), signal:controller.signal});
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'La operación no se ha confirmado.');
      return result;
    } finally { clearTimeout(timer); }
  }
  fillSettings(settings);
  document.getElementById('connectionsForm').addEventListener('submit', async event => {
    event.preventDefault();
    const status = document.getElementById('connectionsStatus');
    const submit = event.currentTarget.querySelector('button[type="submit"]');
    submit.disabled = true; status.className = 'statusline'; status.textContent = 'Guardando campus y chat…';
    try {
      fillSettings(await post('/api/settings', {center:document.getElementById('connectionCenter').value,
        chat:document.getElementById('connectionChat').value, campus_url:document.getElementById('connectionCampus').value}));
      status.textContent = 'Configuración guardada en este ordenador.';
    } catch (error) { status.className = 'statusline error'; status.textContent = 'No se ha guardado: ' + error.message + ' Revisa la dirección del campus y vuelve a guardar.'; document.getElementById('connectionCampus').focus(); }
    finally { submit.disabled = false; }
  });
  document.getElementById('copyOpenChat').addEventListener('click', async () => {
    const target = (settings.chats || {})[settings.chat] || 'https://chatgpt.com/';
    // Abrir por el gesto del usuario: evita bloqueos de ventanas después de await.
    const opened = window.open(target, '_blank', 'noopener,noreferrer');
    await copyText(document.getElementById('sessionPreview').value);
    if (!opened) toast('Contexto preparado. Si el chat no se abrió, usa Mis conexiones → Abrir mi chat.');
  });
  document.getElementById('campusCalendar').addEventListener('change', async event => {
    const status = document.getElementById('calendarStatus'), preview = document.getElementById('calendarPreview');
    calendar = null; preview.replaceChildren(); document.getElementById('saveCalendar').hidden = true;
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 65000) throw Error('El calendario debe ocupar como máximo 65 KB.');
      calendarText = await file.text(); calendar = await post('/api/calendar/preview', {content:calendarText});
      for (const item of calendar.events) {
        const row = document.createElement('label'); row.className = 'record';
        const title = document.createElement('span'); title.textContent = `${item.title} · ${item.date}${item.time ? ' ' + item.time : ''}`;
        const select = document.createElement('select'); select.dataset.calendarId = item.importId;
        select.setAttribute('aria-label', 'Asignatura para ' + item.title);
        select.add(new Option('No importar este evento', ''));
        for (const subject of D.subjects || []) select.add(new Option(subject.name, subject.id));
        row.append(title, document.createElement('br'), select); preview.appendChild(row);
      }
      status.textContent = `${calendar.events.length} eventos listos para revisar. ${calendar.issues.join(' ')}`;
      document.getElementById('saveCalendar').hidden = !calendar.events.length;
    } catch (error) { status.textContent = 'No se pudo revisar: ' + error.message; }
  });
  document.getElementById('saveCalendar').addEventListener('click', async event => {
    if (!calendar) return; event.target.disabled = true;
    try {
      const assignments = Object.fromEntries([...document.querySelectorAll('[data-calendar-id]')].filter(s => s.value).map(s => [s.dataset.calendarId, s.value]));
      const result = await post('/api/calendar/import', {content:calendarText, assignments, panelSha:calendar.panelSha});
      document.getElementById('calendarStatus').textContent = `${result.events} fechas guardadas. Contrasta los cambios posteriores en el campus.`;
      calendar = null; event.target.hidden = true; await syncLive();
    } catch (error) { document.getElementById('calendarStatus').textContent = 'Guardado pendiente: ' + error.message; }
    finally { event.target.disabled = false; }
  });
  document.getElementById('findLocalModels').addEventListener('click', async () => {
    const status = document.getElementById('localModelStatus'); status.textContent = 'Comprobando Ollama de este ordenador…';
    try {
      const result = await post('/api/local-ai/models', {}); localModels = result.models;
      const select = document.getElementById('localModel'); select.replaceChildren();
      for (const name of localModels) select.add(new Option(name, name));
      status.textContent = localModels.length ? `${localModels.length} modelos locales disponibles. Ya puedes consultarlos en Sesión IA.` : 'No hay modelos locales descargados. El chat externo sigue disponible.';
    } catch (error) { status.textContent = error.message; }
  });
  document.getElementById('localAIForm').addEventListener('submit', async event => {
    event.preventDefault(); const status = document.getElementById('localAIStatus'), submit = event.currentTarget.querySelector('button');
    if (!document.getElementById('localConsent').checked) return;
    if (!localModels.includes(document.getElementById('localModel').value)) { status.textContent = 'Primero comprueba tus modelos en Mis conexiones.'; return; }
    submit.disabled = true; status.textContent = 'El modelo local está preparando la respuesta…';
    try {
      const result = await post('/api/local-ai/chat', {model:document.getElementById('localModel').value,
        context:document.getElementById('sessionPreview').value, question:document.getElementById('localQuestion').value}, 115000);
      document.getElementById('localAIResponse').textContent = result.text;
      status.textContent = 'Respuesta de ' + result.model + '. Registra aparte tu intento y la ayuda recibida.';
    } catch (error) { status.textContent = 'Consulta sin respuesta confirmada: ' + error.message; }
    finally { submit.disabled = false; }
  });
  displayView(activeView());
});
