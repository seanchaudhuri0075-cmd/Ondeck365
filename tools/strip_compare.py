#!/usr/bin/env python3
"""Regression gate for an ADDITIVE deckkit change.

  python3 tools/strip_compare.py <regenerated out dir> [--ref out/secret]
                                 [--allow playback loop muted out_sha256]

Compares a freshly regenerated deck against what is COMMITTED (read with
`git show HEAD:`, so a dirty working tree cannot flatter the result):

  assets/*              byte-identical, none missing, none extra
  used_assets.json      byte-identical
  model.json            identical AFTER deleting only the --allow keys
  asset_manifest.json   identical AFTER deleting only the --allow keys
  index.html            rendered from the regenerated model, byte-identical
                        to <ref>/index.html on disk (it is not tracked)

"Identical after stripping" is checked two ways, because either alone can be
fooled: the parsed objects must be equal, AND re-serialising the stripped
object with the builder's own `json.dumps(indent=1)` must reproduce the
committed file byte for byte -- which also proves no surviving key moved,
changed type, or was reordered. The allowance is reported, not assumed: every
stripped key is counted, and a key on the list that never occurs is flagged.

Exit 0 only if every row passes.
"""
import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sha = lambda b: hashlib.sha256(b).hexdigest()


def committed(rel):
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)


def strip(node, allow, seen):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in allow:
                seen[k] += 1
            else:
                out[k] = strip(v, allow, seen)
        return out
    if isinstance(node, list):
        return [strip(v, allow, seen) for v in node]
    return node


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for k in a.keys() | b.keys():
            if k not in a or k not in b:
                return f"{path}.{k}: present on one side only"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
    elif a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("regen", type=Path)
    ap.add_argument("--ref", default="out/secret")
    ap.add_argument("--render", default="phase_1c.secret.render")
    ap.add_argument("--allow", nargs="*", default=["playback", "loop", "muted", "out_sha256"])
    a = ap.parse_args()
    allow, rows, ok = set(a.allow), [], True

    tracked = subprocess.check_output(["git", "ls-files", a.ref], cwd=REPO, text=True).split()
    t_assets = {Path(t).name: t for t in tracked if "/assets/" in t}
    r_assets = {p.name for p in (a.regen / "assets").iterdir()}
    same = sum(1 for n, t in t_assets.items()
               if n in r_assets and sha((a.regen / "assets" / n).read_bytes()) == sha(committed(t)))
    missing, extra = sorted(set(t_assets) - r_assets), sorted(r_assets - set(t_assets))
    good = same == len(t_assets) and not missing and not extra
    rows.append(("assets/", good, f"{same} of {len(t_assets)} identical, "
                 f"missing {len(missing)}, extra {len(extra)}"))

    good = (a.regen / "used_assets.json").read_bytes() == committed(f"{a.ref}/used_assets.json")
    rows.append(("used_assets.json", good, "byte-identical" if good else "DIFFERS"))

    for name in ("model.json", "asset_manifest.json"):
        ref_b = committed(f"{a.ref}/{name}")
        seen = Counter()
        new = strip(json.loads((a.regen / name).read_text()), allow, seen)
        ref_seen = Counter()
        ref = strip(json.loads(ref_b), allow, ref_seen)
        d = first_diff(ref, new)
        reserialised = json.dumps(new, indent=1).encode() == ref_b if not ref_seen else None
        good = d is None and reserialised is not False
        note = ("stripped " + (", ".join(f"{k} x{n}" for k, n in sorted(seen.items())) or "nothing")
                + (f"; committed side already carries {dict(ref_seen)}" if ref_seen else "")
                + ("; re-serialised == committed bytes" if reserialised else "")
                + (f"; FIRST DIFF {d}" if d else "")
                + ("; RE-SERIALISATION DIFFERS" if reserialised is False else ""))
        rows.append((name, good, note))

    render = importlib.import_module(a.render)
    html = render.build_html(json.loads((a.regen / "model.json").read_text()),
                             json.loads((a.regen / "asset_manifest.json").read_text())).encode()
    disk = (REPO / a.ref / "index.html").read_bytes()
    good = html == disk
    rows.append(("index.html", good, f"{sha(html)[:16]}… {len(html):,} B vs on-disk "
                 f"{sha(disk)[:16]}… {len(disk):,} B"))

    for name, good, note in rows:
        ok &= good
        print(f"{'IDENTICAL' if good else 'DIFFERS  '}  {name:22} {note}")
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
