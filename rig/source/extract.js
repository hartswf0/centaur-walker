() => { const T=__t, R={};
 const builds = {
  backpack: {mode:'walk', stock:'epsd', sigma:9.79, Lb:760, gap:40, make:'jig', joints:{O:'bearing',B:'bush',M:'bush',J1:'bush',J2:'bush',J3:'bush',J4:'bush'}},
  bike: {mode:'bike', stock:'ply', sigma:6, mountY:700, make:'jig', drive:'gt27', gap:320, joints:{O:'bearing',B:'bush',M:'bearing',J1:'bush',J2:'bush',J3:'bush',J4:'bush'}} };
 for (const [name, mod] of Object.entries(builds)) {
  const b = Object.assign(JSON.parse(JSON.stringify(T.VARS[0].B)), mod); b.phi0=null;
  const e = T.engine(b);
  const flats={}; for (const p of T.PARTS) flats[p.id]={name:p.name, pts:T.partFlat(p,b), holes:p.holes, segs:p.segs, tri:p.tri||null, foot:p.foot||null};
  const pins={}; for (const pn of T.PINS){ const p=e.pins[pn.id]; pins[pn.id]={parts:pn.parts, use:p.use, peak:p.peak, swing:p.swing, c:p.c, tilt:p.tilt*180/Math.PI, lo:p.lo, hi:p.hi, knocks:p.knockAt.length, recipe:p.recipe}; }
  const links={}; for (const [k,L] of Object.entries(e.links)) links[k]={L:L.Lmm, squeeze:L.cMax, Pcr:L.Pcr, buck:L.buck};
  // 16 frames: positions of all joints for leg 0 and leg 1 (other side), human legs for walk
  const frames=[]; const rpm=e.rpm;
  for (let q=0;q<16;q++){ const c=q/16; const legs=e.offs.map(o=>{const phi=e.A.spin*2*Math.PI*c+e.phi0+o/360*2*Math.PI; const P=T.solve(e.G,phi); const k=T.kIdx(phi); return {P, down: !!e.A.contact[k]};}); frames.push({c, legs}); }
  const hum=[]; for (let q=0;q<=360;q++){ hum.push([T.HM.hipX[q], T.HM.hipY[q]]); }
  R[name]={b, G:e.G, rpm, spin:e.A.spin, phi0:e.phi0, A:{minY:e.A.minY,maxY:e.A.maxY,minX:e.A.minX,maxX:e.A.maxX,topY:e.A.topY,advance:e.A.advance,duty:e.A.duty, fx:Array.from(e.A.fx), fy:Array.from(e.A.fy), contact:Array.from(e.A.contact)},
    layerOf:e.lay.layerOf, nL:e.lay.nL, pins, links, ledger:e.ledger, bom:T.bomOf(e), cost:T.costOf(e), legKg:e.legKg, totalKg:e.totalKg, spread:e.spread, wobble:e.wobble, fricW:e.fricW, footZ:e.footZ, humanZ:e.humanZ, Hc:e.Hc, HMadv:T.HM.advance, HMhip:T.HM.meanHip, g:e.g, flats, frames, worst:e.worst, tIdx:Array.from(e.tIdx)};
 }
 return R; }
