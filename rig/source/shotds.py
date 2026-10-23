from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h,tag in [(390,844,'m'),(1300,820,'d')]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('file://' + __import__('os').path.abspath('../design-set.html') + ''); pg.wait_for_timeout(600)
        pg.screenshot(path=f'ds_{tag}_plate.png')
        for sid in ['p-lo','stacks','checks']:
            pg.evaluate(f"location.hash='';"); 
            pg.locator('#list button', has_text={'p-lo':'Foot triangle','stacks':'Pin stacks','checks':'Checks'}[sid]).first.click(); pg.wait_for_timeout(300); pg.screenshot(path=f'ds_{tag}_{sid}.png')
        pg.click('[data-build=bike]'); pg.locator('#list button', has_text='Drive').first.click(); pg.wait_for_timeout(300); pg.screenshot(path=f'ds_{tag}_bikedrive.png')
        print(tag, errs, pg.evaluate('document.documentElement.scrollWidth'))
    b.close()
