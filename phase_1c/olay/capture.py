"""Playwright capture of the staged build (LEARNINGS rule 16).

Screenshots are a positional/layout sanity check only — the PPTX XML stays
the authority for values. Captures desktop and mobile from the real output
location so relative asset paths are exercised as shipped.
"""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
SHOT = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/shots")

async def main(which):
    SHOT.mkdir(parents=True, exist_ok=True)
    targets = {"desktop": (1600, 900), "mobile": (390, 844)}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for label, (w, h) in targets.items():
            if which and label != which: continue
            pg = await b.new_page(viewport={"width": w, "height": h},
                                  device_scale_factor=1)
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            failed = []
            pg.on("requestfailed", lambda r: failed.append(r.url.split("/")[-1]))
            await pg.goto(f"file://{OUT/'index.html'}", wait_until="load")
            await pg.wait_for_timeout(2500)
            # #deck is a 100vh scroll container. Element screenshots of sections
            # taller than the viewport come back part-black because Playwright
            # cannot scroll inside it — expand it just for capture.
            await pg.add_style_tag(content=
                "#deck{height:auto!important;overflow:visible!important;"
                "scroll-snap-type:none!important}")
            await pg.wait_for_timeout(400)
            for n in range(1, 35):
                await pg.evaluate(f"document.getElementById('s{n}').scrollIntoView()")
                await pg.wait_for_timeout(260)
                el = await pg.query_selector(f"#s{n}")
                await el.screenshot(path=str(SHOT / f"{label}_{n:02d}.png"))
            if label == "mobile":
                audit = await pg.evaluate("""() => {
                  const short=[], ov=[];
                  for (let n=1;n<=34;n++){
                    const s=document.getElementById('s'+n);
                    const h=Math.round(s.getBoundingClientRect().height);
                    if (h < window.innerHeight-2) short.push(n+':'+h+'px');
                    const vis=[...s.querySelectorAll('.sh')]
                      .filter(e=>getComputedStyle(e).display!=='none'
                                 && !e.classList.contains('backdrop'))
                      .map(e=>({c:e.className.replace('sh ',''),r:e.getBoundingClientRect()}));
                    for(let i=0;i<vis.length;i++) for(let j=i+1;j<vis.length;j++){
                      const a=vis[i].r,b=vis[j].r;
                      if (Math.min(a.right,b.right)-Math.max(a.left,b.left)>2 &&
                          Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)
                        ov.push(n+':'+vis[i].c+'/'+vis[j].c);
                    }
                  }
                  // A horizontally-scrolling slide must have ground under ALL
                  // of its scroll width, not just the first viewport: percentage
                  // widths on absolute children resolve against the 390px
                  // padding box, which silently leaves later tiles on bare page.
                  const ground=[];
                  document.querySelectorAll('.slide[data-layout=strip]').forEach(s=>{
                    const c=s.querySelector('.canvas');
                    const cl=c.getBoundingClientRect().left, sl=c.scrollLeft;
                    const p=[...c.querySelectorAll('.sh.rect.backdrop')].map(e=>{
                      const r=e.getBoundingClientRect();
                      return [r.left-cl+sl, r.right-cl+sl];}).sort((a,b)=>a[0]-b[0]);
                    if(!p.length){ ground.push(s.id+':no-ground'); return; }
                    if(Math.abs(p[0][0])>1)
                      ground.push(s.id+':starts@'+Math.round(p[0][0]));
                    if(Math.abs(p[p.length-1][1]-c.scrollWidth)>1)
                      ground.push(s.id+':ends@'+Math.round(p[p.length-1][1])+'/'+c.scrollWidth);
                    for(let i=1;i<p.length;i++)
                      if(Math.abs(p[i][0]-p[i-1][1])>1)
                        ground.push(s.id+':seam '+Math.round(p[i-1][1])+'->'+Math.round(p[i][0]));
                  });
                  return {short, ov, ground, scrollW: document.documentElement.scrollWidth};
                }""")
                # A slide shorter than the viewport lets the NEXT slide share the
                # screen, which reads as two slides colliding. Overlapping shapes
                # in a flow reflow are always a bug.
                assert not audit["short"], f"sections shorter than viewport: {audit['short']}"
                assert not audit["ov"], f"overlapping shapes: {audit['ov']}"
                assert audit["scrollW"] <= w, f"page scrolls horizontally: {audit['scrollW']}"
                assert not audit["ground"], f"strip ground gaps: {audit['ground']}"
                print(f"  layout audit: no short sections, no overlaps, "
                      f"strip ground continuous, scrollWidth={audit['scrollW']}")
            print(f"{label}: 34 shots  console_errors={len(errs)} failed_requests={len(set(failed))}")
            if errs: print("   ", errs[:4])
            if failed: print("   missing:", sorted(set(failed))[:6])
            await pg.close()
        await b.close()

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
