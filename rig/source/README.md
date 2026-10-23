# Rig design set: source

These scripts rebuild everything in `rig/files/`, `rig/design-set.html` and `rig/centaur-rig-design-files.zip` from the leg engine.

Requirements: Python 3, Playwright with Chromium, Pillow (only for thumbnails).

Run from this folder, in this order:

```
python3 ev.py extract.js > /dev/null   # optional: runs extract.js in eval.html (the engine), prints the result
python3 -c "import json,ev; json.dump(ev.run(open('extract.js').read()), open('builds.json','w'))"
python3 gen.py          # parts, DXF, views, stacks, cut/buy/steps -> ../files/
python3 build_html.py   # ../design-set.html (imports gen, so it regenerates ../files too)
python3 tiles.py        # tiled Letter PDFs -> ../files/*/ and the zip, run last
```

| File | What it does |
|---|---|
| `eval.html` | The Centaur Rig engine with a hook (`window.__t`) so scripts can call it. |
| `extract.js` | Defines the two builds and exports linkage, loads, layers, stacks, flats and 16 poses. |
| `ev.py` | Runs a JS function inside `eval.html` with Playwright and returns JSON. |
| `builds.json` | The exported engine data used by `gen.py`. |
| `gen.py` | The generator: stacks, shaft tables, part SVG/DXF, plate, Z map, drive, mounts, cut list, buy list, steps. |
| `build_html.py`, `template.html` | Build the design-set page. |
| `tiles.py` | Tiled 1:1 Letter PDFs and the zip. |
| `duty.js` | The ground-time inquiry (search over link lengths). |
| `grid.js` | The stock × joint comparison for both modes. |
| `torque.js` | Peak crank torque for belt sizing. |
| `sweep.py` | Checks bolt ends against neighbouring layers over a full turn. |
| `snap.py`, `shotds.py` | Render SVGs and the page to PNG for inspection. |
