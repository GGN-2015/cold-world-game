const rotations=[7,12,17,22,5,9,14,20,4,11,16,23,6,10,15,21];
const constants=Array.from({length:64},(_,index)=>Math.floor(Math.abs(Math.sin(index+1))*4294967296)>>>0);
const encoder=new TextEncoder();

export function md5(text) {
  const bytes=encoder.encode(text), size=Math.ceil((bytes.length+9)/64)*64, buffer=new Uint8Array(size);
  buffer.set(bytes);buffer[bytes.length]=128;
  const view=new DataView(buffer.buffer);view.setUint32(size-8,bytes.length*8,true);view.setUint32(size-4,Math.floor(bytes.length/536870912),true);
  const state=[0x67452301,0xefcdab89,0x98badcfe,0x10325476];
  for(let offset=0;offset<size;offset+=64) {
    let [first,second,third,fourth]=state;
    for(let index=0;index<64;index++) {
      const group=index>>>4;
      const value=group===0?(second&third)|(~second&fourth):group===1?(fourth&second)|(~fourth&third):group===2?second^third^fourth:third^(second|~fourth);
      const word=group===0?index:group===1?(5*index+1)%16:group===2?(3*index+5)%16:(7*index)%16;
      const total=(first+value+constants[index]+view.getUint32(offset+word*4,true))>>>0;
      const rotation=rotations[group*4+index%4];
      const next=(second+((total<<rotation)|(total>>>(32-rotation))))>>>0;
      first=fourth;fourth=third;third=second;second=next;
    }
    state[0]=(state[0]+first)>>>0;state[1]=(state[1]+second)>>>0;state[2]=(state[2]+third)>>>0;state[3]=(state[3]+fourth)>>>0;
  }
  return state.flatMap(value=>[0,8,16,24].map(shift=>((value>>>shift)&255).toString(16).padStart(2,'0'))).join('');
}

export const derive=(...parts)=>md5(JSON.stringify(parts.map(String)));
export const chunkSeed=(seed,horizontal,vertical)=>derive(seed,'chunk',horizontal,vertical);
export const cellSeed=(seed,horizontal,vertical,tileX,tileY)=>derive(chunkSeed(seed,horizontal,vertical),'tile',tileX,tileY);

export class RandomStream {
  constructor(seed) {
    const digest=md5(seed);
    this.words=Array.from({length:4},(_,index)=>{const offset=index*8;return [0,2,4,6].reduce((result,shift)=>result|parseInt(digest.slice(offset+shift,offset+shift+2),16)<<(shift*4),0)>>>0;});
    for(let warmup=0;warmup<12;warmup++)this.random();
  }
  random() {
    const [first,second,third,fourth]=this.words,total=(first+second+fourth)>>>0;
    this.words=[(second^(second>>>9))>>>0,(third+(third<<3))>>>0,(((third<<21)|(third>>>11))+total)>>>0,(fourth+1)>>>0];
    return total/4294967296;
  }
  randint(lower,upper){return lower+Math.floor(this.random()*(upper-lower+1));}
  choice(values){return values[this.randint(0,values.length-1)];}
  shuffle(values){for(let index=values.length-1;index>0;index--){const other=this.randint(0,index);[values[index],values[other]]=[values[other],values[index]];}return values;}
  sample(values,count){return this.shuffle([...values]).slice(0,count);}
}

const key=(horizontal,vertical)=>`${horizontal},${vertical}`;
const point=identifier=>identifier.split(',').map(Number);
const sorted=values=>[...values].sort((first,second)=>{const before=point(first),after=point(second);return before[0]-after[0]||before[1]-after[1];});
const steps=[[1,0],[-1,0],[0,1],[0,-1]];

function flood(start,blocked,bounds) {
  const visited=new Set(start.filter(position=>!blocked.has(position))),pending=[...visited];
  for(let cursor=0;cursor<pending.length;cursor++) {
    const [horizontal,vertical]=point(pending[cursor]);
    for(const [offsetX,offsetY]of steps) {
      const nextX=horizontal+offsetX,nextY=vertical+offsetY,identifier=key(nextX,nextY);
      if(nextX>=bounds[0]&&nextX<=bounds[1]&&nextY>=bounds[2]&&nextY<=bounds[3]&&!blocked.has(identifier)&&!visited.has(identifier)){visited.add(identifier);pending.push(identifier);}
    }
  }
  return visited;
}
const adjacent=(position,reachable)=>{const [horizontal,vertical]=point(position);return steps.some(([offsetX,offsetY])=>reachable.has(key(horizontal+offsetX,vertical+offsetY)));};

