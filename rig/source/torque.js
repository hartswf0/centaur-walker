() => { const T=__t, out={};
 for (const [name, mod] of Object.entries({backpack:{mode:'walk', stock:'epsd', sigma:9.49, joints:{O:'bearing',B:'bush',M:'bush',J1:'bush',J2:'bush',J3:'bush',J4:'bush'}}, bike:{mode:'bike', stock:'ply', sigma:6, mountY:700, gap:180, drive:'gt27', joints:{O:'bearing',B:'bush',M:'bearing',J1:'bush',J2:'bush',J3:'bush',J4:'bush'}}})) {
  const b=Object.assign(JSON.parse(JSON.stringify(T.VARS[0].B)),mod); b.phi0=null; const e=T.engine(b);
  let mx=0, sum=0, n=0, P=0; const nl=e.offs.length;
  for (let i=0;i<360;i++){ let tot=0; for (const o of e.offs){ const k=(e.tIdx[i]+o)%360; const f=e.F[k]; const p=e.poses[k]; if(!f||!p.M) continue; const Fs=f.pinVec.M; const tq=-(p.M.x*Fs.y - p.M.y*Fs.x)*b.sigma/1000; tot+=tq; } mx=Math.max(mx,Math.abs(tot)); sum+=tot; n++; }
  out[name]={peakNm:mx, meanNm:sum/n, spin:e.A.spin, rpm:e.rpm, fricW:e.fricW, powerW: Math.abs(sum/n)*e.rpm*2*Math.PI/60};
 } return out; }
