import json, math
D=json.load(open('builds.json'))
JD={'J1':('B','b','M','j',1),'J2':('B','c','M','k',-1),'J3':('B','d','J1','e',1),'J4':('J3','f','J2','g',-1),'F':('J4','h','J2','i',-1)}
def cc(P,r0,Q,r1,s):
    dx,dy=Q[0]-P[0],Q[1]-P[1];d=math.hypot(dx,dy)
    if d>r0+r1 or d<abs(r0-r1): return None
    a=(r0*r0-r1*r1+d*d)/(2*d);h=math.sqrt(max(0,r0*r0-a*a));ux,uy=dx/d,dy/d
    return (P[0]+a*ux-s*h*uy,P[1]+a*uy+s*h*ux)
def solve(G,th):
    p={'O':(0,0),'B':(-G['a'],-G['l']),'A':(0,-G['l']),'M':(G['m']*math.cos(th),G['m']*math.sin(th))}
    for J in ['J1','J2','J3','J4','F']:
        a,r0,b,r1,s=JD[J];p[J]=cc(p[a],G[r0],p[b],G[r1],s)
    return p
def dseg(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];L=dx*dx+dy*dy;t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
SEGS={'frame':[('B','A'),('A','O')],'crank':[('O','M')],'j':[('M','J1')],'k':[('M','J2')],'c':[('B','J2')],'f':[('J3','J4')],'up':[('B','J1'),('J1','J3'),('J3','B')],'lo':[('J2','J4'),('J4','F'),('F','J2')]}
TRI={'up':['B','J1','J3'],'lo':['J2','J4','F']}
def intri(p,t):
    s=lambda a,b,c:(a[0]-c[0])*(b[1]-c[1])-(b[0]-c[0])*(a[1]-c[1])
    d1,d2,d3=s(p,t[0],t[1]),s(p,t[1],t[2]),s(p,t[2],t[0])
    return not((d1<0 or d2<0 or d3<0) and (d1>0 or d2>0 or d3>0))
PINS={'O':['frame','crank'],'B':['frame','up','c'],'M':['crank','j','k'],'J1':['j','up'],'J2':['k','c','lo'],'J3':['up','f'],'J4':['f','lo']}
for name,W,plate in (('backpack',{'frame':64,'crank':50},True),('bike',{'frame':50,'crank':40},True)):
    d=D[name];G=d['G'];sg=d['b']['sigma'];lay=d['layerOf'];wdef=70 if name=='backpack' else 40
    nL=max(lay.values())+1
    for pin,parts in PINS.items():
        ls=[lay[p] for p in parts]; lo,hi=min(ls),max(ls)
        if pin=='O': lo=0
        res=[]
        for side,L in (('inner',lo-1),('outer',hi+1)):
            if L<0: res.append((side,'centre')); continue
            if L>=nL: res.append((side,'clear')); continue
            hit=[]
            for q,l in lay.items():
                if l!=L or q in parts: continue
                w=W.get(q,wdef); deg=0
                for k in range(360):
                    P=solve(G,2*math.pi*k/360)
                    pt=P[pin]
                    dm=min(dseg(pt,P[a],P[b]) for a,b in SEGS[q])*sg
                    inside = q in TRI and plate and intri(pt,[P[x] for x in TRI[q]])
                    if dm < 16+w/2 or inside: deg+=1
                if deg: hit.append(f'{q}:{deg}deg')
            res.append((side,hit or 'clear'))
        print(name,pin,f'L{lo}-{hi}',res)
