import * as THREE from 'three';
const gaussian=(x,mean,width)=>Math.exp(-(((x-mean)/width)**2));
// Original parametric anatomy: skull, orbital hollows, bridge, cheekbones and chin.
// Coordinates remain on a true closed 3D surface; no portrait texture is used.
export function headPoint(u,v){
 const y=Math.cos(v)*1.38,s=Math.sin(v),front=Math.max(0,Math.cos(u)),taper=1-.22*gaussian(y,-1.05,.46);
 const x=Math.sin(u)*Math.pow(s,.88)*.88*taper;
 let z=Math.cos(u)*s*(.69+.06*gaussian(y,.7,.5));
 z+=Math.pow(front,6)*(.17*gaussian(x,0,.12)*gaussian(y,.12,.48)+.25*gaussian(x,0,.18)*gaussian(y,-.18,.17)
  -.13*(gaussian(x,.35,.23)+gaussian(x,-.35,.23))*gaussian(y,.2,.18)
  +.09*(gaussian(x,.51,.23)+gaussian(x,-.51,.23))*gaussian(y,-.25,.28)
  +.08*gaussian(x,0,.3)*gaussian(y,-.56,.13)+.09*gaussian(x,0,.38)*gaussian(y,-.96,.22));
 return [x,y,z];
}
export function headGeometry(cols=72,rows=58){
 const positions=[],indices=[];
 for(let j=0;j<=rows;j++)for(let i=0;i<=cols;i++)positions.push(...headPoint(i/cols*Math.PI*2,j/rows*Math.PI));
 for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const a=j*(cols+1)+i,b=a+cols+1;indices.push(a,b,a+1,b,b+1,a+1)}
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();return geometry;
}
export function headGrid(cols=42,rows=34){
 const positions=[];
 for(let j=1;j<rows;j++)for(let i=0;i<cols;i++){const p=headPoint(i/cols*Math.PI*2,j/rows*Math.PI);positions.push(...p,...headPoint((i+1)/cols*Math.PI*2,j/rows*Math.PI));if(j<rows-1)positions.push(...p,...headPoint(i/cols*Math.PI*2,(j+1)/rows*Math.PI))}
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));return geometry;
}
export function neuralGeometry(low=false){
 const nodes=[],edges=[],pairs=[],cols=low?24:38,rows=low?14:24;
 for(const side of [-1,1]){
  const offset=nodes.length/3;
  for(let j=0;j<=rows;j++)for(let i=0;i<cols;i++){
   const a=i/cols*Math.PI*2,b=j/rows*Math.PI,fold=1+.09*Math.sin(a*7+b*5)*Math.cos(b*9);
   nodes.push(side*.26+Math.sin(b)*Math.cos(a)*.34*fold,.69+Math.cos(b)*.47*fold,-.05+Math.sin(b)*Math.sin(a)*.48*fold);
  }
  for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){
   const a=offset+j*cols+i;
   for(const b of [offset+j*cols+(i+1)%cols,a+cols,offset+(j+1)*cols+(i+1)%cols]){
    const from=nodes.slice(a*3,a*3+3),to=nodes.slice(b*3,b*3+3);edges.push(...from,...to);pairs.push([from,to]);
   }
  }
 }
 const points=new THREE.BufferGeometry();points.setAttribute('position',new THREE.Float32BufferAttribute(nodes,3));const lines=new THREE.BufferGeometry();lines.setAttribute('position',new THREE.Float32BufferAttribute(edges,3));
 return {points,lines,pairs,nodeCount:nodes.length/3,connectionCount:edges.length/6};
}
