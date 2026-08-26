"""Verify the embedded file WITHOUT executing any script.

The Deck Editor parses with DOMParser and never runs JS, so the only honest
test is a JS-disabled parse: whatever is visible there is what the editor sees.
"""
import asyncio, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
EMB = OUT / "olay_deck_embedded.html"

fails = []
def check(cond, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        fails.append(msg)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # scripts disabled — this is the editor's view of the document
        ctx = await b.new_context(java_script_enabled=False,
                                  viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        await pg.goto(f"file://{EMB}", wait_until="load", timeout=180_000)

        n_slides = len(await pg.query_selector_all("section.slide"))
        check(n_slides == 34, f"34 sections with class=slide parse with scripts disabled ({n_slides})")

        ids = [await e.get_attribute("id") for e in await pg.query_selector_all("section.slide")]
        check(ids == [f"s{i}" for i in range(1, 35)], "ids are sequential s1..s34")
        rails = [await e.get_attribute("data-slide") for e in await pg.query_selector_all("section.slide")]
        check(rails == [str(i) for i in range(1, 35)], "rail labels (data-slide) present and sequential")

        imgs = await pg.query_selector_all("img")
        vids = await pg.query_selector_all("video")
        img_data = [e for e in imgs if (await e.get_attribute("src") or "").startswith("data:")]
        vid_data = [e for e in vids if (await e.get_attribute("src") or "").startswith("data:")]
        check(len(img_data) == len(imgs) and len(imgs) > 0,
              f"every <img> has a literal data: src ({len(img_data)}/{len(imgs)})")
        check(len(vid_data) == len(vids) and len(vids) == 31,
              f"every <video> has a literal data: src ({len(vid_data)}/{len(vids)})")

        for sel in ("[srcset]", "picture", "source"):
            n = len(await pg.query_selector_all(sel))
            check(n == 0, f"no {sel} elements ({n})")

        # Live text, counted the same way the folder build is validated.
        html = EMB.read_text()
        import html as _h
        body = "".join(_h.unescape(m) for m in re.findall(r"<p[^>]*>([^<]*)</p>", html))
        body = body.replace("\xa0", "")
        check(len(body) == 4051, f"live text is exactly 4051 characters ({len(body)})")

        for phrase in ("Wrong package", "This looks too fake", "Move forward"):
            check(phrase not in html, f"review sticker text absent: {phrase!r}")
        s33 = re.search(r'<section class="slide" id="s33".*?</section>', html, re.S).group(0)
        check("Focus on product-centric" not in s33, "occluded slide-2 copy absent from slide 33")
        check(html.count('alt="Creative Brief"') == 1, "'Creative Brief' banner appears exactly once")

        await ctx.close(); await b.close()

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}")
    sys.exit(1 if fails else 0)

asyncio.run(main())
