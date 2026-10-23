import json, html, math
import gen
from gen import M, PART_ORDER, PIN_NAMES, fmt, cut_list, buy_list, steps, armbox_parts, files, H

E = html.escape

def tbl(head, rows, cls=''):
    h = '<table class="%s"><tr>%s</tr>' % (cls, ''.join(f'<th>{E(str(x))}</th>' for x in head))
    for r in rows:
        h += '<tr>' + ''.join(f'<td>{x if isinstance(x, str) and x.startswith("<") else E(str(x))}</td>' for x in r) + '</tr>'
    return h + '</table>'

def strip_xml(svg):
    return svg

def checks_html(m):
    d = m['d']; name = m['name']; sp = m['sp']
    footZ = m['zmid']('lo')
    ledger = []
    for a, b, c in d['ledger']:
        if a == 'In line with your feet':
            off = footZ - .035*H; b = f'{"+" if off >= 0 else ""}{fmt(off)} mm'; c = 'ok' if abs(off) < 25 else 'warn' if abs(off) < 60 else 'bad'
        ledger.append((a, b, c))
    led = ''.join(f'<div class="led"><i class="{c}"></i><span>{E(a)}</span><b>{E(b)}</b></div>' for a, b, c in ledger)
    links = [(k, fmt(v['L']), fmt(v['squeeze']) + ' N', fmt(v['Pcr']) + ' N', f'<span class="{ "bad" if v["buck"]>=1 else "warn" if v["buck"]>=.5 else "ok"}">{fmt(v["buck"],2)}×</span>') for k, v in d['links'].items()]
    pins = [(k, PIN_NAMES[k], fmt(v['peak']) + ' N', fmt(v['swing']) + '°' if v['swing'] < 300 else 'full turns', f'<span class="{ "bad" if v["use"]>=1 else "warn" if v["use"]>=.5 else "ok"}">{fmt(v["use"],2)}×</span>', v['knocks']) for k, v in d['pins'].items()]
    limits = []
    if name == 'backpack':
        limits = [
          'Each hind foot is down 44% of a crank turn. A horse walk keeps each foot down about 60%. Searching the linkage lengths reached 47% at best without the foot sliding, so the original Jansen lengths stay.',
          f'The rump bobs with your hip and the feet slide up to {fmt(float(d["ledger"][1][1].split()[0]))} mm per step against your moving hip.',
          'The ground wheel sets the rig stride by distance. Your steps and the hind steps drift in and out of phase over about 30 strides.',
          'The ground wheel sits under the belly, 330 mm ahead of the crank, between your heels and the hind toes. It shows from the side unless the rump skirt covers it.',
          'The wheel arm leads (wheel ahead of its pivot). On a bump the wheel can jam. Walk on flat floors first.',
          f'Hind feet sit {fmt(footZ - .035*H)} mm outside your foot line (measured {fmt(footZ)} vs {fmt(.035*H)} from centre).',
        ]
    else:
        limits = [
          'The legs never touch the road. They read as legs from the swing and timing only.',
          'Rack struts are taken at ±67 mm from the tire centre and 790 mm high. Measure your rack. The drive box must sit outside the strut.',
          f'Worst clearance from a drive pulley to the tire or the rack is {fmt(m["drive"]["clear"])} mm.',
          'The last belt carries about 160 N at peak crank torque (3.1 N·m on a 60T pulley). Use a 10 mm wide GT2 belt there.',
          'Road shock is not in the load model. Loads are walking-speed swing plus weight × 1.3.',
        ]
    return (f'<h3>Pass list <span>computed by the instrument, not yet measured</span></h3>{led}'
            f'<h3>Links <span>squeeze vs buckling</span></h3>' + tbl(['Link', 'Length', 'Squeeze', 'Buckles at', 'Use'], links) +
            f'<h3>Pins <span>peak load and swing</span></h3>' + tbl(['Pin', '', 'Peak', 'Swing', 'Use', 'Knocks/turn'], pins) +
            f'<h3>What still fails or is unknown</h3><ol class="steps">' + ''.join(f'<li>{E(x)}</li>' for x in limits) + '</ol>'
            f'<h3>Measure on the first leg</h3><ol class="steps"><li>Slop at J2 with a dial or feeler gauge, new and after 100 turns.</li><li>Sideways foot travel under a 10 N push. Computed ±{fmt(d["wobble"])} mm.</li><li>Link k bow under load with a straightedge.</li><li>Crank angle of every knock you hear (mark the crank, count frames 1–16).</li><li>Film it side-on at hip height against a 100 mm grid and compare with the 16-frame sheet.</li></ol>')

