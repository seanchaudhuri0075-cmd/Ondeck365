"""Pixel parity: embedded file vs folder build, at both target widths.

Videos are paused and seeked to t=0 in BOTH builds so the comparison is
deterministic — otherwise decode timing, not layout, dominates the diff.
"""
import asyncio, sys
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.async_api import async_playwright

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
SHOT = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/parity")

PIN = """async () => {
  const vs=[...document.querySelectorAll('video')];
  await Promise.all(vs.map(v=>new Promise(res=>{
    v.pause(); v.loop=false; v.muted=true;
    const done=()=>res();
    if (v.readyState>=2) { try{v.currentTime=0;}catch(e){} setTimeout(done,60); }
    else { v.addEventListener('loadeddata',()=>{try{v.currentTime=0;}catch(e){} setTimeout(done,60)},{once:true});
           setTimeout(done,4000); }
  })));
  document.querySelectorAll('*').forEach(e=>{e.style.animationPlayState='paused';});
  return vs.length;
}"""

async def shoot(pg, tag, width, label):
    d = SHOT / f"{label}_{width}"
    d.mkdir(parents=True, exist_ok=True)
    await pg.add_style_tag(content="#deck{height:auto!important;overflow:visible!important;"
                                   "scroll-snap-type:none!important}")
    await pg.wait_for_timeout(400)
    n = await pg.evaluate(PIN)
    await pg.wait_for_timeout(1200)
    for i in range(1, 35):
        el = await pg.query_selector(f"#s{i}")
        await el.screenshot(path=str(d / f"{i:02d}.png"))
    return n

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for width, height in ((390, 844), (1440, 900)):
            for label, url in (("folder", OUT / "index.html"),
                               ("embed", OUT / "olay_deck_embedded.html")):
                pg = await b.new_page(viewport={"width": width, "height": height})
                await pg.goto(f"file://{url}", wait_until="load", timeout=180_000)
                await pg.wait_for_timeout(2500)
                await shoot(pg, label, width, label)
                await pg.close()
        await b.close()

    bad = []
    for width in (390, 1440):
        diffs = []
        for i in range(1, 35):
            a = Image.open(SHOT / f"folder_{width}" / f"{i:02d}.png").convert("RGB")
            c = Image.open(SHOT / f"embed_{width}" / f"{i:02d}.png").convert("RGB")
            if a.size != c.size:
                bad.append(f"{width}px s{i}: size {a.size} vs {c.size}"); continue
            d = sum(ImageStat.Stat(ImageChops.difference(a, c)).mean) / 3
            diffs.append((d, i))
        diffs.sort(reverse=True)
        ident = sum(1 for d, _ in diffs if d == 0)
        print(f"  {width}px: {ident}/34 slides pixel-identical; "
              f"worst {', '.join(f's{i}={d:.4f}' for d, i in diffs[:3])}")
        for d, i in diffs:
            if d > 0.5: bad.append(f"{width}px s{i} diff {d:.4f}")
    print("\nPARITY OK" if not bad else "\nPARITY ISSUES:\n  " + "\n  ".join(bad))
    sys.exit(1 if bad else 0)

asyncio.run(main())
