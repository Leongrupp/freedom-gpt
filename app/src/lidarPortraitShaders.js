const common=`uniform float uTime,uJaw,uRound,uAwake,uAssembly,uMic,uBlink,uThinking,uDisperse;uniform vec2 uGaze;
float sq(float x){return x*x;}
vec3 articulate(vec3 p){float jaw=1.0-smoothstep(-.77,-.35,p.y);p.y-=uJaw*.10*jaw;p.z+=uJaw*.015*jaw;return p;}
`;
export const occluderVertex=common+`void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(articulate(position),1.0);}`;
export const occluderFragment=`uniform float uAwake;void main(){gl_FragColor=vec4(.012,.020,.038,uAwake*.10);}`;
export const cellVertex=common+`
attribute float aTone,aSeed,aLayer,aEdge;uniform float uSize,uPixelRatio,uGlow;
varying float vLight,vAlpha,vLayer;varying vec3 vTint;
void main(){
 vec3 p=position;float tone=aTone;vLayer=aLayer;vTint=vec3(.92,.94,.98);
 if(aLayer<1.5){
  p=articulate(p);
  float rim=1.0-smoothstep(.15,1.0,aEdge);
  tone=.22+aTone*.43+rim*.20;
  float scan=exp(-sq((p.y-(mod(uTime*.20,2.7)-1.3))/.035));
  tone+=scan*.16;vTint=mix(vTint,vec3(1.0),scan*.30+rim*.22);
  float fringe=smoothstep(.48,.87,abs(p.x));
  float gust=.5+.5*sin(uTime*.75+p.y*5.0);
  p.x+=sin(p.y*8.0-uTime*1.25+aSeed*.6)*(.008+fringe*.035)*(1.0+uMic*.35);
  p.z+=sin(p.y*5.0-uTime*.85)*.012;
  if(aSeed>.87){float drift=fract(uTime*.09+aSeed*17.0);p.x+=drift*drift*.18*(.25+fringe);p.y+=sin(uTime+aSeed*9.0)*.018;p.z+=drift*.045;}
  vec3 away=normalize(vec3(p.x,p.y*.6,p.z-.3)+vec3(.001));p+=away*uDisperse*(.3+aSeed*.85);
  p=clamp(p,vec3(-1.40),vec3(1.40));
  vAlpha=(.13+.43*tone+rim*.15)*smoothstep(.02,.24,aEdge)*(aLayer>.4?.24:1.0);
 }else{
  p.x=mod(p.x+uTime*(.20+aSeed*.14)+1.325,2.65)-1.325;
  p.y+=sin(uTime*.85+p.x*2.1+aSeed*17.0)*.055;
  p.z+=sin(uTime*.6+p.x*2.0)*.035;
  tone*=.8+.2*sin(uTime*.55+aSeed*31.0);vAlpha=p.z>.7?.15:.29;
  vTint=vec3(.77,.80,.86);
 }
 vec4 mv=modelViewMatrix*vec4(p,1.0);gl_Position=projectionMatrix*mv;
 float size=uSize*(aLayer>1.5?.68:1.0)*(aLayer>.4&&aLayer<1.5?.84:1.0);
 gl_PointSize=min(12.0,size*(.90+aSeed*.18)*uPixelRatio*(4.2/-mv.z)*(uGlow>.5?2.6:1.0));
 vLight=max(0.0,tone);vAlpha*=uAwake*smoothstep(.02,.25,uAwake);
}`;
export const cellFragment=`precision highp float;uniform float uGlow;varying float vLight,vAlpha,vLayer;varying vec3 vTint;
void main(){vec2 p=(gl_PointCoord-.5)*2.0;float mask;
 if(uGlow>.5){mask=exp(-dot(p,p)*4.0)*.075;}
 else{vec2 q=abs(p)-vec2(.58);float roundBox=length(max(q,0.0))+min(max(q.x,q.y),0.0)-.18;mask=1.0-smoothstep(0.0,.16,roundBox);}
 if(mask<.004)discard;
 vec3 color=vTint*(.42+vLight*.90);if(vLayer>1.5)color=vTint*vLight*2.5;
 gl_FragColor=vec4(color,mask*vAlpha);
}`;
