import sys
from playwright.sync_api import sync_playwright
paths=sys.argv[1:]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1100,'height':900})
    for f in paths:
        svg=open(f).read()
        # scale mm svgs to fit
        pg.set_content(f'<html><body style="margin:0;background:#ccc"><div style="width:1100px">{svg}</div><style>svg{{width:1080px!important;height:auto!important;display:block;background:#fff}}</style></body></html>')
        pg.wait_for_timeout(200)
        out='snap_'+f.replace('/','_').replace('.svg','.png')
        pg.locator('svg').first.screenshot(path=out); print(out)
    b.close()