function building(stream,centerX,centerY) {
  for(let attempt=0;attempt<100;attempt++) {
    const width=stream.randint(7,13),height=stream.randint(7,13),left=centerX+stream.randint(-6,7-width),bottom=centerY+stream.randint(-6,7-height),right=left+width-1,top=bottom+height-1;
    const perimeter=new Set(),interior=new Set();
    for(let horizontal=left;horizontal<=right;horizontal++)for(let vertical=bottom;vertical<=top;vertical++)(horizontal===left||horizontal===right||vertical===bottom||vertical===top?perimeter:interior).add(key(horizontal,vertical));
    for(const edge of stream.sample([0,1,2,3],stream.randint(1,2))) {
      const opening=stream.randint(1,2),start=edge<2?stream.randint(left+1,right-opening):stream.randint(bottom+1,top-opening);
      for(let offset=0;offset<opening;offset++)perimeter.delete(edge<2?key(start+offset,edge===0?bottom:top):key(edge===2?left:right,start+offset));
    }
    const pillars=new Set(stream.sample(sorted(interior),Math.min(5,Math.max(1,Math.floor(interior.size/20))))),chests=[];
    const candidates=stream.shuffle(sorted([...interior].filter(position=>!pillars.has(position)))),desired=stream.randint(1,2);
    for(const position of candidates) {
      const [horizontal,vertical]=point(position);
      if(chests.every(other=>{const coordinates=point(other);return Math.max(Math.abs(horizontal-coordinates[0]),Math.abs(vertical-coordinates[1]))>1;})){chests.push(position);if(chests.length===desired)break;}
    }
    if(chests.length!==desired)continue;
    const blocked=new Set([...perimeter,...pillars,...chests]),reachable=flood([key(left-1,bottom-1)],blocked,[left-1,right+1,bottom-1,top+1]);
    if(![...interior].some(position=>reachable.has(position))||chests.some(position=>!adjacent(position,reachable)))continue;
    return {objects:[...sorted(new Set([...perimeter,...pillars])).map(position=>({kind:'wall',position})),...chests.map(position=>({kind:'chest',position}))],interior};
  }
  throw new Error('procedural_building_unreachable');
}

export function plan(seed,horizontal,vertical,settings) {
  if(settings.algorithm!==1)throw new Error('unsupported_terrain_algorithm');
  const base=chunkSeed(seed,horizontal,vertical),stream=new RandomStream(base),centerX=horizontal*settings.size,centerY=vertical*settings.size,roll=stream.random();
  let objects=[];
  if((horizontal===0&&vertical===0)||roll>=.9) {
    const house=building(stream,centerX,centerY);objects=house.objects;
    for(const [kind,name,chance]of settings.machines) {
      const feature=new RandomStream(derive(base,'feature',name));if(feature.random()>=chance)continue;
      const blocked=new Set(objects.map(object=>object.position)),containers=objects.filter(object=>object.kind!=='wall').map(object=>object.position),bounds=[centerX-8,centerX+8,centerY-8,centerY+8],entrance=key(bounds[0],bounds[2]);
      const protectedTiles=new Set([...flood([entrance],blocked,bounds)].filter(position=>house.interior.has(position)));
      const passages=new Set([...house.interior].filter(position=>{const [tileX,tileY]=point(position);return steps.some(([offsetX,offsetY])=>{const neighbor=key(tileX+offsetX,tileY+offsetY);return !house.interior.has(neighbor)&&!blocked.has(neighbor);});}));
      const candidates=feature.shuffle(sorted([...house.interior].filter(position=>!blocked.has(position))));
      for(const position of candidates) {
        const [tileX,tileY]=point(position);
        if(passages.has(position)||containers.some(target=>{const [targetX,targetY]=point(target);return Math.max(Math.abs(tileX-targetX),Math.abs(tileY-targetY))<=1;}))continue;
        const reachable=flood([entrance],new Set([...blocked,position]),bounds);
        if([...protectedTiles].some(target=>target!==position&&!reachable.has(target))||![...house.interior].some(target=>reachable.has(target))||[...containers,position].some(target=>!adjacent(target,reachable)))continue;
        objects.push({kind,position});break;
      }
    }
  }else if(roll>=.5) {
    for(let tileX=centerX-7;tileX<centerX+8;tileX++)for(let tileY=centerY-7;tileY<centerY+8;tileY++)if(parseInt(derive(cellSeed(seed,horizontal,vertical,tileX,tileY),'tree').slice(0,8),16)/4294967296<.1)objects.push({kind:'tree',position:key(tileX,tileY)});
  }else {
    for(const [kind,definition]of Object.entries(settings.outdoors)) {
      const feature=new RandomStream(derive(base,'feature',definition.stream));if(feature.random()>=definition.chance)continue;
      const occupied=new Set(objects.map(object=>object.position)),candidates=[];
      for(let offsetX=-6;offsetX<=6;offsetX++)for(let offsetY=-6;offsetY<=6;offsetY++){const position=key(centerX+offsetX,centerY+offsetY);if(!occupied.has(position))candidates.push(position);}
      if(candidates.length)objects.push({kind,position:feature.choice(candidates)});
    }
  }
  return objects.map(object=>{const [tileX,tileY]=point(object.position);return {id:`n:${horizontal}:${vertical}:${tileX}:${tileY}:${object.kind}`,kind:object.kind,x:tileX,y:tileY,lit:false,monster_demolition:false};});
}

export const fingerprint=records=>md5(JSON.stringify([...records].sort((first,second)=>first.id<second.id?-1:first.id>second.id?1:0).map(record=>[record.id,record.kind,record.x,record.y])));
