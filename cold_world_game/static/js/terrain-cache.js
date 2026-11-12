export class TerrainCache extends EventTarget {
  constructor(config) {
    super();this.config=config;this.chunks=new Map();this.pending=new Map();this.sequence=0;this.geometry=0;this.epoch=0;
    this.worker=new Worker(new URL('./terrain-worker.js',import.meta.url),{type:'module'});
    this.worker.onmessage=({data})=>{const pending=this.pending.get(data.request);if(!pending)return;clearTimeout(pending.timer);this.pending.delete(data.request);if(data.error)pending.reject(new Error(data.error));else pending.resolve(data.records);};
    this.worker.onerror=event=>{event.preventDefault();this.fail();};
    this.worker.onmessageerror=()=>this.fail();
  }
  fail(){this.failed=true;for(const pending of this.pending.values()){clearTimeout(pending.timer);pending.reject(new Error('terrain_worker_failed'));}this.pending.clear();}
  close(){this.epoch++;this.worker.terminate();this.fail();}
  generate(chunk) {
    if(this.failed)return Promise.reject(new Error('terrain_worker_failed'));
    return new Promise((resolve,reject)=>{
      const request=++this.sequence,timer=setTimeout(()=>{this.pending.delete(request);reject(new Error('terrain_worker_timeout'));},10000);
      this.pending.set(request,{resolve,reject,timer});this.worker.postMessage({request,seed:this.config.seed,settings:this.config.profiles[String(chunk.version)],chunk});
    });
  }
  async update(patch) {
    if(!patch)return;
    const epoch=this.epoch;
    for(const identifier of patch.remove||[]){this.chunks.delete(identifier);this.geometry++;}
    const work=(patch.add||[]).map(async chunk=>{
      const prior=this.chunks.get(chunk.id);
      if(chunk.patch&&!prior)throw new Error('terrain_patch_without_base');
      const added=new Map(chunk.patch?prior.added:[]),removed=new Set(chunk.patch?prior.removed:[]);
      for(const identifier of chunk.remove){added.delete(identifier);removed.add(identifier);}
      for(const record of chunk.add){removed.delete(record.id);added.set(record.id,record);}
      const entry={...prior,...chunk,added,removed,records:prior?.records||[]};this.chunks.set(chunk.id,entry);
      entry.loading=prior?.loading||Promise.resolve(chunk.version>=18?this.generate(chunk):[]);
      const base=await entry.loading;
      if(epoch!==this.epoch||this.chunks.get(chunk.id)!==entry)return;
      const records=new Map(base.filter(record=>!removed.has(record.id)).map(record=>[record.id,record]));
      for(const record of added.values())records.set(record.id,record);
      entry.base=base;entry.records=[...records.values()];entry.ready=true;this.geometry++;
    });
    await Promise.all(work);
    if(epoch===this.epoch)this.dispatchEvent(new Event('change'));
  }
  decorate(state) {
    if(!state)return state;
    if(this.lastGeometry!==this.geometry||this.lastStates!==state.structure_states) {
      const states=new Map((state.structure_states||[]).map(record=>[record.id,record]));
      this.records=[...this.chunks.values()].flatMap(chunk=>chunk.records.map(record=>({...record,...states.get(record.id)})));
      this.lastGeometry=this.geometry;this.lastStates=state.structure_states;
    }
    if(this.sourceChunks!==state.chunks||this.chunkGeometry!==this.geometry){this.sourceChunks=state.chunks;this.chunkGeometry=this.geometry;this.readyChunks=state.chunks.filter(([horizontal,vertical])=>this.chunks.get(`${horizontal},${vertical}`)?.ready);}
    return {...state,structures:this.records||[],terrain_geometry:`${this.config.session}:${this.geometry}`,chunks:this.readyChunks};
  }
}
