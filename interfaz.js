/* Avisos compartidos por el panel local y la web. También funcionan dentro de dialog. */
(function(){
  'use strict';let timer,host;
  function notify(value,error=false) {
    clearTimeout(timer);host?.remove();
    host=document.createElement('div');host.className='floating-notice'+(error?' is-error':'');
    host.setAttribute('aria-label',error?'Operación pendiente':'Confirmación');
    const text=document.createElement('p');text.setAttribute('role',error?'alert':'status');text.setAttribute('aria-live',error?'assertive':'polite');
    const close=document.createElement('button');close.type='button';close.textContent='Cerrar aviso';
    const dismiss=()=>{clearTimeout(timer);host?.remove();host=null;};close.addEventListener('click',dismiss);
    const parent=document.querySelector('dialog[open]')||document.body;parent.append(host);host.append(text,close);
    text.textContent=value;
    // Un error permanece hasta que se cierre. El temporizador se pausa al leer/interactuar.
    const expire=()=>{if(!error)timer=setTimeout(dismiss,12000);};expire();
    host.addEventListener('mouseenter',()=>clearTimeout(timer));host.addEventListener('focusin',()=>clearTimeout(timer));
    host.addEventListener('mouseleave',expire);host.addEventListener('focusout',expire);
    if(parent.tagName==='DIALOG')parent.addEventListener('close',()=>{if(host?.parentElement===parent)document.body.append(host);},{once:true});
  }
  window.StudyUI={notify};
})();
