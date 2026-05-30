# Phase 1C — Color Transform Evidence (P&G deck)

**Source:** `/Users/gif025/Downloads/4f8d0812-4135-4589-9535-03a2ebd1b9e7.pptx`
**Scope:** `ppt/slides/*.xml` · `ppt/slideLayouts/*.xml` · `ppt/slideMasters/*.xml` · `ppt/theme/*.xml`

## Summary

P&G deck uses **6 distinct color-transform kinds** across **182 occurrences** in slides + layouts + masters + theme. Most common transform: **shade (49 occurrences)**, concentrated in slides (39/49). 6 distinct `<a:schemeClr val>` keys referenced (448 total uses; 5 carry transforms, 1 are bare).

## Counts (by transform × file category)

| transform | total | slides | slideLayouts | slideMasters | theme |
|---|---:|---:|---:|---:|---:|
| `<a:lumMod>` | 30 | 14 | 0 | 0 | 16 |
| `<a:lumOff>` | 14 | 14 | 0 | 0 | 0 |
| `<a:tint>` | 27 | 1 | 9 | 3 | 14 |
| `<a:shade>` | 49 | 39 | 0 | 0 | 10 |
| `<a:satMod>` | 33 | 13 | 0 | 0 | 20 |
| `<a:hueMod>` | 0 | 0 | 0 | 0 | 0 |
| `<a:alpha>` | 29 | 27 | 0 | 0 | 2 |

## Representative examples

### `<a:lumMod>` — 30 occurrences

**Example 1** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr` val=45000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="44000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
    <a:alpha val="0"/>
  </a:schemeClr>
</a:gs>
```

**Example 2** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr` val=45000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="100000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
  </a:schemeClr>
</a:gs>
```

