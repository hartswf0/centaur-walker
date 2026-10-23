const HOLY={a:38,b:41.5,c:39.3,d:40.1,e:55.8,f:39.4,g:36.7,h:65.7,i:49,j:50,k:61.9,l:7.8,m:15};
const JD={J1:['B','b','M','j',1],J2:['B','c','M','k',-1],J3:['B','d','J1','e',1],J4:['J3','f','J2','g',-1],F:['J4','h','J2','i',-1]};
const N=360,TAU=Math.PI*2;
function cc(P,r0,Q,r1,s){const dx=Q.x-P.x,dy=Q.y-P.y,d=Math.hypot(dx,dy);if(d<1e-9||d>r0+r1||d<Math.abs(r0-r1))return null;const a=(r0*r0-r1*r1+d*d)/(2*d),h=Math.sqrt(Math.max(0,r0*r0-a*a)),ux=dx/d,uy=dy/d;return{x:P.x+a*ux-s*h*uy,y:P.y+a*uy+s*h*ux}}
function solve(G,th){const p={O:{x:0,y:0},B:{x:-G.a,y:-G.l},M:{x:G.m*Math.cos(th),y:G.m*Math.sin(th)}};for(const J of ['J1','J2','J3','J4','F']){const[a,r0,b,r1,s]=JD[J];const q=cc(p[a],G[r0],p[b],G[r1],s);if(!q)return null;p[J]=q}return p}
function metrics(G){const fx=[],fy=[];for(let k=0;k<N;k++){const p=solve(G,TAU*k/N);if(!p)return null;fx.push(p.F.x);fy.push(p.F.y)}
 const minY=Math.min(...fy),maxY=Math.max(...fy),lift=maxY-minY;
 // contact: within 2% of lift (flat enough for a plant)
 const tol=1.0;let c=0,sv=0,nv=0;const con=fy.map(y=>y<minY+tol);
 for(let k=0;k<N;k++){if(con[k])c++;const n=(k+1)%N;if(con[k]&&con[n]){sv+=fx[n]-fx[k];nv++}}
 // speed uniformity in stance
 let vs=[];for(let k=0;k<N;k++){const n=(k+1)%N;if(con[k]&&con[n])vs.push(Math.abs(fx[n]-fx[k]))}
 const vm=vs.reduce((a,b)=>a+b,0)/vs.length,vv=Math.sqrt(vs.reduce((a,b)=>a+(b-vm)**2,0)/vs.length)/vm;
 const ys=fy.filter((y,k)=>con[k]);const flat=Math.max(...ys)-Math.min(...ys);
 let run=[],bestRun=[];for(let q=0;q<2*N;q++){const k=q%N;if(con[k])run.push(fx[k]);else{if(run.length>bestRun.length)bestRun=run;run=[]}}
 if(bestRun.length<2)return null; const L=bestRun.length;let sl=0;for(let i=0;i<L;i++){const lin=bestRun[0]+(bestRun[L-1]-bestRun[0])*i/(L-1);sl=Math.max(sl,Math.abs(bestRun[i]-lin))}
 return{slide:sl,duty:c/N,adv:Math.abs(sv/nv)*N,lift,flat,vv,minY}}
const base=metrics(HOLY);console.log('holy',base);
let best=[];let seed=7;const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647};
const keys=['b','c','d','e','f','g','h','i','j','k'];
let cur={...HOLY},curS=-1e9;
function score(m){if(!m)return -1e9; if(m.lift<10)return -1e9; return m.duty*100 - 8*Math.max(0,m.slide-1.5) + .05*Math.min(m.adv,130) - 5*Math.max(0, 14-m.lift)}
for(let run=0;run<6;run++){let G={...HOLY},S=score(metrics(G));let T=3;
 for(let it=0;it<6000;it++){const g={...G};const k=keys[Math.floor(rnd()*keys.length)];g[k]=+(g[k]+(rnd()-.5)*T).toFixed(2);const m=metrics(g),s=score(m);if(s>S||rnd()<Math.exp((s-S)/ (T*2))*0.02){G=g;S=s}T=Math.max(.2,T*0.9995)}
 const m=metrics(G);best.push({S,G,m});}
best.sort((a,b)=>b.S-a.S);for(const b of best.slice(0,3)){console.log(JSON.stringify(b.m),JSON.stringify(b.G))}
