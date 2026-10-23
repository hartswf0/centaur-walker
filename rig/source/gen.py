"""Centaur Rig design set generator.
Reads builds.json (exported from the instrument engine) and writes, per build:
  1:1 SVG and DXF for every cut part, the drive and mount layouts, the 16-frame plate,
  the front section, stack recipes, cut list, buy list, steps and checks, and one HTML design set.
"""
import json, math, os, zipfile, html

D = json.load(open('builds.json'))
H = 1750.0
OUT = '../files'
os.makedirs(OUT, exist_ok=True)
BOLTS_M8 = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140, 150]
GT2_PD = lambda n: 2.0 * n / math.pi           # GT2 pitch diameter, mm
SPUR_PD = lambda n: 1.0 * n                    # module 1 spur gear pitch diameter, mm

# ---------------------------------------------------------------- build specs
SPEC = {
  'backpack': dict(
    title='Backpack', code='BP', wearer='1.75 m wearer, hip belt at 900 mm',
    foam=True, core=25.4, cheek=5.5, cheekD=60, w=70, plyW={'frame': 64, 'crank': 50}, gap=40,
    thick={'frame': 11.0, 'crank': 11.0}, thickDefault=25.4 + 2 * 5.5,
    stockName='1 in EPS (25.4), 1/4 in ply cheeks',
    roller=55.0, ratio=[('gt2', 16, 40), ('spur', 20, 60)],
  ),
  'bike': dict(
    title='Bike', code='BK', wearer='rack top 790 mm, tire 702 mm OD',
    foam=False, ply=5.5, w=40, plyW={'frame': 50, 'crank': 40}, gap=320,
    thick={'frame': 11.0, 'crank': 11.0}, thickDefault=5.5,
    stockName='1/4 in birch ply (5.5)',
    roller=52.0, ratio=[('spur', 20, 60), ('gt2', 20, 60), ('gt2', 20, 60)],
  ),
}
PIN_NAMES = {'O': 'crank axle', 'B': 'frame pivot', 'M': 'crank pin', 'J1': 'top', 'J2': 'knee', 'J3': 'back', 'J4': 'hock'}
PART_ORDER = ['frame', 'crank', 'j', 'k', 'c', 'f', 'up', 'lo']
LINKS = ['j', 'k', 'c', 'f']

def fmt(v, d=0):
    s = f"{v:.{d}f}"
    return '0' if s in ('-0', '-0.0') else s

# ---------------------------------------------------------------- geometry helpers
def hull(points):
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in points))
    if len(pts) < 3: return pts
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]

def outline(centres, r, n=48):
    pts = []
    for (x, y) in centres:
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    return hull(pts)

def dist(a, b): return math.hypot(b[0]-a[0], b[1]-a[1])

def cc(P, r0, Q, r1, s):
    dx, dy = Q[0]-P[0], Q[1]-P[1]; d = math.hypot(dx, dy)
    if d > r0 + r1 or d < abs(r0 - r1) or d < 1e-9: return None
    a = (r0*r0 - r1*r1 + d*d) / (2*d); h = math.sqrt(max(0, r0*r0 - a*a)); ux, uy = dx/d, dy/d
    return (P[0] + a*ux - s*h*uy, P[1] + a*uy + s*h*ux)

def belt_len(c, d1, d2):
    return 2*c + math.pi*(d1+d2)/2 + (d2-d1)**2/(4*c)

def centre_for_belt(L, d1, d2):
    lo, hi = 1.0, 3000.0
    for _ in range(80):
        m = (lo + hi) / 2
        if belt_len(m, d1, d2) < L: lo = m
        else: hi = m
    return (lo + hi) / 2

# human gait (same keyframes as the instrument)
HIPK = [[0,25],[.1,22],[.3,5],[.5,-12],[.6,-8],[.75,18],[.88,30]]
KNEEK = [[0,5],[.15,18],[.4,5],[.55,30],[.72,62],[.85,40],[.97,3]]
def curve(keys, u):
    u = u % 1.0; n = len(keys); i = n - 1
    for q in range(n):
        if keys[q][0] <= u: i = q
    k1, k2, k0, k3 = keys[i], keys[(i+1) % n], keys[(i-1) % n], keys[(i+2) % n]
    u1, u2 = k1[0], k2[0]
    if u2 <= u1: u2 += 1
    uu = u + 1 if u < u1 else u
    t = (uu - u1) / (u2 - u1); p0, p1, p2, p3 = k0[1], k1[1], k2[1], k3[1]
    return 0.5*((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t + (-p0+3*p1-3*p2+p3)*t*t*t)
def human_leg(u):
    Lt, Ls = .245*H, .246*H
    a = math.radians(curve(HIPK, u)); kf = math.radians(curve(KNEEK, u))
    knee = (Lt*math.sin(a), -Lt*math.cos(a))
    ank = (knee[0] + Ls*math.sin(a-kf), knee[1] - Ls*math.cos(a-kf))
    return knee, ank

# ---------------------------------------------------------------- per-build model
def model(name):
    d = D[name]; sp = SPEC[name]; sg = d['b']['sigma']; lay = d['layerOf']
    nL = max(lay.values()) + 1
    # thickness at the joint, bush flanges (1 mm each) included
    TH = {'backpack': {'frame': 13.0, 'crank': 11.0, '_': 25.4 + 2*5.5 + 2*1.0},
          'bike': {'frame': 13.0, 'crank': 11.0, '_': 5.5 + 1.0}}[name]
    EXTRA = {'backpack': {}, 'bike': {2: 10.0}}[name]     # extra gap after a layer, so a nut clears the next layer
    def thick(pid): return TH.get(pid, TH['_'])
    layerT = [max(thick(p) for p in PART_ORDER if lay[p] == L) for L in range(nL)]
    WASH, FEND, NUT, HEAD, NUTAF = 1.0, 1.6, 8.0, 5.3, 13.0
    z0 = sp['gap'] / 2; zL = []; z = z0
    for L in range(nL):
        zL.append(z); z += layerT[L] + WASH + EXTRA.get(L, 0.0)
    def zmid(pid): return zL[lay[pid]] + thick(pid) / 2

    CAPTIVE_M = 'M8 thin nut (DIN 439, 5 mm) epoxied in a 13 AF hex cut through the INNER ply layer before gluing'
    CAPTIVE_O = 'M8 thin nut (DIN 439, 5 mm) epoxied in a 13 AF hex cut through the OUTER ply layer, flush; 3 mm roll pin across the crank through the rod in the INNER layer, 2.75 from the glue line'
    def hole(pid, pin):
        if pid == 'frame' and pin == 'O': return 22.0, '608 bearing, press fit, flush with inner face'
        if pid == 'crank': return 8.2, (CAPTIVE_O if pin == 'O' else CAPTIVE_M)
        if sp['foam'] and pid != 'frame': return 10.0, 'cheek plates: flanged bush 8×10×5 pressed into each face; foam core Ø14'
        return 10.0, 'flanged bush 8×10×5, flange outward'

    parts = {}
    for pid in PART_ORDER:
        fl = d['flats'][pid]
        pts = {k: (v['x'], v['y']) for k, v in fl['pts'].items()}
        w = sp['plyW'].get(pid, sp['w'])
        centres = list(pts.values()); extra = []
        if pid == 'frame':
            O = pts['O']
            if name == 'backpack':
                extra = [('S1', (O[0], O[1] - 40.0), 22.0, '608 bearing for drive shaft S1, flush with inner face'),
                         ('m1', (O[0] - 30, O[1] + 85), 6.5, 'M6 × 80 through frame, saddle block, frame'),
                         ('m2', (O[0] - 110, O[1] + 85), 6.5, 'M6 × 80 through frame, saddle block, frame')]
            else:
                extra = [('m1', (O[0] + 60, O[1] + 77), 6.5, 'M6 × 30 to rack angle'),
                         ('m2', (O[0] - 120, O[1] + 77), 6.5, 'M6 × 30 to rack angle')]
            centres += [e[1] for e in extra]
        poly = outline(centres, w/2)
        holes = [(h, pts[h], *hole(pid, h)) for h in (['O', 'M'] if pid == 'crank' else fl['holes'])]
        holes += extra
        parts[pid] = dict(name=fl['name'], pts=pts, w=w, poly=poly, holes=holes, thick=thick(pid), layer=lay[pid],
                          tri=fl['tri'], foot=fl['foot'], segs=fl['segs'])

    def gap_items(L):
        it = [('nylon washer 8 × 16 × 1', WASH, 'washer')]
        if EXTRA.get(L): it.append((f'spacer tube {fmt(EXTRA[L],1)} long, 12 OD × 8.5 ID', EXTRA[L], 'spacer'))
        return it

    stacks = {}
    for pin, pd in d['pins'].items():
        on = {p: lay[p] for p in pd['parts']}
        lo, hi = (0 if pin == 'O' else pd['lo']), pd['hi']
        body = []
        for L in range(lo, hi + 1):
            here = [p for p, l in on.items() if l == L]
            if here:
                p = here[0]; t = 11.0 if (pin == 'O' and p == 'frame') else thick(p)
                body.append((f"{parts[p]['name']}: {hole(p, pin)[1]}", t, 'plate:' + p))
                if L < hi and t < layerT[L] - .05:
                    body.append((f"spacer tube {fmt(layerT[L]-t,1)} long, 12 OD × 8.5 ID", layerT[L] - t, 'spacer'))
            else:
                body.append((f"spacer tube {fmt(layerT[L],1)} long, 12 OD × 8.5 ID", layerT[L], 'spacer'))
            if L < hi: body += gap_items(L)
        if pin == 'O':
            items = [(('shaft collar (left leg) / 60T spur hub (right leg), against the bearing' if name == 'backpack' else 'shaft collar against the bearing (each leg)'), 7.0, 'head')] + body
            crankOut = zL[lay['crank']] + thick('crank')
            rodLen = round(2 * crankOut)
            fastener = f"M8 threaded rod, cut to {rodLen}, shared by both legs, ends flush with the crank outer faces, cranks 180° apart, thread locker"
            grip = sum(t for n_, t, k in body)
        elif pin == 'M':
            # crank holds a captive nut; bolt enters from the outside, tip stops inside the crank
            items = body + [('M8 fender washer 32 mm', FEND, 'washer'), ('M8 bolt head (outer side)', HEAD, 'head')]
            grip = sum(t for n_, t, k in items if k != 'head')
            cut = grip - 1.0
            std = next((b_ for b_ in BOLTS_M8 if b_ >= cut), math.ceil(cut/10)*10)
            fastener = f"M8 × {std} bolt, cut to {fmt(cut)} so the tip stops 1 mm inside the crank, thread locker"
        else:
            items = [('M8 bolt head', HEAD, 'head'), ('M8 fender washer 32 mm', FEND, 'washer')] + body + [('M8 fender washer 32 mm', FEND, 'washer'), ('M8 nylock nut', NUT, 'nut')]
            grip = sum(t for n_, t, k in items if k not in ('head', 'nut'))
            need = grip + NUT + 2.5
            std = next((b_ for b_ in BOLTS_M8 if b_ >= need), math.ceil(need/10)*10)
            fastener = f"M8 × {std} bolt (partly threaded), nylock"
        stacks[pin] = dict(items=items, grip=grip, fastener=fastener, lo=lo, hi=hi, parts=pd['parts'])
    rodLen = round(2 * (zL[lay['crank']] + thick('crank')))
    drive = drive_layout(name, d, sp, sg)
    drive['shafts'] = shaft_table(name, sp, zL, thick, rodLen, drive)
    return dict(name=name, d=d, sp=sp, sg=sg, parts=parts, stacks=stacks, layerT=layerT, zL=zL, zmid=zmid, nL=nL, rodLen=rodLen, drive=drive)

def shaft_table(name, sp, zL, thick, rodLen, dr):
    """what sits where along each drive shaft; z in mm from the rig centreline, + = right side"""
    f0, f1, c0 = zL[0], zL[0] + 11.0, zL[1]
    leg = lambda sgn: [('crank (captive nut + roll pin)', c0, c0 + 11), ('washer', c0 - 1, c0), ('spacer tube', f1, c0 - 1), ('frame bearing 608', f0, f1)]
    def side(sgn, rows):
        return [(n, f'{min(sgn*a_, sgn*b_):.0f} … {max(sgn*a_, sgn*b_):.0f}') for (n, a_, b_) in rows]
    if name == 'backpack':
        O = side(-1, leg(-1)) + [('shaft collar', '-19 … -12'), ('60T spur, hub to the right', '8 … 19')] + side(1, leg(1)[::-1])
        return [
          ('O crank rod', f'{rodLen}', O),
          ('S1 shaft, 8 mm steel', f'{round(2*f1)}', [('frame bearing, left', f'{-f1:.0f} … {-f0:.0f}'), ('nylon washer', '-20 … -19'), ('wheel arm (608 in arm)', '-19 … -8'), ('40T GT2 pulley', '-6 … 7'), ('20T spur, hub to the right', '8 … 19'), ('frame bearing, right', f'{f0:.0f} … {f1:.0f}')]),
          ('R roller shaft, 8 mm steel', '66', [('shaft collar', '-26 … -19'), ('wheel arm (608 in arm)', '-19 … -8'), ('16T GT2 pulley', '-6 … 7'), ('55 mm roller, locked to shaft with epoxy putty', '8 … 32'), ('shaft collar', '33 … 40')]),
          ('W wheel axle', 'M8 × 70 bolt', [('wheel arm', '-19 … -8'), ('spacer tube 14', '-7 … 7'), ('110 mm wheel on its own bearings', '8 … 32'), ('washer + nylock', '33 … 43')]),
          ('Tensioner', 'M6 × 30 pivot, M5 × 30 idler', [('wheel arm', '-19 … -8'), ('tensioner lever (one ply)', '-7 … -2'), ('GT2 20T toothed idler, shim to line up with the belt', '-1 … 9')]),
        ]
    else:
        O = side(-1, leg(-1)) + [('shaft collar', f'{-f0+1:.0f} … {-f0+8:.0f}'), ('drive box outer plate (608)', '-143 … -132'), ('60T GT2 pulley, 10 mm belt', '-101 … -87'), ('drive box inner plate (608)', '-85 … -74'), ('shaft collar', f'{f0-8:.0f} … {f0-1:.0f}')] + side(1, leg(1)[::-1])
        return [
          ('C crank rod', f'{rodLen}', O),
          ('R roller shaft, 8 mm steel', '174', [('shaft collar', '-150 … -143'), ('box outer plate (608)', '-143 … -132'), ('20T spur', '-130 … -120'), ('box inner plate (608)', '-85 … -74'), ('52 mm roller, locked with epoxy putty', '-16 … 16'), ('shaft collar', '17 … 24')]),
          ('S1 shaft, 8 mm steel', '83', [('shaft collar', '-150 … -143'), ('box outer plate (608)', '-143 … -132'), ('60T spur', '-130 … -120'), ('20T GT2 pulley, 6 mm belt', '-117 … -103'), ('box inner plate (608)', '-85 … -74'), ('shaft collar', '-74 … -67')]),
          ('S2 shaft, 8 mm steel', '83', [('shaft collar', '-150 … -143'), ('box outer plate (608)', '-143 … -132'), ('60T GT2 pulley, 6 mm belt', '-117 … -103'), ('20T GT2 pulley, 10 mm belt', '-101 … -87'), ('box inner plate (608)', '-85 … -74'), ('shaft collar', '-74 … -67')]),
          ('Box standoffs ×3', 'M6 × 80 + nylock', [('outer plate', '-143 … -132'), ('spacer tube 47', '-132 … -85'), ('inner plate', '-85 … -74')]),
        ]

def drive_layout(name, d, sp, sg):
    out = {}
    if name == 'backpack':
        Hc = d['Hc']; O = (0.0, Hc); S1 = (0.0, Hc - 40.0)
        Wr = 55.0  # 110 mm inline wheel radius
        W = (330.0, Wr); R = (W[0], W[1] + Wr + sp['roller']/2)
        c_long = dist(R, S1); d1, d2 = GT2_PD(16), GT2_PD(40)
        L = belt_len(c_long, d1, d2)
        out = dict(O=O, S1=S1, W=W, R=R, Wr=Wr, rollR=sp['roller']/2, belt=[('R', 'S1', 16, 40, c_long, L, 'GT2 6 mm: closed loop 1650–1660 mm or a spliced open belt; sprung toothed idler takes up slack')],
                   spur=[('S1', 'O', 20, 60, 40.0)], ratio=2.5*3, perTurn=math.pi*sp['roller']*7.5,
                   arm=dict(top=S1, bottom=W, len=dist(S1, W)))
    else:
        g = d['g']; mx, my = d['b']['mountX'], d['b']['mountY']
        C = (mx, my); R = (g['roller']['x'], g['roller']['y'])
        cS = 40.0
        c2 = centre_for_belt(200, GT2_PD(20), GT2_PD(60))
        best = None
        r = g['r']; hub = (0.0, r); rack = g['rack']['y']
        for i in range(720):
            a = 2*math.pi*i/720
            S1 = (R[0] + cS*math.cos(a), R[1] + cS*math.sin(a))
            for s in (1, -1):
                S2 = cc(S1, c2, C, c2, s)
                if not S2: continue
                # clearances: tire and rack
                clear = min(dist(S1, hub) - r - 31, dist(S2, hub) - r - 20, dist(C, hub) - r - 20,
                            rack - 4 - (S1[1] + 31), rack - 4 - (S2[1] + 20), rack - 4 - (C[1] + 20))
                if best is None or clear > best[0]: best = (clear, S1, S2)
        clear, S1, S2 = best
        out = dict(C=C, R=R, S1=S1, S2=S2, clear=clear, hub=hub, r=r, rack=rack, rollR=sp['roller']/2,
                   spur=[('R', 'S1', 20, 60, cS)],
                   belt=[('S1', 'S2', 20, 60, dist(S1, S2), 200, 'GT2 6 mm closed loop 200 mm'),
                         ('S2', 'C', 20, 60, dist(S2, C), 200, 'GT2 10 mm closed loop 200 mm (last stage carries the most)')],
                   ratio=27, perTurn=math.pi*sp['roller']*27)
    return out

M = {n: model(n) for n in D}

# ---------------------------------------------------------------- SVG: part drawings at 1:1
INK = '#000'; BLUE = '#2563eb'; TEAL = '#0fb39a'; AMBER = '#d99a00'; RED = '#e11d1d'
def svg_open(w, h, units='mm', extra=''):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(w,1)}{units}" height="{fmt(h,1)}{units}" viewBox="0 0 {fmt(w,2)} {fmt(h,2)}" font-family="IBM Plex Mono, ui-monospace, monospace" {extra}>'

