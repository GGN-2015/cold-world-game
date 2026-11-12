import {plan,fingerprint} from './procedural.js';

let database;
const opening=new Promise(resolve=>{
  try {
    const request=indexedDB.open('cold-world-baselines-v1',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('chunks');
    request.onsuccess=()=>{database=request.result;resolve();};
    request.onerror=()=>resolve();request.onblocked=()=>resolve();
  }catch{resolve();}
});
async function read(key) {
  await opening;
  if(!database)return;
  return new Promise(resolve=>{try{const request=database.transaction('chunks').objectStore('chunks').get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve();}catch{resolve();}});
}
function write(key,value) {
  if(!database)return;
  try {
    const store=database.transaction('chunks','readwrite').objectStore('chunks');store.put(value,key);
    const count=store.count();count.onsuccess=()=>{let excess=count.result-512;if(excess<=0)return;const cursor=store.openCursor();cursor.onsuccess=()=>{const current=cursor.result;if(current&&excess-->0){current.delete();current.continue();}};};
  }catch{}
}
self.onmessage=async({data})=>{
  try {
    const {request,seed,settings,chunk}=data,key=`${settings.digest}:${seed}:${chunk.id}`;
    let records=await read(key),cached=Boolean(records);
    if(!Array.isArray(records)||fingerprint(records)!==chunk.hash){records=plan(seed,chunk.x,chunk.y,settings);cached=false;if(fingerprint(records)!==chunk.hash)throw new Error('terrain_fingerprint_mismatch');write(key,records);}
    self.postMessage({request,records,cached});
  }catch(error){self.postMessage({request:data.request,error:String(error.message)});}
};