**Example 3** — `ppt/slides/slide13.xml` line 2 (parent color: `schemeClr` val=45000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="44000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
    <a:alpha val="0"/>
  </a:schemeClr>
</a:gs>
```

### `<a:lumOff>` — 14 occurrences

**Example 1** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr` val=55000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="44000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
    <a:alpha val="0"/>
  </a:schemeClr>
</a:gs>
```

**Example 2** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr` val=55000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="100000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
  </a:schemeClr>
</a:gs>
```

**Example 3** — `ppt/slides/slide13.xml` line 2 (parent color: `schemeClr` val=55000)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="44000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
    <a:alpha val="0"/>
  </a:schemeClr>
</a:gs>
```

### `<a:tint>` — 27 occurrences

**Example 1** — `ppt/slideLayouts/slideLayout3.xml` line 2 (parent color: `schemeClr` val=82000)

```xml
<a:solidFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <a:schemeClr val="tx1">
    <a:tint val="82000"/>
  </a:schemeClr>
</a:solidFill>
```

**Example 2** — `ppt/slideLayouts/slideLayout3.xml` line 2 (parent color: `schemeClr` val=82000)

```xml
<a:solidFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <a:schemeClr val="tx1">
    <a:tint val="82000"/>
  </a:schemeClr>
</a:solidFill>
```

**Example 3** — `ppt/slideLayouts/slideLayout3.xml` line 2 (parent color: `schemeClr` val=82000)

```xml
<a:solidFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <a:schemeClr val="tx1">
    <a:tint val="82000"/>
  </a:schemeClr>
</a:solidFill>
```

### `<a:shade>` — 49 occurrences

**Example 1** — `ppt/slides/slide1.xml` line 2 (parent color: `schemeClr` val=15000)

```xml
<a:lnRef xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" idx="2">
  <a:schemeClr val="accent1">
    <a:shade val="15000"/>
  </a:schemeClr>
</a:lnRef>
```

**Example 2** — `ppt/slides/slide1.xml` line 2 (parent color: `schemeClr` val=45000)

```xml
<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <a:blip r:embed="rId3" cstate="email">
    <a:duotone>
      <a:schemeClr val="bg2">
        <a:shade val="45000"/>
        <a:satMod val="135000"/>
      </a:schemeClr>
      <a:prstClr val="white"/>
    </a:duotone>
    <a:extLst>
...(truncated)
```

**Example 3** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr` val=15000)

```xml
<a:lnRef xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" idx="2">
  <a:schemeClr val="accent1">
    <a:shade val="15000"/>
  </a:schemeClr>
</a:lnRef>
```

### `<a:satMod>` — 33 occurrences

**Example 1** — `ppt/slides/slide1.xml` line 2 (parent color: `schemeClr` val=135000)

```xml
<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <a:blip r:embed="rId3" cstate="email">
    <a:duotone>
      <a:schemeClr val="bg2">
        <a:shade val="45000"/>
        <a:satMod val="135000"/>
      </a:schemeClr>
      <a:prstClr val="white"/>
    </a:duotone>
    <a:extLst>
...(truncated)
```

**Example 2** — `ppt/slides/slide11.xml` line 2 (parent color: `schemeClr` val=135000)

```xml
<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <a:blip r:embed="rId2" cstate="email">
    <a:duotone>
      <a:schemeClr val="bg2">
        <a:shade val="45000"/>
        <a:satMod val="135000"/>
      </a:schemeClr>
      <a:prstClr val="white"/>
    </a:duotone>
    <a:extLst>
...(truncated)
```

**Example 3** — `ppt/slides/slide2.xml` line 2 (parent color: `srgbClr` val=400000)

```xml
<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <a:blip r:embed="rId2" cstate="email">
    <a:duotone>
      <a:prstClr val="black"/>
      <a:srgbClr val="53C1EA">
        <a:tint val="45000"/>
        <a:satMod val="400000"/>
      </a:srgbClr>
    </a:duotone>
    <a:alphaModFix amt
...(truncated)
```

### `<a:hueMod>` — 0 occurrences (skipped)

### `<a:alpha>` — 29 occurrences

**Example 1** — `ppt/slides/slide1.xml` line 2 (parent color: `schemeClr`)

```xml
<a:solidFill xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <a:schemeClr val="bg1">
    <a:alpha val="38000"/>
  </a:schemeClr>
</a:solidFill>
```

**Example 2** — `ppt/slides/slide10.xml` line 2 (parent color: `schemeClr`)

```xml
<a:gs xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" pos="44000">
  <a:schemeClr val="accent1">
    <a:lumMod val="45000"/>
    <a:lumOff val="55000"/>
    <a:alpha val="0"/>
  </a:schemeClr>
</a:gs>
```

**Example 3** — `ppt/slides/slide10.xml` line 2 (parent color: `prstClr`)

```xml
<a:outerShdw xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" blurRad="70161" dist="38100" dir="2700000" algn="tl" rotWithShape="0">
  <a:prstClr val="black">
    <a:alpha val="26000"/>
  </a:prstClr>
</a:outerShdw>
```

## Distinct `<a:schemeClr val="...">` values referenced

| val | total uses | bare (no transform) | with transforms | transforms applied |
|---|---:|---:|---:|---|
| `bg1` | 182 | 181 | 1 | `alpha` |
| `accent1` | 101 | 60 | 41 | `alpha`, `lumMod`, `lumOff`, `shade` |
| `lt1` | 90 | 90 | 0 | — |
| `tx1` | 33 | 21 | 12 | `tint` |
| `phClr` | 30 | 10 | 20 | `lumMod`, `satMod`, `shade`, `tint` |
| `bg2` | 12 | 0 | 12 | `satMod`, `shade` |

## Notes

- `<a:alpha>` count is restricted to alpha applied directly to a color element (`srgbClr`/`schemeClr`/`prstClr`/`sysClr`), per task scope.
- "Parent color" in examples = the immediate color element the transform child belongs to (e.g. `schemeClr` if `<a:schemeClr><a:lumMod/></a:schemeClr>`).
- Transforms in `<a:bgFillStyleLst>` / `<a:fillStyleLst>` / `<a:lnStyleLst>` / `<a:effectStyleLst>` (theme) are template definitions consumed via `<a:fillRef idx>`/`<a:lnRef idx>` references on shapes — they fire whenever a shape references that style index.
- `tint` lightens (mixes toward white); `shade` darkens (mixes toward black); `lumMod`/`lumOff` work in HSL luminance; `satMod` scales saturation; `hueMod` rotates hue.