def dimtext(x, y, t, size=4.2, fill=INK, bg='#fff', anchor='middle'):
    wbox = len(t) * size * 0.62 + 2
    x0 = x - wbox/2 if anchor == 'middle' else x - 1
    return (f'<rect x="{x0:.2f}" y="{y-size*0.8:.2f}" width="{wbox:.2f}" height="{size*1.15:.2f}" fill="{bg}"/>'
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}">{html.escape(t)}</text>')

def part_svg(m, pid, for_print=True):
    p = m['parts'][pid]; sp = m['sp']; name = m['name']
    xs = [q[0] for q in p['poly']]; ys = [q[1] for q in p['poly']]
    mx, Mx, my, My = min(xs), max(xs), min(ys), max(ys)
    pad = 14; tb = 44
    W = (Mx - mx) + 2*pad; Hh = (My - my) + 2*pad + tb
    W = max(W, 150)
    X = lambda x: pad + (x - mx); Y = lambda y: pad + (My - y)
    s = [svg_open(W, Hh)]
    s.append(f'<rect width="{W:.2f}" height="{Hh:.2f}" fill="#fff"/>')
    d_ = 'M ' + ' L '.join(f'{X(a):.2f} {Y(b):.2f}' for a, b in p['poly']) + ' Z'
    fill = '#f6efe0' if (pid in ('frame', 'crank') or not sp['foam']) else '#fbfbfb'
    s.append(f'<path d="{d_}" fill="{fill}" stroke="{INK}" stroke-width="0.5"/>')
    # dowel spine slot on foam links
    if sp['foam'] and pid in LINKS:
        a = p['pts'][p['holes'][0][0]]; b = p['pts'][p['holes'][1][0]]
        L = dist(a, b); ux, uy = (b[0]-a[0])/L, (b[1]-a[1])/L; nx, ny = -uy, ux
        s0 = (a[0] + ux*38, a[1] + uy*38); s1 = (b[0] - ux*38, b[1] - uy*38); hw = 3.25
        pts = [(s0[0]+nx*hw, s0[1]+ny*hw), (s1[0]+nx*hw, s1[1]+ny*hw), (s1[0]-nx*hw, s1[1]-ny*hw), (s0[0]-nx*hw, s0[1]-ny*hw)]
        s.append('<path d="M ' + ' L '.join(f'{X(x):.2f} {Y(y):.2f}' for x, y in pts) + f' Z" fill="none" stroke="{BLUE}" stroke-width="0.35" stroke-dasharray="2 1.2"/>')
        mid = ((s0[0]+s1[0])/2, (s0[1]+s1[1])/2)
        s.append(dimtext(X(mid[0]), Y(mid[1]) + 8, f'slot 6.5 × 7 deep × {fmt(dist(s0, s1))}, 1/4 in dowel', 3.2, BLUE))
    # cheek plates (foam parts)
    for (h, c, dia, note) in p['holes']:
        if sp['foam'] and pid not in ('frame', 'crank') and h in PIN_NAMES:
            s.append(f'<circle cx="{X(c[0]):.2f}" cy="{Y(c[1]):.2f}" r="{sp["cheekD"]/2:.2f}" fill="none" stroke="{AMBER}" stroke-width="0.35" stroke-dasharray="1.5 1"/>')
    # holes + centre marks + labels
    for (h, c, dia, note) in p['holes']:
        cx, cy = X(c[0]), Y(c[1])
        s.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{dia/2:.2f}" fill="#fff" stroke="{INK}" stroke-width="0.45"/>')
        s.append(f'<path d="M {cx-4:.2f} {cy:.2f} H {cx+4:.2f} M {cx:.2f} {cy-4:.2f} V {cy+4:.2f}" stroke="{INK}" stroke-width="0.2"/>')
        lab = f'{h} Ø{fmt(dia,1)}'
        s.append(dimtext(cx + max(dia/2, 4) + 2, cy - max(dia/2, 4) - 1.5, lab, 3.4, BLUE, anchor='start'))
        if pid == 'crank':
            s.append(f'<polygon points="' + ' '.join(f'{cx+7.5*math.cos(math.pi/6+k*math.pi/3):.2f},{cy+7.5*math.sin(math.pi/6+k*math.pi/3):.2f}' for k in range(6)) + f'" fill="none" stroke="{RED}" stroke-width="0.35" stroke-dasharray="1 0.8"/>')
    # centre-to-centre dimensions
    hp = [(h, c) for (h, c, _, _) in p['holes'] if h in PIN_NAMES or h == 'S1']
    pairs = [(hp[i][1], hp[j][1]) for i in range(len(hp)) for j in range(i+1, len(hp))]
    named = {h: c for (h, c, _, _) in p['holes']}
    if 'm1' in named: pairs += [(named['O'], named['m1']), (named['m1'], named['m2'])]
    if p['foot']:
        F = p['pts'][p['foot']]; pairs += [(F, p['pts']['J2']), (F, p['pts']['J4'])]
    for (a, b) in pairs:
        if True:
            L = dist(a, b)
            s.append(f'<line x1="{X(a[0]):.2f}" y1="{Y(a[1]):.2f}" x2="{X(b[0]):.2f}" y2="{Y(b[1]):.2f}" stroke="{INK}" stroke-width="0.2" stroke-dasharray="3 1.5"/>')
            mx_, my_ = (X(a[0])+X(b[0]))/2, (Y(a[1])+Y(b[1]))/2
            s.append(f'<rect x="{mx_-9:.2f}" y="{my_-3.6:.2f}" width="18" height="5.2" fill="{INK}"/><text x="{mx_:.2f}" y="{my_+0.4:.2f}" font-size="4" text-anchor="middle" fill="#fff">{fmt(L,1)}</text>')
    if p['foot']:
        fc = p['pts'][p['foot']]
        s.append(f'<circle cx="{X(fc[0]):.2f}" cy="{Y(fc[1]):.2f}" r="1.2" fill="{INK}"/>')
        lab_ = 'F foot point: glue a 10 mm rubber pad under it'; half = len(lab_)*3.2*0.31 + 2
        s.append(dimtext(min(max(X(fc[0]), half), W - half), Y(fc[1]) + p['w']/2 + 5, lab_, 3.2))
    # title block
    ty = Hh - tb + 4
    qty = 2
    mat = ('1/4 in ply, 2 layers glued (11.0)' + (' · red hex = nut recess (see holes)' if pid == 'crank' else '') if pid in ('frame', 'crank') else (sp['stockName'] + (', 1/4 in dowel spine' if pid in LINKS else '') if sp['foam'] else '1/4 in ply (5.5)'))
    s.append(f'<line x1="0" y1="{ty-4:.2f}" x2="{W:.2f}" y2="{ty-4:.2f}" stroke="{INK}" stroke-width="0.4"/>')
    s.append(f'<text x="{pad}" y="{ty+4:.2f}" font-size="5" font-weight="700">{sp["code"]}-{pid.upper()} · {html.escape(p["name"])} · cut {"4, glue in 2 pairs" if pid in ("frame","crank") else qty}</text>')
    segs_ = [html.escape(mat), f'width {fmt(p["w"])}', f'overall {fmt(Mx-mx)} × {fmt(My-my)}', 'all mm · print at 100%']
    lines_, cur_ = [], ''
    for sg_ in segs_:
        t_ = (cur_ + ' · ' + sg_) if cur_ else sg_
        if len(t_) * 3.6 * 0.68 > W - 2*pad and cur_: lines_.append(cur_); cur_ = sg_
        else: cur_ = t_
    lines_.append(cur_)
    for i_, l_ in enumerate(lines_): s.append(f'<text x="{pad}" y="{ty+10+i_*4.6:.2f}" font-size="3.6">{l_}</text>')
    yb = ty + 10 + len(lines_)*4.6 + 3
    s.append(f'<path d="M {pad} {yb:.2f} h 100" stroke="{INK}" stroke-width="0.8"/><path d="M {pad} {yb-2:.2f} v 4 M {pad+50} {yb-1.5:.2f} v 3 M {pad+100} {yb-2:.2f} v 4" stroke="{INK}" stroke-width="0.4"/>')
    s.append(f'<text x="{pad}" y="{yb+5:.2f}" font-size="3.2">100 mm: measure after printing</text>')
    s.append('</svg>')
    return ''.join(s), (W, Hh)

