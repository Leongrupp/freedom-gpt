// Original continuous facial relief. No portrait, camera texture or eyeballs.
const bell=(v,c,s)=>Math.exp(-(((v-c)/s)**2));
const smooth=(a,b,x)=>{const t=Math.min(1,Math.max(0,(x-a)/(b-a)));return t*t*(3-2*t)};
export function matrixFace(x,y){
 x/=1.58;y/=1.55;
 const n=(y-.06)/1.30;if(Math.abs(n)>=1)return {depth:0,mask:0};
 const width=.98*Math.pow(1-n*n,.44)*(1-.10*bell(y,-.88,.36));
 const mask=(1-smooth(width-.10,width,Math.abs(x)))*(1-smooth(.95,1,Math.abs(n)));
 const front=Math.sqrt(Math.max(0,1-(x/Math.max(.001,width))**2));
 let z=.32*front;
 z+=.09*(bell(x,.45,.24)+bell(x,-.45,.24))*bell(y,-.13,.26);
 z-=.14*(bell(x,.34,.22)+bell(x,-.34,.22))*bell(y,.28,.13);
 z+=.045*(bell(x,.32,.25)+bell(x,-.32,.25))*bell(y,.46,.085);
 z+=.16*bell(x,0,.12)*bell(y,.18,.40)+.29*bell(x,0,.155)*bell(y,-.12,.14);
 z-=.035*(bell(x,.16,.06)+bell(x,-.16,.06))*bell(y,-.18,.045);
 z+=.055*bell(x,0,.30)*bell(y,-.44,.045)+.045*bell(x,0,.28)*bell(y,-.55,.045);
 z-=.055*bell(x,0,.31)*bell(y,-.49,.035);
 z+=.07*bell(x,0,.38)*bell(y,-.91,.19);
 return {depth:z*mask*1.22,mask};
}
export function matrixGrid(low=false){
 const cols=low?48:66,rows=low?60:82,positions=[],face=[],seed=[];
 const width=3.34,height=4.05;
 for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){
  const x=(i/(cols-1)-.5)*width,y=(j/(rows-1)-.5)*height;
  const f=matrixFace(x,y),dx=(matrixFace(x+.004,y).depth-matrixFace(x-.004,y).depth)/.008,dy=(matrixFace(x,y+.004).depth-matrixFace(x,y-.004).depth)/.008;
  positions.push(x,y,0);face.push(f.depth,dx,dy,f.mask);
  const r=Math.sin(i*127.1+j*311.7)*43758.5453;seed.push(r-Math.floor(r));
 }
 return {cols,rows,count:seed.length,width,height,positions,face:new Float32Array(face),seed:new Float32Array(seed),tile:Math.min(width/(cols-1),height/(rows-1))*.86};
}
