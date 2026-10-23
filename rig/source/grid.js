() => { const T=__t, out=[];
 const policies = {
  cheap: null,
  bush: {O:'bearing',B:'bush',M:'bearing',J1:'bush',J2:'bush',J3:'bush',J4:'bush'},
  bear: {O:'bearing',B:'bearing',M:'bearing',J1:'bearing',J2:'bearing',J3:'bearing',J4:'bearing'},
  clev: {O:'bearing',B:'clevis',M:'bearing',J1:'bush',J2:'clevis',J3:'bush',J4:'bush'},
  pvc: {O:'bearing',B:'pvc',M:'bearing',J1:'pvc',J2:'pvc',J3:'pvc',J4:'pvc'} };
 for (const mode of ['walk','bike']) for (const stock of ['epsd','ply','pvc','alu','eps']) for (const [pn,pol] of Object.entries(policies)) {
   if (pn==='pvc' && stock!=='pvc') continue; if (stock==='pvc' && pn!=='pvc') continue;
   const b = JSON.parse(JSON.stringify(T.VARS[0].B)); b.mode=mode; b.stock=stock; b.phi0=null;
   if (mode==='bike'){ b.sigma=6; b.drive='w30'; b.make='jig'; } else { b.sigma=9.75; b.make='jig'; }
   if (pol) b.joints={...pol}; else { b.joints={O:'bearing',B:'puck',M:'puck',J1:'puck',J2:'puck',J3:'puck',J4:'puck'}; let e=T.engine(b); for (const p of T.PINS){ let best=null; for (const key of Object.keys(T.JT)){ } } }
   const e=T.engine(b);
   const links=Object.entries(e.links).map(([k,L])=>k+(L.buck).toFixed(2)).join(' ');
   out.push([mode,stock,pn,'worst',e.worst.toFixed(2),'wander',e.spread.toFixed(0)+'/'+e.wobble.toFixed(0),'kg',e.totalKg.toFixed(1),'$',T.costOf(e).toFixed(0),'pass',e.legible+'/'+e.ledN,'stack',e.stackMax.toFixed(0),'L',links].join(' '));
 }
 return out; }
