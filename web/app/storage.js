'use strict';
function bookStorageError(error) {
  return Error(error?.name==='QuotaExceededError'?'No queda espacio para guardar el cuaderno. Conserva el texto de la revisión y descarga una copia antes de liberar espacio.':
    'El navegador no confirmó el guardado. Conserva el texto y descarga una copia antes de volver a intentarlo.');
}
window.BookStorage = {
  async open() {
    if (!window.indexedDB) throw Error('Este navegador no permite guardar el cuaderno. Usa Safari o Chrome fuera de la navegación privada.');
    return new Promise((resolve,reject)=>{
      const req=indexedDB.open('mi-grado-web',1);
      req.onupgradeneeded=()=>{req.result.createObjectStore('books');req.result.createObjectStore('history',{keyPath:'key'});};
      req.onerror=()=>reject(req.error);
      req.onblocked=()=>reject(Error('Cierra las otras pestañas de Mi grado y vuelve a intentarlo.'));
      req.onsuccess=()=>{const db=req.result;db.onversionchange=()=>db.close();resolve(db);};
    });
  },
  async load(db) {
    const raw=await new Promise((resolve,reject)=>{
      const tx=db.transaction('books','readonly'),req=tx.objectStore('books').get('current');
      req.onsuccess=()=>resolve(req.result || null);req.onerror=()=>reject(req.error);
    });
    if(!raw)return null;
    const clean=GradeBook.validate(raw);
    // La copia anterior y la conversión se escriben en una misma transacción.
    return raw.version!==clean.version?this.save(db,clean,raw,true):clean;
  },
  async save(db,next,expected,archive=false) {
    const clean=GradeBook.validate(next);
    return new Promise((resolve,reject)=>{
      const tx=db.transaction(['books','history'],'readwrite'),store=tx.objectStore('books'),req=store.get('current');
      let failure, saved;
      req.onsuccess=()=>{
        try{
        const old=req.result;
        if ((old && expected && (old.id!==expected.id || old.rev!==expected.rev)) || (old && !expected) || (!old && expected)) {
          failure=Error('Otra pestaña cambió el cuaderno. Recarga antes de guardar; tus cambios aún están en el formulario.');tx.abort();return;
        }
        if (old && (archive || old.id!==clean.id)) tx.objectStore('history').put({key:GradeBook.uid('copy'),createdAt:new Date().toISOString(),reason:old.version!==clean.version?'before-upgrade':typeof archive==='string'?archive:'before-restore',book:old});
        saved={...clean,rev:(old?.rev || 0)+1};store.put(saved,'current');
        }catch(error){failure=bookStorageError(error);tx.abort();}
      };
      tx.oncomplete=()=>resolve(saved);
      tx.onabort=()=>reject(failure || bookStorageError(tx.error));
      tx.onerror=event=>{failure ||= bookStorageError(event.target.error||tx.error);};
    });
  },
  async history(db) {
    return new Promise((resolve,reject)=>{const req=db.transaction('history','readonly').objectStore('history').getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
  },
  async exportInfo(db,bookId) {
    return new Promise((resolve,reject)=>{const req=db.transaction('books','readonly').objectStore('books').get('export:'+bookId);req.onsuccess=()=>resolve(req.result || null);req.onerror=()=>reject(req.error);});
  },
  async markExport(db,book) {
    const info={bookId:book.id,rev:book.rev,at:new Date().toISOString()};
    return new Promise((resolve,reject)=>{const tx=db.transaction('books','readwrite');tx.objectStore('books').put(info,'export:'+book.id);tx.oncomplete=()=>resolve(info);tx.onabort=()=>reject(tx.error);tx.onerror=()=>reject(tx.error);});
  }
};