def footfalls(m):
    if m['name'] != 'backpack': return ''
    fr = m['d']['frames']; d = m['d']; hipY = d['HMhip']
    feet = {'near hind': [f['legs'][0]['down'] for f in fr], 'far hind': [f['legs'][1]['down'] for f in fr],
            'your near foot': [hipY + gen.human_leg(f['c'])[1][1] < 60 for f in fr], 'your far foot': [hipY + gen.human_leg(f['c'] + .5)[1][1] < 60 for f in fr]}
    ev = []
    for k, v in feet.items():
        for q in range(16):
            if v[q] and not v[q-1]: ev.append((q+1, k))
    ev.sort()
    return ' → '.join(f'{k} lands (frame {q})' for q, k in ev)

def build_sheets(m):
    name = m['name']; sp = m['sp']; code = sp['code']; d = m['d']; dr = m['drive']
    S = []
    # overview
    summary = [('Leg scale', f'{fmt(m["sg"],2)} mm per Jansen unit'),
               ('Crank axle height', f'{fmt(d["Hc"] if name=="backpack" else d["b"]["mountY"])} mm'),
               ('Rig stride (one crank turn)', f'{fmt(d["A"]["advance"]*m["sg"])} mm' if name == 'backpack' else f'{fmt(dr["perTurn"])} mm of road'),
               ('Crank speed', f'{fmt(d["rpm"])} rpm' + (' at your walk' if name == 'backpack' else ' at 16 km/h')),
               ('Leg weight, each', f'{fmt(d["legKg"],2)} kg'), ('Rig weight', f'{fmt(d["totalKg"],1)} kg'),
               ('Leg spacing (gap between frames)', f'{fmt(sp["gap"])} mm'), ('Material', sp['stockName'])]
    cost = sum(q*p for (_, q, p) in buy_list(m))
    summary.append(('Parts cost, rough US', f'${fmt(cost)}'))
    order = footfalls(m)
    S.append(dict(id='plate', title='16 exposures', svg=files[f'{name}/views/{code}-PLATE.svg'],
                  panel=('<p class="lead">One crank turn in 16 frames, after Muybridge. Under each foot that is down: teal = near hind, teal outline = far hind, black = your near foot, grey = your far foot.</p>' if name == 'backpack' else '<p class="lead">One crank turn in 16 frames. The legs swing 149 mm above the road; they never land.</p>') +
                        (f'<p class="lead"><b>Footfall order:</b> {E(order)}</p>' if order else '') + tbl(['', ''], summary, 'kv')))
    # front section
    rows = []
    for L in range(m['nL']):
        ps = [p for p in PART_ORDER if m['parts'][p]['layer'] == L]
        rows.append((L, fmt(m['layerT'][L], 1), f'{fmt(m["zL"][L],1)} – {fmt(m["zL"][L]+m["layerT"][L],1)}', ', '.join(ps)))
    S.append(dict(id='front', title='Z map', svg=files[f'{name}/views/{code}-FRONT.svg'],
                  panel='<p class="lead">Every part and drive item at its distance from the centreline. The left leg mirrors the right. A 1 mm nylon washer sits between layers.</p>' + tbl(['Layer', 'Thick', 'z from centre', 'Parts'], rows) +
                  ''.join(f'<h3>{E(sh[0])}</h3>' + tbl(['#', 'Item', 'z mm'], [(i+1, a, r) for i, (a, r) in enumerate(sh[2])]) for sh in dr['shafts'])))
    # drive
    if name == 'backpack':
        rows = [('Ground wheel W', '110 mm inline skate wheel', f'({fmt(dr["W"][0])}, {fmt(dr["W"][1])})'),
                ('Roller R', '55 mm inline wheel on W top', f'({fmt(dr["R"][0])}, {fmt(dr["R"][1])})'),
                ('Shaft S1', '608s in both frames + arm top', f'({fmt(dr["S1"][0])}, {fmt(dr["S1"][1])})'),
                ('Crank O', 'M8 rod, 608s in frames', f'({fmt(dr["O"][0])}, {fmt(dr["O"][1])})')]
        stages = [('1 friction', 'W → R', 'reverses', '—'), ('2 belt', 'R 16T → S1 40T', f'×2.5, C {fmt(dr["belt"][0][4])}, loop {fmt(dr["belt"][0][5])}', 'GT2 6 mm'),
                  ('3 spur', 'S1 20T → O 60T', '×3, C 40.0, reverses', 'module 1 steel')]
    else:
        rows = [(k, v, f'({fmt(dr[k][0])}, {fmt(dr[k][1])})') for k, v in (('R', '52 mm roller on tire top'), ('S1', '608s in both box plates'), ('S2', '608s in both box plates'), ('C', 'crank rod; box hinges here'))]
        stages = [('1 friction', 'tire → R', 'reverses', '—'), ('2 spur', 'R 20T → S1 60T', '×3, C 40.0, reverses', 'module 1 steel'),
                  ('3 belt', 'S1 20T → S2 60T', f'×3, C {fmt(dr["belt"][0][4],1)}', 'GT2 6 mm, 200 loop'), ('4 belt', 'S2 20T → C 60T', f'×3, C {fmt(dr["belt"][1][4],1)}', 'GT2 10 mm, 200 loop')]
    S.append(dict(id='drive', title='Drive', svg=files[f'{name}/views/{code}-DRIVE.svg'],
                  panel=tbl(['Shaft', 'What', 'x, y mm'], rows) + tbl(['Stage', 'From → to', 'Ratio', 'Part'], stages) +
                  '<p class="note">Test: stand on the rig\'s right side while it moves to your right. The crank turns clockwise, the same way as the wheels.</p>' +
                  ''.join(f'<h3>{E(sh[0])} <span>{E(str(sh[1]))}{" mm" if str(sh[1]).isdigit() else ""}</span></h3>' + tbl(['#', 'Item', 'z mm'], [(i+1, a, r) for i, (a, r) in enumerate(sh[2])]) for sh in dr['shafts'])))
    # stacks
    st = m['stacks']; panel = ''
    for pin in ['O', 'B', 'M', 'J1', 'J2', 'J3', 'J4']:
        s_ = st[pin]
        panel += f'<h3>{pin} {PIN_NAMES[pin]} <span>clamped length {fmt(s_["grip"],1)} mm</span></h3><div class="stack">' + ''.join(f'<span>{i+1}</span><span>{E(n_)}</span><span class="t">{fmt(t,1) if t else ""}</span>' for i, (n_, t, k) in enumerate(s_['items'])) + f'</div><p class="fast">{E(s_["fastener"])}</p>'
    S.append(dict(id='stacks', title='Pin stacks', svg=files[f'{name}/views/{code}-STACKS.svg'], panel=panel))
    # parts
    for pid in PART_ORDER:
        p = m['parts'][pid]
        rows = [(h, f'Ø{fmt(dia,1)}', note) for (h, c, dia, note) in p['holes']]
        mat = '1/4 in ply, 2 layers glued (11.0)' if pid in ('frame', 'crank') else (sp['stockName'] + (', 1/4 in dowel spine' if pid in gen.LINKS else '')) if sp['foam'] else '1/4 in ply (5.5)'
        qty = '4 layers (2 per leg, glued in pairs)' if pid in ('frame', 'crank') else '2 (one per leg)'
        S.append(dict(id=f'p-{pid}', title=p['name'], part=True, svg=files[f'{name}/parts/{code}-{pid.upper()}.svg'],
                      panel=tbl(['', ''], [('Sheet', f'{code}-{pid.upper()}'), ('Material', mat), ('Cut', qty), ('Width', f'{fmt(p["w"])} mm'), ('Layer', p['layer'])], 'kv') + tbl(['Hole', 'Size', 'Fitting'], rows)))
    if sp['foam']:
        S.append(dict(id='p-cheek', title='Cheek plate', part=True, svg=files[f'{name}/parts/{code}-CHEEK.svg'],
                      panel=f'<p class="lead">Ø60 disc of 1/4 in ply, Ø10 hole. Glue one to each face of the foam at every hole: {gen.cheek_count(m)} discs. The bush presses into the cheek, so the bolt bears on ply, not foam.</p>'))
    for a in armbox_parts(m):
        rows_ = [(h, f'Ø{fmt(dia,1)}', note) for (h, c, dia, note) in a['holes']]
        S.append(dict(id=f'p-{a["id"]}', title=a['name'], part=True, svg=files[f'{name}/parts/{code}-{a["id"].upper()}.svg'],
                      panel=tbl(['', ''], [('Sheet', f'{code}-{a["id"].upper()}'), ('Material', '1/4 in ply'), ('Cut', a['qty']), ('Width', f'{a["w"]} mm')], 'kv') + tbl(['Hole', 'Size', 'Fitting'], rows_)))
    S.append(dict(id='mounts', title='Mounts', svg=files[f'{name}/views/{code}-MOUNTS.svg'],
                  panel=('<p class="lead">Saddle block between the frames, drawbar from the block to a butt hinge on the lumbar plate, lumbar plate strapped to the backpack hip belt. The hinge lets the rig pitch with the ground.</p>' if name == 'backpack'
                         else '<p class="lead">Rack board on the rack with 4 U-bolts. One aluminium angle under each long edge. Each leg frame bolts to the outside of its angle at m1, m2.</p>')))
    # cut list, buy, steps, checks
    S.append(dict(id='cut', title='Cut list', svg=files[f'{name}/views/{code}-STACKS.svg'],
                  panel=tbl(['Sheet', 'Part', 'Stock', 'Qty', 'Size mm', 'Holes'], cut_list(m))))
    br = buy_list(m)
    S.append(dict(id='buy', title='Buy', svg=files[f'{name}/views/{code}-DRIVE.svg'],
                  panel=tbl(['Item', 'Qty', '$'], [(a, q, fmt(q*p)) for a, q, p in br] + [('<b>Total</b>', '', f'<b>{fmt(sum(q*p for _, q, p in br))}</b>')])))
    S.append(dict(id='steps', title='Steps', svg=files[f'{name}/views/{code}-STACKS.svg'],
                  panel='<ol class="steps">' + ''.join(f'<li>{E(x)}</li>' for x in steps(m)) + '</ol>' + ('<p class="note">No solvent glue, solvent spray paint or PVC cement on EPS. Use foam-safe spray adhesive.</p>' if sp['foam'] else '')))
    S.append(dict(id='checks', title='Checks', svg=files[f'{name}/views/{code}-PLATE.svg'], panel=checks_html(m)))
    return S

SHEETS = {n: build_sheets(m) for n, m in M.items()}
FILELIST = sorted(p for p in files)

page = open('template.html').read()
payload = {n: [dict(id=s['id'], title=s['title'], part=s.get('part', False), svg=s['svg'], panel=s['panel']) for s in SHEETS[n]] for n in SHEETS}
page = page.replace('/*DATA*/null', json.dumps(payload)).replace('/*FILES*/null', json.dumps(FILELIST))
open('../design-set.html', 'w').write(page)
print('html', len(page)//1024, 'KB', {n: len(v) for n, v in SHEETS.items()})