def cheek_svg(m):
    sp = m['sp']; W, Hh = 120, 92; r = sp['cheekD']/2
    s = [svg_open(W, Hh), f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    s.append(f'<circle cx="40" cy="40" r="{r}" fill="#f6efe0" stroke="{INK}" stroke-width="0.5"/><circle cx="40" cy="40" r="5" fill="#fff" stroke="{INK}" stroke-width="0.45"/>')
    s.append(dimtext(40, 40 + r + 6, f'Ø{fmt(sp["cheekD"])} disc, Ø10 hole', 3.6, BLUE))
    n = cheek_count(m)
    s.append(f'<text x="76" y="30" font-size="4.6" font-weight="700">BP-CHEEK</text><text x="76" y="37" font-size="3.6">cut {n}</text><text x="76" y="43" font-size="3.6">1/4 in ply</text><text x="76" y="49" font-size="3.6">glue both faces</text><text x="76" y="55" font-size="3.6">of foam at every</text><text x="76" y="61" font-size="3.6">hole, PVA</text>')
    s.append(f'<path d="M 10 84 h 100" stroke="{INK}" stroke-width="0.8"/><text x="10" y="89.5" font-size="3.2">100 mm: measure after printing</text></svg>')
    return ''.join(s), (W, Hh)

def cheek_count(m):
    n = 0
    for pid in PART_ORDER:
        if pid in ('frame', 'crank'): continue
        n += sum(1 for h in m['parts'][pid]['holes'] if h[0] in PIN_NAMES) * 2
    return n * 2  # two legs

def armbox_parts(m):
    """Drive plates: backpack arm (S1 to wheel) and bike drive box. Doubled 1/4 ply, 608 bearings."""
    dr = m['drive']
    if m['name'] == 'backpack':
        S1, W, R = dr['S1'], dr['W'], dr['R']
        # local coordinates: S1 at origin
        cen = [S1, R, W]
        holes = [('S1', S1, 22.0, '608 bearing, arm pivots on S1'), ('R', R, 22.0, '608 bearing, roller shaft (fixed)'), ('W', W, 8.2, 'wheel axle M8')]
        L = dist(S1, R); ux, uy = (R[0]-S1[0])/L, (R[1]-S1[1])/L; nx, ny = -uy, ux
        mid = (S1[0] + ux*L*0.45, S1[1] + uy*L*0.45)
        Lw = dist(S1, W); wx, wy = (W[0]-S1[0])/Lw, (W[1]-S1[1])/Lw
        tp = (S1[0] + ux*L*0.45 + nx*20, S1[1] + uy*L*0.45 + ny*20)
        sa = (S1[0] + ux*L*0.62 + nx*20, S1[1] + uy*L*0.62 + ny*20)
        w1 = (W[0] - wx*130, W[1] - wy*130); w2 = (W[0] - wx*500, W[1] - wy*500)
        holes += [('tp', tp, 6.5, 'tensioner lever pivot, M6 × 30'), ('sa', sa, 5.0, 'tensioner spring anchor (screw eye)'),
                  ('w1', w1, 6.5, 'weight bar, M6 × 30'), ('w2', w2, 6.5, 'weight bar, M6 × 30')]
        lev = dict(id='tension', name='Tensioner lever', cen=[(0, 0), (100, 0)], holes=[('tp', (0, 0), 6.5, 'pivot on the arm, M6 × 30 + nylock, loose'), ('ti', (100, 0), 5.2, 'GT2 20T toothed idler on M5 × 30'), ('sk', (60, 0), 4.0, 'spring hook')], w=26, qty='cut 1, single 1/4 in ply (5.5)')
        return [dict(id='arm', name='Wheel arm', cen=cen, holes=holes, w=60, qty='cut 2, glue as 1 pair (11.0), 1 per rig'), lev]
    else:
        C, R, S1, S2 = dr['C'], dr['R'], dr['S1'], dr['S2']
        holes = [('C', C, 22.0, '608, box hinges on crank shaft'), ('R', R, 22.0, '608, roller shaft'), ('S1', S1, 22.0, '608'), ('S2', S2, 22.0, '608')]
        def towards(p, q, d_):
            L_ = dist(p, q); return (p[0] + (q[0]-p[0])*d_/L_, p[1] + (q[1]-p[1])*d_/L_)
        cx_ = sum(p[0] for p in (C, R, S1, S2))/4; cy_ = sum(p[1] for p in (C, R, S1, S2))/4
        mcr = ((C[0]+R[0])/2, (C[1]+R[1])/2); Lcr = dist(C, R); ncr = ((R[1]-C[1])/Lcr, -(R[0]-C[0])/Lcr)
        if ncr[1] > 0: ncr = (-ncr[0], -ncr[1])
        m12 = ((S1[0]+S2[0])/2, (S1[1]+S2[1])/2)
        holes += [('t1', (C[0]+10, C[1]-28), 6.5, 'standoff M6 × 80'), ('t2', (mcr[0]+ncr[0]*25, mcr[1]+ncr[1]*25), 6.5, 'standoff M6 × 80'), ('t3', (R[0]+25, R[1]-15), 6.5, 'standoff M6 × 80'),
                  ('sa', (C[0]-58, C[1]+8), 5.0, 'spring anchor on the tail behind the hinge (outer plate); spring straight up to the rack board pushes the roller down')]
        return [dict(id='box', name='Drive box plate', cen=[C, R, S1, S2, (C[0]-58, C[1]+8)], holes=holes, w=70, qty='cut 4, glue as 2 pairs (11.0)')]

def armbox_svg(m, a):
    sp = m['sp']; poly = outline(a['cen'], a['w']/2)
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    mx, Mx, my, My = min(xs), max(xs), min(ys), max(ys); pad = 14; tb = 34
    W = max(150, Mx - mx + 2*pad) + 45; Hh = max(My - my + 2*pad + tb, 70)
    X = lambda x: pad + (x - mx); Y = lambda y: pad + (My - y)
    s = [svg_open(W, Hh), f'<rect width="{W:.2f}" height="{Hh:.2f}" fill="#fff"/>']
    s.append('<path d="M ' + ' L '.join(f'{X(p[0]):.2f} {Y(p[1]):.2f}' for p in poly) + f' Z" fill="#f6efe0" stroke="{INK}" stroke-width="0.5"/>')
    for (h, c, dia, note) in a['holes']:
        s.append(f'<circle cx="{X(c[0]):.2f}" cy="{Y(c[1]):.2f}" r="{dia/2}" fill="#fff" stroke="{INK}" stroke-width="0.45"/>')
        s.append(dimtext(X(c[0]) + dia/2 + 2, Y(c[1]) - dia/2 - 1.5, f'{h} Ø{fmt(dia,1)}', 3.4, BLUE, anchor='start'))
    if a.get('slot'):
        sl = outline(a['slot'], 4.1, 24)
        s.append('<path d="M ' + ' L '.join(f'{X(p[0]):.2f} {Y(p[1]):.2f}' for p in sl) + f' Z" fill="#fff" stroke="{INK}" stroke-width="0.45"/>')
        c0 = ((a['slot'][0][0]+a['slot'][1][0])/2, (a['slot'][0][1]+a['slot'][1][1])/2)
        s.append(dimtext(X(c0[0]) + 10, Y(c0[1]), 'idler slot 8.2 × 34, centre ' + fmt(dist(a['holes'][0][1], c0), 1) + ' from S1', 3.4, BLUE, anchor='start'))
    hs = a['holes']
    main = [h for h in hs if h[0] in ('C', 'R', 'S1', 'S2', 'W')] or hs[:2]
    aux = [h for h in hs if h not in main]
    pairs = [(main[i], main[j]) for i in range(len(main)) for j in range(i+1, len(main))]
    for h in aux:
        if a['id'] == 'tension': continue
        pairs.append((h, min(main, key=lambda q: dist(q[1], h[1]))))
    # coordinate table from the first hole
    o = hs[0][1]
    for i, h in enumerate(hs):
        s.append(f'<text x="{W - 4:.2f}" y="{8 + i*4.6:.2f}" font-size="3.4" text-anchor="end">{h[0]}: {fmt(h[1][0]-o[0],1)}, {fmt(h[1][1]-o[1],1)}</text>')
    s.append(f'<text x="{W - 4:.2f}" y="{8 + len(hs)*4.6:.2f}" font-size="3" text-anchor="end">x, y from {hs[0][0]}, y up</text>')
    for (hA, hB) in pairs:
        if True:
            A_, B_ = hA[1], hB[1]
            mx_, my_ = (X(A_[0])+X(B_[0]))/2, (Y(A_[1])+Y(B_[1]))/2
            s.append(f'<line x1="{X(A_[0]):.2f}" y1="{Y(A_[1]):.2f}" x2="{X(B_[0]):.2f}" y2="{Y(B_[1]):.2f}" stroke="{INK}" stroke-width="0.2" stroke-dasharray="3 1.5"/>')
            s.append(f'<rect x="{mx_-9:.2f}" y="{my_-3.6:.2f}" width="18" height="5.2" fill="{INK}"/><text x="{mx_:.2f}" y="{my_+0.4:.2f}" font-size="4" text-anchor="middle" fill="#fff">{fmt(dist(A_,B_),1)}</text>')
    ty = Hh - tb + 4
    s.append(f'<line x1="0" y1="{ty-4:.2f}" x2="{W:.2f}" y2="{ty-4:.2f}" stroke="{INK}" stroke-width="0.4"/>')
    s.append(f'<text x="{pad}" y="{ty+4:.2f}" font-size="5" font-weight="700">{sp["code"]}-{a["id"].upper()} · {a["name"]} · {a["qty"]}</text>')
    s.append(f'<text x="{pad}" y="{ty+10:.2f}" font-size="3.6">1/4 in ply · width {a["w"]} · overall {fmt(Mx-mx)} × {fmt(My-my)} · all mm · print at 100%</text>')
    s.append(f'<path d="M {pad} {ty+17:.2f} h 100" stroke="{INK}" stroke-width="0.8"/><text x="{pad+103}" y="{ty+18.5:.2f}" font-size="3.2">100 mm</text></svg>')
    return ''.join(s), (W, Hh)

# ---------------------------------------------------------------- DXF (R12, mm)
def dxf(entities):
    o = ['0', 'SECTION', '2', 'HEADER', '9', '$INSUNITS', '70', '4', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
    for e in entities:
        if e[0] == 'LINE':
            _, layer, a, b = e
            o += ['0', 'LINE', '8', layer, '10', f'{a[0]:.3f}', '20', f'{a[1]:.3f}', '30', '0', '11', f'{b[0]:.3f}', '21', f'{b[1]:.3f}', '31', '0']
        else:
            _, layer, c, r = e
            o += ['0', 'CIRCLE', '8', layer, '10', f'{c[0]:.3f}', '20', f'{c[1]:.3f}', '30', '0', '40', f'{r:.3f}']
    o += ['0', 'ENDSEC', '0', 'EOF']
    return '\n'.join(o) + '\n'

def part_dxf(poly, holes, extra_circles=()):
    ents = []
    for i in range(len(poly)):
        ents.append(('LINE', 'CUT', poly[i], poly[(i+1) % len(poly)]))
    for (h, c, dia, note) in holes: ents.append(('CIRCLE', 'CUT', c, dia/2))
    for (layer, c, r) in extra_circles: ents.append(('CIRCLE', layer, c, r))
    return dxf(ents)

# ---------------------------------------------------------------- views
def leg_world(m, P):
    """map leg units to world mm for the build"""
    sg = m['sg']; d = m['d']
    if m['name'] == 'backpack':
        return lambda k: (P[k]['x']*sg, d['Hc'] + P[k]['y']*sg)
    mx, my = d['b']['mountX'], d['b']['mountY']
    return lambda k: (mx + P[k]['x']*sg, my + P[k]['y']*sg)

def poly_path(pts, X, Y):
    return 'M ' + ' L '.join(f'{X(a):.1f} {Y(b):.1f}' for a, b in pts)

def draw_leg(m, P, X, Y, s, col=INK, wscale=1.0, faint=False):
    w = leg_world(m, P); o = []
    sw = max(0.8, m['sp']['w'] * s * wscale)
    for pid in PART_ORDER:
        part = m['parts'][pid]
        for a_, b_ in part['segs']:
            if a_ not in P or b_ not in P: continue
            A_, B_ = w(a_), w(b_)
            o.append(f'<line x1="{X(A_[0]):.1f}" y1="{Y(A_[1]):.1f}" x2="{X(B_[0]):.1f}" y2="{Y(B_[1]):.1f}" stroke="{col}" stroke-width="{sw:.2f}" stroke-linecap="round" opacity="{0.35 if faint else 1}"/>')
    if not faint:
        for pid in PART_ORDER:
            part = m['parts'][pid]
            for a_, b_ in part['segs']:
                if a_ not in P or b_ not in P: continue
                A_, B_ = w(a_), w(b_)
                o.append(f'<line x1="{X(A_[0]):.1f}" y1="{Y(A_[1]):.1f}" x2="{X(B_[0]):.1f}" y2="{Y(B_[1]):.1f}" stroke="#fff" stroke-width="{max(0.3, sw-2):.2f}" stroke-linecap="round"/>')
        for k in PIN_NAMES:
            if k in P:
                c = w(k); o.append(f'<circle cx="{X(c[0]):.1f}" cy="{Y(c[1]):.1f}" r="{max(1.2, 6*s*m["sg"]/3):.1f}" fill="{INK}"/>')
    return ''.join(o)

def plate_svg(m, cellW=240, cellH=200):
    d = m['d']; frames = d['frames']; sg = m['sg']; name = m['name']
    W, Hh = cellW*4, cellH*4
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace">', f'<rect width="{W}" height="{Hh}" fill="#111"/>']
    for q in range(16):
        cx, cy = (q % 4)*cellW, (q // 4)*cellH
        s.append(f'<g transform="translate({cx+3},{cy+3})"><rect width="{cellW-6}" height="{cellH-6}" fill="#f3ead8"/>')
        f = frames[q]; c = f['c']
        if name == 'backpack':
            hipX, hipY = d['b']['Lb'], m['d']['HMhip']
            left, right = -1100, hipX + 450
            sc = min((cellW-14)/(right-left), (cellH-16)/1900)
            X = lambda x: 7 + (x-left)*sc; Y = lambda y: cellH - 12 - y*sc
            # grid
            for gx in range(-1000, int(right), 250): s.append(f'<line x1="{X(gx):.1f}" y1="{Y(0):.1f}" x2="{X(gx):.1f}" y2="{Y(1800):.1f}" stroke="#d8ccb4" stroke-width="0.5"/>')
            s.append(f'<line x1="0" y1="{Y(0):.1f}" x2="{cellW}" y2="{Y(0):.1f}" stroke="{INK}" stroke-width="1"/>')
            # far legs
            P1 = f['legs'][1]['P']; s.append(draw_leg(m, P1, X, Y, sc, '#6b7fa8', faint=True))
            kn, an = human_leg(c + .5); hip = (hipX, hipY)
            s.append(f'<path d="{poly_path([hip, (hip[0]+kn[0], hip[1]+kn[1]), (hip[0]+an[0], hip[1]+an[1])], X, Y)}" stroke="#6b7fa8" stroke-width="{max(1.5,110*sc):.1f}" fill="none" stroke-linecap="round"/>')
            # body: rump, drawbar, torso
            s.append(f'<path d="{poly_path([(hipX-170, hipY+40), (hipX-170, hipY+300), (-150, d["Hc"]+260), (-560, d["Hc"]+160), (-640, d["Hc"]-20), (-120, d["Hc"]-60)], X, Y)} Z" fill="rgba(0,0,0,.07)" stroke="#8a7a5c" stroke-width="0.6" stroke-dasharray="3 2"/>')
            s.append(f'<line x1="{X(hipX-120):.1f}" y1="{Y(hipY):.1f}" x2="{X(0):.1f}" y2="{Y(d["Hc"]+60):.1f}" stroke="{INK}" stroke-width="{max(1,24*sc):.1f}"/>')
            sh = (hipX + 50, hipY + .288*H)
            s.append(f'<line x1="{X(hipX):.1f}" y1="{Y(hipY):.1f}" x2="{X(sh[0]):.1f}" y2="{Y(sh[1]):.1f}" stroke="{INK}" stroke-width="{max(2,300*sc):.1f}" stroke-linecap="round"/>')
            s.append(f'<circle cx="{X(sh[0]+30):.1f}" cy="{Y(sh[1]+175):.1f}" r="{110*sc:.1f}" fill="#f3ead8" stroke="{INK}" stroke-width="1"/>')
            # ground wheel and arm
            dr = m['drive']
            s.append(f'<line x1="{X(dr["S1"][0]):.1f}" y1="{Y(dr["S1"][1]):.1f}" x2="{X(dr["W"][0]):.1f}" y2="{Y(dr["W"][1]):.1f}" stroke="#444" stroke-width="{max(1,30*sc):.1f}"/>')
            s.append(f'<circle cx="{X(dr["W"][0]):.1f}" cy="{Y(dr["W"][1]):.1f}" r="{55*sc:.1f}" fill="#f3ead8" stroke="#444" stroke-width="1"/>')
            P0 = f['legs'][0]['P']; s.append(draw_leg(m, P0, X, Y, sc))
            # near human leg
            kn, an = human_leg(c)
            s.append(f'<path d="{poly_path([hip, (hip[0]+kn[0], hip[1]+kn[1]), (hip[0]+an[0], hip[1]+an[1]), (hip[0]+an[0]+.1*H, max(0, hip[1]+an[1]-.035*H))], X, Y)}" stroke="{INK}" stroke-width="{max(2,130*sc):.1f}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
            for li, L in enumerate(f['legs']):
                if L['down']:
                    w = leg_world(m, L['P'])('F')
                    s.append(f'<rect x="{X(w[0])-7:.1f}" y="{Y(0)+1:.1f}" width="14" height="5" fill="{TEAL if li == 0 else "#fff"}" stroke="{TEAL}" stroke-width="1.5"/>')
            for hl, col in ((c, INK), (c+.5, '#6b7fa8')):
                kn_, an_ = human_leg(hl)
                if hip[1] + an_[1] < 60: s.append(f'<rect x="{X(hip[0]+an_[0])-7:.1f}" y="{Y(0)+1:.1f}" width="14" height="5" fill="{col}"/>')
        else:
            g = d['g']; dr = m['drive']
            left, right = -620, g['wb'] + g['r'] + 30
            sc = min((cellW-14)/(right-left), (cellH-16)/1650)
            X = lambda x: 7 + (x-left)*sc; Y = lambda y: cellH - 12 - y*sc
            s.append(f'<line x1="0" y1="{Y(0):.1f}" x2="{cellW}" y2="{Y(0):.1f}" stroke="{INK}" stroke-width="1"/>')
            tick = -(c * dr['perTurn']) % 100
            for gx in range(int(left), int(right), 100): s.append(f'<line x1="{X(gx+tick):.1f}" y1="{Y(0):.1f}" x2="{X(gx+tick):.1f}" y2="{Y(0)+3:.1f}" stroke="{INK}" stroke-width="0.6"/>')
            P1 = f['legs'][1]['P']; s.append(draw_leg(m, P1, X, Y, sc, '#6b7fa8', faint=True))
            for wc in ((0, g['r']), (g['wb'], g['r'])):
                s.append(f'<circle cx="{X(wc[0]):.1f}" cy="{Y(wc[1]):.1f}" r="{g["r"]*sc:.1f}" fill="none" stroke="{INK}" stroke-width="1.4"/>')
                a0 = -c * dr['perTurn'] / g['r']
                for i in range(6):
                    a = a0 + i*math.pi/3
                    s.append(f'<line x1="{X(wc[0]):.1f}" y1="{Y(wc[1]):.1f}" x2="{X(wc[0]+math.cos(a)*(g["r"]-20)):.1f}" y2="{Y(wc[1]+math.sin(a)*(g["r"]-20)):.1f}" stroke="{INK}" stroke-width="0.4"/>')
            BB, sC, hT, hB = g['BB'], g['seatC'], g['headT'], g['headB']
            rA = (0, g['r']); fA = (g['wb'], g['r'])
            fw = max(1, 9*sc)
            s.append(f'<path d="{poly_path([rA, (BB["x"],BB["y"]), (sC["x"],sC["y"]), rA], X, Y)}" stroke="{INK}" stroke-width="{fw:.1f}" fill="none"/>')
            s.append(f'<path d="{poly_path([(sC["x"],sC["y"]), (hT["x"],hT["y"]), (hB["x"],hB["y"]), (BB["x"],BB["y"])], X, Y)}" stroke="{INK}" stroke-width="{fw:.1f}" fill="none"/>')
            s.append(f'<path d="{poly_path([(hB["x"],hB["y"]), fA], X, Y)}" stroke="{INK}" stroke-width="{fw:.1f}" fill="none"/>')
            rk = g['rack']
            s.append(f'<path d="{poly_path([(rk["x0"], rk["y"]), (rk["x1"], rk["y"])], X, Y)}" stroke="{INK}" stroke-width="{max(1.5,10*sc):.1f}"/>')
            s.append(f'<path d="{poly_path([(rk["x0"]+40, rk["y"]), rA], X, Y)}" stroke="{INK}" stroke-width="{max(1,6*sc):.1f}"/>')
            # rider
            hip = (g['hip']['x'], g['hip']['y']); sh = (hip[0] + .21*H, hip[1] + .2*H)
            pa = -2*math.pi*c*dr['perTurn']/ (math.pi*0.0 + 2*math.pi*g['r']) * (g['r']*2*math.pi/ (2*math.pi*170)) * 0.0
            Lt, Ls2 = g['Lt'], g['Ls2']
            for side, col, ww in ((1, '#6b7fa8', 120), (0, INK, 140)):
                ang = -2*math.pi*c*dr['perTurn']/2100 + side*math.pi
                p = (BB['x'] + 170*math.cos(ang), BB['y'] + 170*math.sin(ang))
                dx, dy = p[0]-hip[0], p[1]-hip[1]; dd = min(math.hypot(dx, dy), Lt+Ls2-1); a0 = math.atan2(dy, dx)
                cA = math.acos(max(-1, min(1, (Lt*Lt + dd*dd - Ls2*Ls2)/(2*Lt*dd))))
                kn = (hip[0] + Lt*math.cos(a0+cA), hip[1] + Lt*math.sin(a0+cA))
                s.append(f'<path d="{poly_path([hip, kn, p], X, Y)}" stroke="{col}" stroke-width="{max(1.2,ww*sc):.1f}" fill="none" stroke-linecap="round"/>')
            bar = (g['bar']['x'], g['bar']['y'])
            s.append(f'<path d="{poly_path([hip, sh, bar], X, Y)}" stroke="{INK}" stroke-width="{max(2,240*sc):.1f}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
            s.append(f'<circle cx="{X(sh[0]+120):.1f}" cy="{Y(sh[1]+170):.1f}" r="{108*sc:.1f}" fill="#f3ead8" stroke="{INK}" stroke-width="1"/>')
            s.append(f'<circle cx="{X(dr["R"][0]):.1f}" cy="{Y(dr["R"][1]):.1f}" r="{max(1.5,26*sc):.1f}" fill="#fff" stroke="{INK}" stroke-width="0.8"/>')
            P0 = f['legs'][0]['P']; s.append(draw_leg(m, P0, X, Y, sc))

        s.append(f'<text x="6" y="{cellH-16}" font-size="13" font-style="italic" fill="{INK}">{q+1}</text></g>')
    s.append('</svg>')
    return ''.join(s)

def zr(txt):
    a_, b_ = txt.replace('…', ' ').split()[:2]
    return float(a_), float(b_)

def front_svg(m):
    """z map seen from behind: every part and every drive item at its z, + = right side"""
    sp = m['sp']; zL = m['zL']; name = m['name']; dr = m['drive']
    zmax = max(zL[-1] + m['layerT'][-1], m['rodLen']/2, 150) + 15
    W = 980; LC = 190; rowH = 26
    rows = [(m['parts'][p]['name'] + f' · L{m["parts"][p]["layer"]}', 'part', p) for p in PART_ORDER] + [(sh[0], 'shaft', sh) for sh in dr['shafts']]
    Hh = 60 + rowH*len(rows) + 50
    sx = (W - LC - 90) / (2*zmax); Xz = lambda z: LC + 10 + (z + zmax)*sx
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    s.append(f'<text x="10" y="18" font-weight="700">Z MAP · seen from behind · left leg ← centreline → right leg · mm</text>')
    y0 = 40
    # reference lines
    refs = []
    if name == 'backpack': refs = [(-.035*H, RED, 'your foot'), (.035*H, RED, 'your foot')]
    else: refs = [(-67, INK, 'strut'), (67, INK, 'strut'), (-28, '#888', 'tire'), (28, '#888', 'tire')]
    for z, col, lab in refs:
        s.append(f'<line x1="{Xz(z):.1f}" y1="{y0-6}" x2="{Xz(z):.1f}" y2="{Hh-40}" stroke="{col}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    s.append(f'<text x="{Xz(refs[1][0])+3:.1f}" y="{y0-2}" font-size="9" fill="{refs[1][1]}">{refs[1][2]} ±{fmt(abs(refs[1][0]))}</text>')
    if len(refs) > 2: s.append(f'<text x="{Xz(refs[3][0])+3:.1f}" y="{Hh-44}" font-size="9" fill="#666">tire ±28</text>')
    s.append(f'<line x1="{Xz(0):.1f}" y1="{y0-10}" x2="{Xz(0):.1f}" y2="{Hh-36}" stroke="#999"/>')
    for i, (lab, kind, ref) in enumerate(rows):
        y = y0 + i*rowH
        s.append(f'<text x="10" y="{y+15}" font-size="10" font-weight="{700 if kind=="shaft" else 400}">{html.escape(lab)}</text>')
        if kind == 'part':
            p = m['parts'][ref]; z1 = zL[p['layer']]; z2 = z1 + p['thick']
            for sg_ in (1, -1):
                xa, xb = sorted((Xz(sg_*z1), Xz(sg_*z2)))
                fill = '#f6efe0' if (ref in ('frame', 'crank') or not sp['foam']) else '#fff'
                s.append(f'<rect x="{xa:.1f}" y="{y+3}" width="{xb-xa:.1f}" height="{rowH-8}" fill="{fill}" stroke="{INK}" stroke-width="0.8"/>')
            s.append(f'<text x="{Xz(z2)+4:.1f}" y="{y+15}" font-size="9">{fmt(z1,1)}–{fmt(z2,1)}</text>')
        else:
            sh = ref; zs = [zr(r_) for (_, r_) in sh[2]]
            s.append(f'<line x1="{Xz(min(a_ for a_, b_ in zs)):.1f}" y1="{y+rowH/2-1:.1f}" x2="{Xz(max(b_ for a_, b_ in zs)):.1f}" y2="{y+rowH/2-1:.1f}" stroke="#555" stroke-width="3"/>')
            for k, (lab2, r_) in enumerate(sh[2]):
                za, zb = zr(r_)
                l2 = lab2.lower()
                fill = TEAL if 'pulley' in l2 else AMBER if 'spur' in l2 else INK if ('collar' in l2 or 'nylock' in l2) else '#fff' if ('roller' in l2 or 'wheel' in l2 and 'arm' not in l2) else '#f6efe0'
                s.append(f'<rect x="{Xz(za):.1f}" y="{y+3}" width="{max(1.5,(zb-za)*sx):.1f}" height="{rowH-8}" fill="{fill}" stroke="{INK}" stroke-width="0.7"/>')
                tx = '#fff' if fill == INK else INK
                if (zb-za)*sx > 12: s.append(f'<text x="{Xz((za+zb)/2):.1f}" y="{y+15}" font-size="8.5" text-anchor="middle" fill="{tx}">{k+1}</text>')
    for z in range(-int(zmax//50)*50, int(zmax)+1, 50):
        s.append(f'<line x1="{Xz(z):.1f}" y1="{Hh-34}" x2="{Xz(z):.1f}" y2="{Hh-28}" stroke="{INK}"/><text x="{Xz(z):.1f}" y="{Hh-16}" font-size="9" text-anchor="middle">{z}</text>')
    s.append(f'<text x="10" y="{Hh-16}" font-size="9">numbers = items in the shaft table</text>')
    s.append('</svg>')
    return ''.join(s)

def drive_svg(m):
    dr = m['drive']; sp = m['sp']; d = m['d']
    W, Hh = 900, 600
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    legend = []
    def mark(X, Y, key, p, txt, left=False):
        bx = X(p[0]) - 11 - 8*len(key) if left else X(p[0]) + 5; by = Y(p[1]) + (3 if left else -17)
        s.append(f'<circle cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="3.2" fill="{INK}"/><rect x="{bx:.1f}" y="{by:.1f}" width="{8*len(key)+6}" height="14" fill="{BLUE}"/><text x="{bx+3:.1f}" y="{by+11:.1f}" fill="#fff" font-size="10" font-weight="700">{key}</text>')
        legend.append(f'{key}  ({fmt(p[0])}, {fmt(p[1])})  {txt}')
    if m['name'] == 'backpack':
        O, S1, W_, R = dr['O'], dr['S1'], dr['W'], dr['R']
        left, right, bot, top = -1150, 900, -20, 1150
        sc = min((W-300)/(right-left), (Hh-110)/(top-bot)); X = lambda x: 280 + (x-left)*sc; Y = lambda y: Hh - 30 - (y-bot)*sc
        s.append(f'<line x1="270" y1="{Y(0):.1f}" x2="{W}" y2="{Y(0):.1f}" stroke="{INK}"/>')
        P = d['frames'][0]['legs'][0]['P']; s.append(draw_leg(m, P, X, Y, sc, '#9aa', faint=True))
        hipX, hipY = d['b']['Lb'], d['HMhip']
        s.append(f'<rect x="{X(hipX-60):.1f}" y="{Y(hipY+520):.1f}" width="{140*sc:.1f}" height="{560*sc:.1f}" fill="none" stroke="{INK}" stroke-dasharray="4 3"/>')
        s.append(f'<rect x="{X(hipX-80):.1f}" y="{Y(hipY+80):.1f}" width="{12*sc:.1f}" height="{160*sc:.1f}" fill="#f6efe0" stroke="{INK}"/>')
        topK = O[1] + 85 + 44.5
        s.append(f'<line x1="{X(hipX-80):.1f}" y1="{Y(hipY):.1f}" x2="{X(-130):.1f}" y2="{Y(topK+6):.1f}" stroke="{INK}" stroke-width="{max(2,23.4*sc):.1f}"/>')
        s.append(f'<rect x="{X(-140):.1f}" y="{Y(topK):.1f}" width="{140*sc:.1f}" height="{89*sc:.1f}" fill="#f6efe0" stroke="{INK}"/>')
        s.append(f'<line x1="{X(S1[0]):.1f}" y1="{Y(S1[1]):.1f}" x2="{X(W_[0]):.1f}" y2="{Y(W_[1]):.1f}" stroke="#555" stroke-width="{60*sc:.1f}" stroke-linecap="round" opacity=".45"/>')
        s.append(f'<line x1="{X(R[0]):.1f}" y1="{Y(R[1]):.1f}" x2="{X(S1[0]):.1f}" y2="{Y(S1[1]):.1f}" stroke="{TEAL}" stroke-width="2"/>')
        s.append(f'<circle cx="{X(W_[0]):.1f}" cy="{Y(W_[1]):.1f}" r="{55*sc:.1f}" fill="#fff" stroke="{INK}" stroke-width="1.4"/>')
        s.append(f'<circle cx="{X(R[0]):.1f}" cy="{Y(R[1]):.1f}" r="{dr["rollR"]*sc:.1f}" fill="#fff" stroke="{INK}" stroke-width="1.2"/>')
        s.append(f'<circle cx="{X(O[0]):.1f}" cy="{Y(O[1]):.1f}" r="{30*sc:.1f}" fill="{AMBER}" opacity=".7" stroke="{INK}"/>')
        mid = (S1[0] + (R[0]-S1[0])*.45, S1[1] + (R[1]-S1[1])*.45)
        mark(X, Y, 'O', O, 'crank rod, 60T spur'); mark(X, Y, 'S1', S1, 'arm pivot, 20T spur + 40T pulley', left=True)
        mark(X, Y, 'T', (S1[0] + (R[0]-S1[0])*.45, S1[1] + (R[1]-S1[1])*.45), 'tensioner pivot tp; lever points up toward S1'); mark(X, Y, 'R', R, '55 roller + 16T pulley')
        mark(X, Y, 'W', W_, '110 ground wheel')
        mark(X, Y, 'K', (-70, O[1]+85), 'saddle block, 2×4 (38 × 89) × 140, bolts at m1 m2')
        mark(X, Y, 'D', ((hipX-80-130)/2, (hipY+topK)/2), f'drawbar 3/4 in EMT, cut {fmt(math.hypot(hipX-80+130, topK-hipY)+20)}, rear flattened 150, front 60')
        mark(X, Y, 'L', (hipX-80, hipY+80), 'lumbar plate + 3 in butt hinge')
        title = 'BACKPACK DRIVE · seen from the rig\'s right side · walking to the right'
        chain = 'wheel clockwise → roller anticlockwise → belt → S1 anticlockwise → spur → crank clockwise'
        rule = f'one crank turn = π × 55 × 2.5 × 3 = {fmt(dr["perTurn"])} mm of ground = one rig stride'
    else:
        C, R, S1, S2, hub, r = dr['C'], dr['R'], dr['S1'], dr['S2'], dr['hub'], dr['r']
        g = d['g']
        left, right, bot, top = -300, 120, 560, 860
        sc = min((W-300)/(right-left), (Hh-110)/(top-bot)); X = lambda x: 280 + (x-left)*sc; Y = lambda y: Hh - 30 - (y-bot)*sc
        s.append(f'<defs><clipPath id="cp"><rect x="270" y="70" width="{W-270}" height="{Hh-70}"/></clipPath></defs><g clip-path="url(#cp)">')
        s.append(f'<circle cx="{X(hub[0]):.1f}" cy="{Y(hub[1]):.1f}" r="{r*sc:.1f}" fill="none" stroke="{INK}" stroke-width="3"/>')
        rk = g['rack']
        s.append(f'<line x1="{X(rk["x0"]):.1f}" y1="{Y(rk["y"]):.1f}" x2="{X(rk["x1"]):.1f}" y2="{Y(rk["y"]):.1f}" stroke="{INK}" stroke-width="5"/>')
        s.append(f'<line x1="{X(rk["x0"]+40):.1f}" y1="{Y(rk["y"]):.1f}" x2="{X(0):.1f}" y2="{Y(r):.1f}" stroke="{INK}" stroke-width="2" stroke-dasharray="6 3"/>')
        s.append(f'<rect x="{X(-260):.1f}" y="{Y(rk["y"]+18):.1f}" width="{420*sc:.1f}" height="{18*sc:.1f}" fill="#f6efe0" stroke="{INK}"/>')
        poly = outline([C, R, S1, S2], 28)
        s.append(f'<path d="{poly_path(poly, X, Y)} Z" fill="#f6efe0" stroke="{INK}" opacity=".85"/>')
        for a_, b_, col in ((S1, S2, TEAL), (S2, C, TEAL)):
            s.append(f'<line x1="{X(a_[0]):.1f}" y1="{Y(a_[1]):.1f}" x2="{X(b_[0]):.1f}" y2="{Y(b_[1]):.1f}" stroke="{col}" stroke-width="4"/>')
        s.append(f'<circle cx="{X(R[0]):.1f}" cy="{Y(R[1]):.1f}" r="{10*sc:.1f}" fill="{AMBER}" stroke="{INK}"/><circle cx="{X(S1[0]):.1f}" cy="{Y(S1[1]):.1f}" r="{30*sc:.1f}" fill="{AMBER}" opacity=".6" stroke="{INK}"/>')
        s.append(f'<circle cx="{X(R[0]):.1f}" cy="{Y(R[1]):.1f}" r="{26*sc:.1f}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
        s.append('</g>')
        mark(X, Y, 'C', C, 'crank rod, 60T pulley (10 mm); box hinge')
        mark(X, Y, 'R', R, '52 roller + 20T spur')
        mark(X, Y, 'S1', S1, '60T spur + 20T pulley')
        mark(X, Y, 'S2', S2, '60T + 20T (10 mm) pulleys')
        legend.append(f'rack top {fmt(rk["y"])}; dashed line = rack strut (measure yours)')
        legend.append(f'worst clearance to tire or rack: {fmt(dr["clear"])} mm'); legend.append('box is outside the strut in z (Z map)')
        title = 'BIKE DRIVE · seen from the bike\'s right side · riding to the right'
        chain = 'tire clockwise → roller anticlockwise → spur → S1 clockwise → belts → crank clockwise'
        rule = f'1:27 · {fmt(d["rpm"])} rpm at 16 km/h · box hinges on the crank rod; a spring pulls the roller onto the tire'
    s.append(f'<text x="14" y="20" font-weight="700">{title}</text><text x="14" y="38">{chain}</text><text x="14" y="56">{rule}</text>')
    s.append(f'<text x="14" y="90" font-size="10" font-weight="700">x, y in mm · {"axle O at x 0, floor y 0" if m["name"]=="backpack" else "rear hub x 0, floor y 0"}</text>')
    for i, t in enumerate(legend):
        s.append(f'<text x="14" y="{110 + i*18}" font-size="10">{html.escape(t)}</text>')
    s.append('</svg>')
    return ''.join(s)

def overview_svg(m):
    """one still of the full rig, side, with key dimensions"""
    d = m['d']; f = d['frames'][2]
    W, Hh = 760, 500
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    inner = plate_cell(m, 2, W, Hh)
    s.append(inner)
    s.append('</svg>')
    return ''.join(s)

def plate_cell(m, q, W, Hh):
    big = plate_svg(m, W, Hh)
    # extract cell q from a 4x4 plate drawn at (W,Hh) per cell: translate and clip
    return f'<svg x="0" y="0" width="{W}" height="{Hh}" viewBox="{(q%4)*W} {(q//4)*Hh} {W} {Hh}">{big[big.index(">")+1:-6]}</svg>'

def mounts_svg(m):
    """mount parts with dimensions (not to scale on screen; all numbers in mm)"""
    W, Hh = 900, 560
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    def rect(x, y, w, h, fill='#f6efe0'): s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{INK}" stroke-width="1"/>')
    def hole(x, y, r=4): s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{INK}"/>')
    def txt(x, y, t, size=11, w=400, anchor='start', col=INK): s.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" text-anchor="{anchor}" fill="{col}">{html.escape(t)}</text>')
    def dim(x1, y1, x2, y2, t, off=14):
        if y1 == y2:
            s.append(f'<path d="M {x1} {y1+off} H {x2} M {x1} {y1+off-4} v 8 M {x2} {y1+off-4} v 8" stroke="{BLUE}" stroke-width="0.8"/>'); txt((x1+x2)/2, y1+off-3, t, 10, 400, 'middle', BLUE)
        else:
            s.append(f'<path d="M {x1-off} {y1} V {y2} M {x1-off-4} {y1} h 8 M {x1-off-4} {y2} h 8" stroke="{BLUE}" stroke-width="0.8"/>'); txt(x1-off-6, (y1+y2)/2+4, t, 10, 400, 'end', BLUE)
    if m['name'] == 'backpack':
        k = 2.0  # px per mm
        txt(14, 22, 'BACKPACK MOUNT PARTS · all mm', 12, 700)
        # saddle block, side view (x along the rig, y up)
        x0, y0 = 60, 60
        txt(x0, y0-10, 'BP-BLOCK · 2×4 (38 × 89) × 140 · side view, front of rig to the right', 10, 700)
        rect(x0, y0, 140*k, 89*k)
        for hx in (30, 110):  # m2, m1 measured from the rear end (x -140 → 0)
            hole(x0 + (140-hx)*k if False else x0 + (140 - hx)*k, y0 + 44.5*k, 3.25*k)
        for vx in (10, 130):
            s.append(f'<line x1="{x0 + (140-vx)*k}" y1="{y0}" x2="{x0 + (140-vx)*k}" y2="{y0+89*k}" stroke="{INK}" stroke-dasharray="4 3"/>')
        dim(x0, y0+89*k, x0+140*k, y0+89*k, '140')
        dim(x0, y0, x0, y0+89*k, '89', 10)
        dim(x0+30*k, y0+44.5*k, x0+110*k, y0+44.5*k, '80', 18)
        for i, t in enumerate(['Side to side: Ø6.5 at 30 and 110 from the rear end,', '44.5 from the top. M6 × 80 through frame, block, frame.',
                               'Top to bottom (dashed): Ø6.5 at 10 and 130 from', 'the rear end, centred. M6 × 110 hold the drawbar.', 'A 1 mm nylon washer each side fills the 40 mm gap.']):
            txt(x0, y0+89*k+38+i*15, t, 10)
        # drawbar
        L = bp_drawbar_len(m)
        x1, y1 = 60, 445
        txt(x1, y1-14, f'BP-DRAWBAR · 3/4 in EMT, cut {fmt(L)} · flatten 150 at the rear end, 60 at the front, in a vise', 10, 700)
        s.append(f'<rect x="{x1}" y="{y1}" width="{L*0.45:.0f}" height="12" fill="#ddd" stroke="{INK}"/>')
        rect(x1, y1-4, 150*0.45, 20, '#bbb'); rect(x1 + L*0.45 - 60*0.45, y1-4, 60*0.45, 20, '#bbb')
        for e in (10, 130): hole(x1 + e*0.45, y1+6, 3)
        for e in (15, 45): hole(x1 + L*0.45 - e*0.45, y1+6, 3)
        txt(x1, y1+38, 'Rear end: 2 × Ø6.5 at 10 and 130 from the end; end flush with the block rear (matches the block).', 10)
        txt(x1, y1+54, 'Front end: 2 × Ø6.5 at 15 and 45 from the end, to the hinge leaf.', 10)
        # lumbar plate
        x2, y2 = 560, 60; k2 = 1.0  # lumbar
        txt(x2, y2-10, 'BP-LUMBAR · 1/2 in ply 250 × 150', 10, 700)
        rect(x2, y2, 250*k2, 150*k2)
        for sx in (20, 230): s.append(f'<rect x="{x2+sx-4}" y="{y2+25}" width="8" height="100" fill="#fff" stroke="{INK}"/>')
        rect(x2+95, y2+60, 60, 30, '#ddd'); txt(x2+125, y2+80, 'hinge', 9, 400, 'middle')
        for hx in (105, 145): hole(x2+hx, y2+67, 2.5); hole(x2+hx, y2+83, 2.5)
        dim(x2, y2+150, x2+250, y2+150, '250'); dim(x2, y2, x2, y2+150, '150', 10)
        txt(x2, y2+190, 'Strap slots 8 × 100, 20 in from each side.', 10)
        txt(x2, y2+206, '3 in butt hinge centred, pin horizontal (side to side).', 10)
        txt(x2, y2+222, 'Hinge leaf: 4 × wood screws into the plate.', 10)
        txt(x2, y2+238, 'Other leaf: 2 × M6 × 40 to the drawbar front.', 10)
    else:
        k = 1.0
        txt(14, 22, 'BIKE MOUNT PARTS · all mm', 12, 700)
        x0, y0 = 60, 60
        txt(x0, y0-10, 'BK-BOARD · 1/2 in ply 420 × 320 · seen from above, front of bike to the right', 10, 700)
        rect(x0, y0, 420*k, 320*k)
        for ux in (200, 390):
            for uz in (100, 220):
                hole(x0+ux-12, y0+uz, 4); hole(x0+ux+12, y0+uz, 4)
        for ax in (30, 210):
            hole(x0+ax, y0+12, 3.25); hole(x0+ax, y0+320-12, 3.25)
        dim(x0, y0+320, x0+420, y0+320, '420'); dim(x0, y0, x0, y0+320, '320', 10)
        txt(x0, y0+360, 'U-bolt holes (pairs 24 apart) at 200 and 390 from the rear end, over the rack; shown for rails 120 apart, drill to suit yours.', 10)
        txt(x0, y0+376, 'Angle bolts: 4 × Ø6.5, 12 in from each long edge, at 30 and 210 from the rear end. Angles flush with the rear end.', 10)
        txt(x0, y0+392, 'The board rear end overhangs the rack by 170. Crank rod: 190 behind the rear axle, 700 above the floor.', 10)
        x1, y1 = 540, 60; k1 = 1.0
        txt(x1, y1-10, 'BK-ANGLE ×2 · alu 1 × 1 × 1/8 in, 300 long', 10, 700)
        rect(x1, y1, 300*k1*0.9, 25, '#ddd'); txt(x1, y1+38, 'vertical leg (frame side)', 9)
        for hx in (90, 270): hole(x1 + hx*0.9, y1+12.5, 3.25)
        rect(x1, y1+50, 300*0.9, 25, '#ddd'); txt(x1, y1+88, 'flange under the board', 9)
        for hx in (30, 210): hole(x1 + hx*0.9, y1+62.5, 3.25)
        for i, t in enumerate(['Vertical leg: Ø6.5 at 90 and 270 from the rear end,', '13 below the board = the frame holes m2, m1.', 'Flange: Ø6.5 at 30 and 210 to the board.', 'Outer face of the vertical leg flush with the board', 'edge, so the frames sit 320 apart on the outside.']):
            txt(x1, y1+118+i*16, t, 10)
    s.append('</svg>')
    return ''.join(s)

def stack_svg(m):
    st = m['stacks']; pins = ['O', 'B', 'M', 'J1', 'J2', 'J3', 'J4']
    maxg = max(sum(t for (n_, t, k) in st[p]['items']) for p in pins)
    W = 980; rowH = 54; Hh = 40 + rowH*len(pins) + 20
    sx = (W - 470) / maxg
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" font-family="IBM Plex Mono, monospace" font-size="11">', f'<rect width="{W}" height="{Hh}" fill="#fff"/>']
    s.append(f'<text x="10" y="18" font-weight="700">STACK AT EACH PIN · to scale, {fmt(sx,2)} px/mm · inner (centreline side) on the left</text>')
    for i, p in enumerate(pins):
        y = 40 + i*rowH; x = 120
        s.append(f'<text x="10" y="{y+20}" font-weight="700">{p}</text><text x="10" y="{y+34}" font-size="9">{PIN_NAMES[p]}</text>')
        s.append(f'<rect x="{x-4}" y="{y+15}" width="{sum(t for (n_,t,k) in st[p]["items"])*sx+8:.1f}" height="6" fill="#777"/>')
        for (n_, t, k) in st[p]['items']:
            wpx = t*sx
            if k.startswith('plate'):
                pid = k.split(':')[1]; fill = '#f6efe0' if (pid in ('frame','crank') or not m['sp']['foam']) else '#fff'; hh = 30
            elif k == 'spacer': fill = AMBER; hh = 14
            elif k == 'washer': fill = '#dfe9ff'; hh = 22
            else: fill = INK; hh = 18
            s.append(f'<rect x="{x:.1f}" y="{y+18-hh/2:.1f}" width="{max(0.8,wpx):.1f}" height="{hh}" fill="{fill}" stroke="{INK}" stroke-width="0.6"/>')
            if k.startswith('plate') and wpx > 18: s.append(f'<text x="{x+wpx/2:.1f}" y="{y+22:.1f}" font-size="9" text-anchor="middle">{k.split(":")[1]}</text>')
            x += wpx
        s.append(f'<text x="{x+6:.1f}" y="{y+22}" font-size="10">{fmt(st[p]["grip"],1)} · {html.escape((st[p]["fastener"] or "").split(",")[0])}</text>')
    s.append('</svg>')
    return ''.join(s)

# ---------------------------------------------------------------- tables
def bp_drawbar_len(m):
    d = m['d']; O = m['drive']['O']; hipX, hipY = d['b']['Lb'], d['HMhip']; topK = O[1] + 85 + 44.5
    return math.hypot(hipX - 80 + 130, topK - hipY) + 20

def cut_list(m):
    rows = []; sp = m['sp']; code = sp['code']
    for pid in PART_ORDER:
        p = m['parts'][pid]; xs = [q[0] for q in p['poly']]; ys = [q[1] for q in p['poly']]
        if pid in ('frame', 'crank'): mat, qty = '1/4 in ply', 4
        else: mat, qty = ('1 in EPS' if sp['foam'] else '1/4 in ply'), 2
        rows.append((f"{code}-{pid.upper()}", p['name'], mat, qty, f"{fmt(max(xs)-min(xs))} × {fmt(max(ys)-min(ys))}", len(p['holes'])))
    if sp['foam']:
        rows.append((f"{code}-CHEEK", 'Cheek plate Ø60', '1/4 in ply', cheek_count(m), 'Ø60', 1))
        for pid in LINKS:
            a_ = m['parts'][pid]
            L = dist(a_['pts'][a_['holes'][0][0]], a_['pts'][a_['holes'][1][0]]) - 76
            rows.append((f"{code}-SPINE-{pid.upper()}", f'Dowel spine, link {pid}', '1/4 in dowel', 2, f'{fmt(L)} long', 0))
    for a_ in armbox_parts(m):
        poly = outline(a_['cen'], a_['w']/2); xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
        rows.append((f"{code}-{a_['id'].upper()}", a_['name'], '1/4 in ply', 1 if a_['id'] == 'tension' else 2 if m['name'] == 'backpack' else 4, f"{fmt(max(xs)-min(xs))} × {fmt(max(ys)-min(ys))}", len(a_['holes'])))
    if m['name'] == 'backpack':
        rows += [(f'{code}-BLOCK', 'Saddle block (holes on the Mounts sheet)', '2×4 lumber (38 × 89)', 1, '140 long', 4),
                 (f'{code}-DRAWBAR', 'Drawbar, rear end flattened 150, front 60 (Mounts sheet)', '3/4 in EMT', 1, f'{fmt(bp_drawbar_len(m))} long', 4),
                 (f'{code}-LUMBAR', 'Lumbar plate (Mounts sheet)', '1/2 in ply', 1, '250 × 150', 4),
                 (f'{code}-SHAFT-S1', 'S1 shaft', '8 mm steel rod', 1, f'{m["drive"]["shafts"][1][1]} long', 0),
                 (f'{code}-SHAFT-R', 'R roller shaft', '8 mm steel rod', 1, '66 long', 0),
                 (f'{code}-ROD-O', 'Crank rod', 'M8 threaded rod', 1, f'{m["rodLen"]} long', 0),
                 (f'{code}-SPACERS', 'Spacer tubes (cut list per pin on the Pin stacks sheet)', '12 OD × 8.5 ID tube', 1, f'{fmt(spacer_total(m))} total', 0)]
    else:
        rows += [(f'{code}-BOARD', 'Rack board (Mounts sheet)', '1/2 in ply', 1, '420 × 320', 12),
                 (f'{code}-ANGLE', 'Rack angle (Mounts sheet)', 'alu angle 1 × 1 × 1/8 in', 2, '300 long', 4),
                 (f'{code}-SHAFT-R', 'R roller shaft', '8 mm steel rod', 1, '174 long', 0),
                 (f'{code}-SHAFT-S', 'S1 and S2 shafts', '8 mm steel rod', 2, '83 long', 0),
                 (f'{code}-STANDOFF', 'Box standoffs', 'tube 12 OD × 8.5 ID', 3, '47 long', 0),
                 (f'{code}-ROD-C', 'Crank rod', 'M8 threaded rod', 1, f'{m["rodLen"]} long', 0),
                 (f'{code}-SPACERS', 'Spacer tubes (per pin on the Pin stacks sheet)', '12 OD × 8.5 ID tube', 1, f'{fmt(spacer_total(m))} total', 0)]
    return rows

def spacer_total(m):
    legs = sum(t for s_ in m['stacks'].values() for (n_, t, k) in s_['items'] if k == 'spacer') * 2
    return legs + (14 if m['name'] == 'backpack' else 3*47) + 20  # drive spacers + 20 mm saw kerf allowance

def bush_count(m):
    n = 0; sp = m['sp']
    for pid in PART_ORDER:
        for (h, c, dia, note) in m['parts'][pid]['holes']:
            if 'bush' in note: n += 2 if (sp['foam'] and pid not in ('frame', 'crank')) else (2 if pid == 'frame' else 1)
    return n * 2

def nylon_count(m):
    return 2 * sum(1 for s_ in m['stacks'].values() for (n_, t, k) in s_['items'] if n_.startswith('nylon washer'))

def buy_list(m):
    sp = m['sp']; st = m['stacks']; name = m['name']
    bolts = {}
    for pin, s_ in st.items():
        if pin == 'O': continue
        k = s_['fastener'].split(',')[0].split(' (')[0]
        bolts[k] = bolts.get(k, 0) + 2
    nb = sum(bolts.values())
    rows = []
    if name == 'backpack':
        rows += [('EPS foam board 1 in, 2 × 4 ft', 2, 8.0), ('1/4 in birch ply, 2 × 4 ft', 2, 15.0), ('1/2 in ply offcut 250 × 150', 1, 3.0),
                 ('1/4 in hardwood dowel, 36 in', 4, 1.0), ('2×4 offcut, 140 mm', 1, 1.0), ('3/4 in EMT conduit, 10 ft', 1, 9.0)]
    else:
        rows += [('1/4 in birch ply, 2 × 4 ft', 1, 15.0), ('1/2 in ply 420 × 320', 1, 6.0), ('aluminium angle 1 × 1 × 1/8 in, 3 ft', 1, 12.0),
                 ('U-bolts to clamp the board to the rack (measure rack tubes)', 4, 1.5)]
    rows += [('wood glue (PVA, foam-safe)', 1, 5.0), ('spray adhesive (to stick the printed sheets to stock, foam-safe)', 1, 8.0),
             ('5-minute epoxy (captive nuts)', 1, 6.0), ('epoxy putty stick (locks the roller to its shaft)', 1, 6.0), ('thread locker, medium', 1, 6.0)]
    for k, v in sorted(bolts.items()): rows.append((k, v, 0.6))
    rows += [('M8 nylock nut', nb, 0.12), ('M8 thin nut DIN 439 (captive in the cranks)', 4, 0.15), ('roll pin 3 × 40 (crank to rod)', 2, 0.3), ('M8 fender washer 32 mm', 2*nb, 0.15), ('nylon washer 8 × 16 × 1', nylon_count(m) + 4, 0.08),
             ('flanged nylon bush 8 ID × 10 OD × 5, 1 mm flange', bush_count(m), 0.35), (f'tube 12 OD × 8.5 ID (aluminium or nylon), {fmt(spacer_total(m))} mm total', 1, 6.0),
             ('M8 threaded rod, 1 m', 1, 4.0), (('8 mm steel rod, 300 mm (S1 + R shafts)' if name == 'backpack' else '8 mm steel rod, 500 mm (R, S1, S2 shafts)'), 1, 6.0 if name == 'backpack' else 9.0), ('8 mm shaft collar with set screw', 4 if name == 'backpack' else 8, 0.8)]
    if name == 'backpack':
        rows += [('608-2RS bearing (frame O ×2, frame S1 ×2, arm S1, arm R)', 6, 0.9), ('GT2 20T toothed idler, 5 mm bore, 6 mm belt', 1, 3.0),
                 ('110 mm inline skate wheel with bearings (ground wheel)', 1, 8.0), ('55 mm aggressive inline wheel (roller, bearings removed)', 1, 5.0),
                 ('GT2 pulley 16T, 8 mm bore, 6 mm belt', 1, 4.0), ('GT2 pulley 40T, 8 mm bore, 6 mm belt', 1, 6.0), ('GT2 6 mm belt: closed loop 1650–1700 mm, or 2 m open belt spliced (see Steps)', 1, 8.0),
                 ('spur gear module 1, 20T, 8 mm bore, steel', 1, 6.0), ('spur gear module 1, 60T, 8 mm bore, steel', 1, 9.0),
                 ('M6 × 80 bolt + nylock (frame–block–frame)', 2, 0.5), ('M6 × 110 bolt + nylock (drawbar to block)', 2, 0.6), ('M6 × 40 bolt + nylock (drawbar to hinge)', 2, 0.4),
                 ('M8 × 70 bolt + nylock (wheel axle)', 1, 0.6), ('M6 × 30 bolt + nylock (lever pivot ×1, weight bar ×2)', 3, 0.4), ('M5 × 30 bolt + nylock (idler)', 1, 0.3),
                 ('3 in steel butt hinge (drawbar pitch pivot)', 1, 4.0), ('2 in ratchet straps (lumbar plate to backpack hip belt)', 2, 6.0),
                 ('extension spring ~20 N (tensioner) + screw eye', 1, 2.5), ('steel flat bar 50 × 6 mm, 420 long, ~1 kg (wheel down-force)', 1, 6.0), ('rubber pad 10 mm, 50 × 50 (feet)', 2, 1.0)]
    else:
        rows += [('608-2RS bearing (frame O ×2, box plates C R S1 S2 ×2)', 10, 0.9), ('52 mm skateboard wheel (roller, bearings removed)', 1, 5.0),
                 ('spur gear module 1, 20T + 60T, 8 mm bore, steel', 1, 15.0), ('GT2 pulley 20T 8 mm bore, 6 mm belt', 1, 3.0), ('GT2 pulley 60T 8 mm bore, 6 mm belt', 1, 8.0),
                 ('GT2 pulley 20T 8 mm bore, 10 mm belt', 1, 4.0), ('GT2 pulley 60T 8 mm bore, 10 mm belt', 1, 10.0),
                 ('GT2 6 mm closed belt, 200 mm loop', 1, 3.0), ('GT2 10 mm closed belt, 200 mm loop', 1, 4.0),
                 ('M6 × 30 bolt + nylock (frames to angles)', 4, 0.4), ('M6 × 40 bolt + nylock (angles to board)', 4, 0.4), ('M6 × 80 bolt + nylock (box standoffs)', 3, 0.5), ('extension spring ~20 N (roller down-force) + screw eye', 1, 3.5)]
    return rows

def steps(m):
    sp = m['sp']; name = m['name']; st = m['stacks']; d = m['d']; dr = m['drive']
    out = ['Print every part sheet at 100% (tiled PDF in the files). Measure the 100 mm bar. Reprint if it is off by more than 1 mm. Join tiles on the crosses.']
    out.append('Before gluing the crank pairs: cut a 13 mm across-flats hex right through one layer (red hex on the sheet): at M in the inner layer (faces the frame), at O in the outer layer. Epoxy an M8 thin nut (5 mm) in each, flush.')
    if name == 'backpack':
        out += [
          'Glue pairs of 1/4 in ply for frames (×2), cranks (×2) and the wheel arm (×1). Clamp flat overnight.',
          'Stick the printed sheets to the stock with spray adhesive. Cut foam with a snap blade in two passes or a hot wire. Cut ply with a jigsaw.',
          'Drill ply on a drill press: Ø10 for bushes, Ø22 for 608s (Forstner, flush with the inner face), Ø8.2 at the crank centres, Ø6.5 for M6, Ø5 for the screw eye.',
          'Cut 6.5 × 7 mm slots along links j, k, c, f (table saw or router, two passes). Glue the 1/4 in dowel in with PVA. Let dry.',
          f'Cut {cheek_count(m)} cheek discs Ø60 with Ø10 holes. Drill the foam Ø14 at each hole. Glue a cheek to each face, lined up on an M8 bolt.',
          'Press a flanged bush into every Ø10 hole from the outside face, flange out. Press 608s into the frames (O, S1) and the arm (S1, R).',
        ]
    else:
        out += [
          'Glue pairs of 1/4 in ply for frames (×2), cranks (×2) and drive-box plates (×2 pairs). Clamp flat overnight.',
          'Stick the printed sheets to the ply with spray adhesive. Cut with a jigsaw or bandsaw. Drill on a drill press: Ø10 bushes, Ø22 608s (Forstner), Ø8.2 crank centres, Ø6.5 for M6.',
          'Press flanged bushes into every Ø10 hole, flange out. Press 608s into the frames (O) and both box plates (C, R, S1, S2).',
        ]
    for pin in ['B', 'J1', 'J2', 'J3', 'J4']:
        s_ = st[pin]
        seq = ' / '.join(n_.split(':')[0] for (n_, t, k) in s_['items'] if k == 'spacer' or k.startswith('plate'))
        out.append(f'Pin {pin} ({PIN_NAMES[pin]}): {s_["fastener"]}. Head on the centre side. Inner to outer: {seq}. Tighten until it stops rattling, then back off 1/8 turn.')
    s_ = st['M']
    seq = ' / '.join(n_.split(':')[0] for (n_, t, k) in s_['items'] if k == 'spacer' or k.startswith('plate'))
    out.append(f'Pin M (crank pin): {s_["fastener"]}. Bolt goes in from the outside, through {seq}, into the captive nut. Check j and k swing freely.')
    out.append(f'Crank rod O: {st["O"]["fastener"]}. Order is on the Z map. Set the cranks 180° apart, then drill 3 mm across each crank through the rod, in the inner ply layer 2.75 from the glue line, and tap in a 3 × 40 roll pin.')
    out.append('File a small flat on every shaft where a pulley, spur or collar sits. Tighten each set screw onto its flat with thread locker.')
    if name == 'backpack':
        out += [
          'Fit the 60T spur on the crank rod and the 20T spur + 40T pulley on S1 (positions on the Z map). The gears should mesh with a paper-thin gap.',
          'Remove the bearings from the 55 mm roller. Slide it on the R shaft and pack the core with epoxy putty, centred. Let it cure.',
          f'Hang the arm on S1. Fit the 110 mm wheel on its M8 × 70 axle and the R shaft with roller and 16T pulley. The roller sits on top of the wheel. The belt path is {fmt(dr["belt"][0][5])} mm: use a 1650–1700 mm closed loop, or splice a 2 m open belt (overlap 40 mm teeth-in-teeth, glue with flexible CA, wrap with tape); a clamp joint will not pass the 16T pulley.',
          'Bolt the tensioner lever to the arm at tp (loose, nylock), pointing up the arm toward S1, the toothed idler at its end inside the belt loop. Hook the spring from the lever to the screw eye at sa so the idler pushes one belt span outward. Shim with washers so the idler lines up with the belt.',
          f'Bolt the saddle block between the frames (2 × M6 × 80 at m1, m2). Flatten both ends of the drawbar ({fmt(bp_drawbar_len(m))} mm). Bolt one end on top of the block (2 × M6 × 110), the other to the butt hinge on the lumbar plate.',
          'Strap the lumbar plate to the backpack hip belt with two ratchet straps. The hinge pin runs side to side so the rig can pitch.',
          'Drill the steel bar Ø6.5 at 20 and 390 from one end and bolt it along the arm at w1, w2 (left face). Its weight presses the wheel down about 1 kg.',
          'Glue a rubber pad under each foot point F.',
        ]
    else:
        out += [
          'Bolt the two angles under the board long edges, flush with the rear end and the edges (Mounts sheet). Bolt the board to the rack with 4 U-bolts so the board overhangs the rack by 170 at the back and the crank rod will sit 190 behind the rear axle.',
          'Bolt each leg frame to its angle with 2 × M6 × 30 at m1, m2: head on the inside (box side), nylock outside.',
          'Remove the bearings from the 52 mm roller. Slide it on the R shaft and pack the core with epoxy putty, centred. Let it cure.',
          'Assemble the drive box with the shaft order on the Z map: three M6 × 80 standoffs with 47 mm tubes hold the plates apart. Fit both 200 mm belts. If a belt is slack, the centres are off: re-drill S2. Hang the box on the crank rod.',
          'Hook the spring from the screw eye at hole sa (on the tail behind the hinge) straight up to the rack board. The tail lifts, the roller presses the tire with about 1 kg.',
        ]
    out += [
      'Turn the crank one full turn by hand. Nothing catches. Mark any pin that knocks.',
      ('Stand on the rig\'s right side and push it forward (to your right). The crank turns clockwise and each foot moves backward while it is down. If not, the gear stage is missing or doubled.' if name == 'backpack'
       else 'Bike on a stand, roller down. Stand on the right side and turn the rear wheel forward. The crank turns clockwise. Count 27 roller turns per crank turn.'),
      ('Hang the rump (2 kg) and walk 100 strides. Measure foot slop, sideways push at the foot (10 N), and link k bow. Compare with the Checks sheet.' if name == 'backpack'
       else 'Ride 1 km at walking pace, then 16 km/h. Check bolts, belt tension and roller grip.'),
    ]
    return out

# ---------------------------------------------------------------- write files
files = {}
for name, m in M.items():
    code = m['sp']['code']
    for pid in PART_ORDER:
        svg, _ = part_svg(m, pid)
        p = m['parts'][pid]
        files[f'{name}/parts/{code}-{pid.upper()}.svg'] = svg
        extra = []
        if m['sp']['foam'] and pid not in ('frame', 'crank'):
            extra = [('CHEEK-OUTLINE', c, m['sp']['cheekD']/2) for (h, c, dia, note) in p['holes'] if h in PIN_NAMES]
        if p['foot']:
            F = p['pts'][p['foot']]; extra = list(extra) + [('MARK-FOOT', F, 1.5)]
        hexes = []
        if pid == 'crank':
            for h_ in ('O', 'M'):
                c_ = p['pts'][h_]; r_ = 13/math.sqrt(3)
                hexes += [('LINE', 'HEX-' + ('OUTER' if h_ == 'O' else 'INNER') + '-LAYER', (c_[0]+r_*math.cos(k*math.pi/3), c_[1]+r_*math.sin(k*math.pi/3)), (c_[0]+r_*math.cos((k+1)*math.pi/3), c_[1]+r_*math.sin((k+1)*math.pi/3))) for k in range(6)]
        dx_ = part_dxf(p['poly'], p['holes'], extra)
        if hexes: dx_ = dx_.replace('0\nENDSEC\n0\nEOF', dxf(hexes).split('ENTITIES\n', 1)[1])
        files[f'{name}/dxf/{code}-{pid.upper()}.dxf'] = dx_
    if m['sp']['foam']:
        svg, _ = cheek_svg(m); files[f'{name}/parts/{code}-CHEEK.svg'] = svg
        files[f'{name}/dxf/{code}-CHEEK.dxf'] = part_dxf(outline([(0, 0)], 30), [('c', (0, 0), 10.0, '')])
    for a in armbox_parts(m):
        svg, _ = armbox_svg(m, a); files[f'{name}/parts/{code}-{a["id"].upper()}.svg'] = svg
        dx_ = part_dxf(outline(a['cen'], a['w']/2), a['holes'])
        if a.get('slot'):
            sl = outline(a['slot'], 4.1, 24)
            dx_ = dx_.replace('0\nENDSEC\n0\nEOF', ''.join(f'0\nLINE\n8\nCUT\n10\n{sl[i][0]:.3f}\n20\n{sl[i][1]:.3f}\n30\n0\n11\n{sl[(i+1)%len(sl)][0]:.3f}\n21\n{sl[(i+1)%len(sl)][1]:.3f}\n31\n0\n' for i in range(len(sl))) + '0\nENDSEC\n0\nEOF')
        files[f'{name}/dxf/{code}-{a["id"].upper()}.dxf'] = dx_
    files[f'{name}/views/{code}-PLATE.svg'] = plate_svg(m)
    files[f'{name}/views/{code}-FRONT.svg'] = front_svg(m)
    files[f'{name}/views/{code}-DRIVE.svg'] = drive_svg(m)
    files[f'{name}/views/{code}-STACKS.svg'] = stack_svg(m)
    files[f'{name}/views/{code}-MOUNTS.svg'] = mounts_svg(m)

summary = {}
for name, m in M.items():
    d = m['d']
    summary[name] = dict(
        sigma=m['sg'], axle=d['Hc'] if name == 'backpack' else d['b']['mountY'], rpm=d['rpm'], worst=d['worst'], legKg=d['legKg'], totalKg=d['totalKg'],
        spread=d['spread'], wobble=d['wobble'], ledger=d['ledger'], links=d['links'],
        pins={k: dict(use=v['use'], peak=v['peak'], swing=v['swing'], knocks=v['knocks']) for k, v in d['pins'].items()},
        stacks={k: dict(items=[(n_, round(t, 1)) for (n_, t, kk) in v['items']], grip=round(v['grip'], 1), fastener=v['fastener']) for k, v in m['stacks'].items()},
        layers=dict(order=d['layerOf'], thick=m['layerT'], zInner=m['zL']), footZ=m['zmid']('lo'), humanZ=.035*H,
        drive={k: (v if not isinstance(v, tuple) else list(v)) for k, v in m['drive'].items() if k not in ('arm',)},
        cut=cut_list(m), buy=buy_list(m), steps=steps(m))
files['design-data.json'] = json.dumps(summary, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o))

for path, txt in files.items():
    full = os.path.join(OUT, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w').write(txt)
with zipfile.ZipFile('../centaur-rig-design-files.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for path in files: z.write(os.path.join(OUT, path), 'centaur-rig/' + path)
json.dump({n: {'files': [p for p in files if p.startswith(n)]} for n in M}, open('../files/index.json', 'w'))
print('wrote', len(files), 'files')
for name, m in M.items():
    print(name, 'rod', m['rodLen'], 'footZ', round(m['zmid']('lo'), 1), 'layers', [round(t, 1) for t in m['layerT']], 'z', [round(z, 1) for z in m['zL']])
    for pin, s_ in m['stacks'].items(): print('  ', pin, round(s_['grip'], 1), s_['fastener'])
    print('   drive', {k: v for k, v in m['drive'].items() if k in ('S1', 'S2', 'R', 'C', 'W', 'clear', 'perTurn')})
