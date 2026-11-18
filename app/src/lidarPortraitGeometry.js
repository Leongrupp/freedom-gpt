// Original analytic anatomy, sampled as a volume of discrete light cells.
// No photograph, movie frame or camera stream is part of the portrait.
const bell=(v,c,s)=>Math.exp(-(((v-c)/s)**2));
export function faceWidth(y){
 const n=(y-.05)/1.14;if(Math.abs(n)>=1)return 0;
 return .89*Math.pow(1-n*n,.47)*(1-.055*bell(y,-.80,.34)+.035*bell(y,-.18,.40));
}
export function faceDepth(x,y){
 const width=Math.max(.01,faceWidth(y)),side=Math.sqrt(Math.max(0,1-(x/width)**2)),front=Math.pow(side,.72);
 let z=(.53+.025*bell(y,.6,.8))*front;
 // A smooth, featureless silhouette: cheeks, a nose profile and rounded chin.
 z+=front*(.035*bell(x,0,.13)*bell(y,.13,.36)+.12*bell(x,0,.135)*bell(y,-.10,.13)
  +.055*(bell(x,.43,.24)+bell(x,-.43,.24))*bell(y,-.22,.22)
  +.025*bell(x,0,.32)*bell(y,-.48,.12)+.025*bell(x,0,.36)*bell(y,-.83,.22));
 return z;
}
const hash=(a,b)=>{const n=Math.sin(a*127.1+b*311.7)*43758.5453;return n-Math.floor(n)};
export function portraitCells(quality='auto'){
 const low=quality==='low',high=quality==='high',cols=low?76:high?150:114,rows=low?108:high?214:162;
 const position=[],tone=[],seed=[],layer=[],edge=[];
 const append=(x,y,z,t,s,l,e=1)=>{position.push(x,y,z);tone.push(t);seed.push(s);layer.push(l);edge.push(e)};
 for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){
  const y=-1.09+j/(rows-1)*2.28,x=-.92+i/(cols-1)*1.84,w=faceWidth(y);if(Math.abs(x)>w-.002)continue;
  const random=hash(i,j),z=faceDepth(x,y),dx=(faceDepth(x+.003,y)-faceDepth(x-.003,y))/.006,dy=(faceDepth(x,y+.003)-faceDepth(x,y-.003))/.006;
  const length=Math.hypot(dx,dy,1),light=Math.max(0,(-dx*-.20-dy*.12+.97)/length);
  let brightness=.48+.38*light;
  brightness+=.045*(bell(x,.43,.20)+bell(x,-.43,.20))*bell(y,-.22,.18);
  brightness*=.88+random*.12;
  append(x+(random-.5)*.003,y+(hash(j,i)-.5)*.002,z+(random-.5)*.004,brightness,random,0,Math.min(1,Math.max(0,(w-Math.abs(x))/.10)));
  if((i+j)%3===0)append(x,y,z-.027,brightness*.43,hash(i+12,j),.6,Math.min(1,Math.max(0,(w-Math.abs(x))/.10)));
 }
 // Sparse, deep slices create parallax outside the facial silhouette.
 const volumeCount=low?2600:high?7200:4600;
 const fieldCols=low?52:high?80:70,fieldRows=Math.ceil(volumeCount/fieldCols);
 for(let i=0;i<volumeCount;i++){
  const col=i%fieldCols,row=Math.floor(i/fieldCols);
  const x=(col/(fieldCols-1)-.5)*2.65,y=(row/(fieldRows-1)-.5)*2.65,z=i%7===0?1.03:-.38-hash(col,23)*.85;
  const peripheral=Math.abs(x)>faceWidth(Math.max(-1.29,Math.min(1.35,y)))*.8;
  append(x,y,z,(peripheral?.22:.13)*(hash(i,67)*.6+.4),hash(i,14),2);
 }
 return {position:new Float32Array(position),tone:new Float32Array(tone),edge:new Float32Array(edge),seed:new Float32Array(seed),layer:new Float32Array(layer),cols,rows,count:tone.length,volumeCount};
}
export function portraitOccluder(cols=64,rows=88){
 const position=[],indices=[];
 for(let j=0;j<=rows;j++){const y=-1.09+j/rows*2.28,w=faceWidth(y);for(let i=0;i<=cols;i++){const x=(i/cols*2-1)*w;position.push(x,y,faceDepth(x,y)-.052)}}
 for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const a=j*(cols+1)+i,b=a+cols+1;indices.push(a,a+1,b,a+1,b+1,b)}
 return {position:new Float32Array(position),indices};
}
