import os, re, math, glob, zipfile
from playwright.sync_api import sync_playwright
PW, PH, MG, OV = 215.9, 279.4, 10.0, 10.0
TW, TH = PW - 2*MG, PH - 2*MG - 8
def size(svg):
    m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', svg); return float(m.group(1)), float(m.group(2))
def build(name, code):
    parts = sorted(glob.glob(f'../files/{name}/parts/*.svg'))
    pages = []
    for f in parts:
        svg = open(f).read(); W, H = size(svg); tag = os.path.basename(f)[:-4]
        nx = max(1, math.ceil((W - OV) / (TW - OV))); ny = max(1, math.ceil((H - OV) / (TH - OV)))
        cross = ''.join(f'<path d="M {x-4} {y} h 8 M {x} {y-4} v 8" stroke="#e11d1d" stroke-width="0.25"/>' for x in range(0, int(W)+1, 50) for y in range(0, int(H)+1, 50))
        over = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" style="position:absolute;left:0;top:0">{cross}</svg>'
        mp = re.search(r'<path d="M ([^"]+?) Z"', svg)
        poly = [tuple(map(float, q.strip().split())) for q in mp.group(1).split(' L ')] if mp else []
        def inside(x, y):
            ins = False
            for i in range(len(poly)):
                (x1, y1), (x2, y2) = poly[i], poly[i-1]
                if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1) + x1: ins = not ins
            return ins
        def used(ox, oy):
            if not poly: return True
            if any(ox <= x <= ox+TW and oy <= y <= oy+TH for x, y in poly): return True
            return any(inside(ox + fx*TW, oy + fy*TH) for fx in (0, .25, .5, .75, 1) for fy in (0, .25, .5, .75, 1)) or (oy + TH > H - 34 and ox < 160)
        for r in range(ny):
            for c in range(nx):
                ox, oy = c*(TW-OV), r*(TH-OV)
                if not used(ox, oy): continue
                pages.append(f'<div class="pg"><div class="lab">{tag} · tile row {r+1}/{ny}, col {c+1}/{nx} · overlap 10 mm, match red crosses · 100% scale</div>'
                             f'<div class="win"><div style="position:absolute;left:{-ox}mm;top:{-oy}mm;width:{W}mm;height:{H}mm">{svg.replace("<svg ", "<svg style=\"position:absolute;left:0;top:0\" ", 1)}{over}</div></div></div>')
    html = ('<html><head><style>@page{size:215.9mm 279.4mm;margin:0} body{margin:0;font-family:monospace}'
            f'.pg{{width:{PW}mm;height:{PH}mm;position:relative;page-break-after:always;overflow:hidden}}'
            f'.lab{{position:absolute;left:{MG}mm;top:4mm;font-size:8pt}} .win{{position:absolute;left:{MG}mm;top:{MG+4}mm;width:{TW}mm;height:{TH}mm;overflow:hidden;outline:0.2mm solid #999}}'
            '</style></head><body>' + ''.join(pages) + '</body></html>')
    open(f'tiles_{name}.html', 'w').write(html)
    return len(pages)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    for name, code in (('backpack', 'BP'), ('bike', 'BK')):
        n = build(name, code)
        pg.goto('file://' + os.path.abspath(f'tiles_{name}.html')); pg.wait_for_timeout(500)
        pg.pdf(path=f'../files/{name}/{code}-parts-tiled-letter.pdf', width='8.5in', height='11in', print_background=True, margin={'top':'0','bottom':'0','left':'0','right':'0'})
        print(name, n, 'pages')
    b.close()
with zipfile.ZipFile('../centaur-rig-design-files.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, fs in os.walk('../files'):
        for f in fs: z.write(os.path.join(root, f), 'centaur-rig/' + os.path.relpath(os.path.join(root, f), '../files'))
    z.write('../design-set.html', 'centaur-rig/design-set.html')
print(os.path.getsize('../centaur-rig-design-files.zip')//1024, 'KB')
