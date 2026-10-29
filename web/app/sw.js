'use strict';
const CACHE='mi-grado-web-v1';
const ASSETS=['./','index.html','app.css','identidad.css','flujo-estudio.js','interfaz.js','materiales-ui.js','PRIMER-USO.md','app.js','core.js','storage.js','manifest.webmanifest','icon-192.png','icon-512.png','INSTRUCCIONES-IA.md','GUIA-IA.md','mi-grado-obsidian-ia.zip','mi-grado-obsidian-ia-plugin.zip'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS.map(asset=>new Request(asset,{cache:'reload'})))).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('mi-grado-web-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin||!url.pathname.startsWith(new URL('./',self.location.href).pathname))return;
  // No se cachean notas, contexto ni respuestas: únicamente archivos estáticos enumerados.
  event.respondWith(caches.open(CACHE).then(cache=>cache.match(event.request)).then(hit=>hit||fetch(event.request)));
});
