import json,sys
from playwright.sync_api import sync_playwright
def run(js):
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={'width':1300,'height':820})
        pg.goto('file://' + __import__('os').path.abspath('eval.html') + ''); pg.wait_for_timeout(600)
        r=pg.evaluate(js); b.close(); return r
if __name__=='__main__':
    print(json.dumps(run(open(sys.argv[1]).read()),indent=1))
