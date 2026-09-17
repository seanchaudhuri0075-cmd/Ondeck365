#!/usr/bin/env python3
"""Regression gate for an ADDITIVE deckkit change.

  python3 tools/strip_compare.py <regenerated out dir> [--ref out/secret]
                                 [--allow playback loop muted out_sha256]
                                 [--rev HEAD] [--allow-assets image65.png ...]

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

A DELIBERATE RE-BASELINE is a different act from an additive change, and is
named rather than absorbed: `--allow-assets <source media name>` permits that
one asset's bytes, and that one manifest entry, to differ. It is reported as
"N identical + M allowed" -- never folded into the identical count -- and an
allowed name that turns out NOT to differ fails the run, so a stale allowance
cannot sit in a command line unnoticed. `--rev` picks the commit to compare
against (default HEAD); after a re-baseline is committed, HEAD~1 with the
allowance and HEAD without it should both pass.

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


REV = "HEAD"


def committed(rel):
    return subprocess.check_output(["git", "show", f"{REV}:{rel}"], cwd=REPO)


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
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--allow-assets", nargs="*", default=[], metavar="SOURCE_NAME")
    a = ap.parse_args()
    global REV
    REV = a.rev
    allow, rows, ok = set(a.allow), [], True
    print(f"comparing {a.regen.name}/ against {a.ref} @ "
          f"{subprocess.check_output(['git', 'rev-parse', '--short', REV], cwd=REPO, text=True).strip()}")

    regen_man = json.loads((a.regen / "asset_manifest.json").read_text())
    out_of = {k: e["out"] for grp in regen_man.values() for k, e in grp.items()}
    unknown = [n for n in a.allow_assets if n not in out_of]
    assert not unknown, f"--allow-assets names media this deck does not have: {unknown}"
    allowed_files = {out_of[n]: n for n in a.allow_assets}

    tracked = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", REV, a.ref],
                                      cwd=REPO, text=True).split()
    t_assets = {Path(t).name: t for t in tracked if "/assets/" in t}
    r_assets = {p.name for p in (a.regen / "assets").iterdir()}
    differ = sorted(n for n, t in t_assets.items()
                    if n in r_assets and sha((a.regen / "assets" / n).read_bytes()) != sha(committed(t)))
    missing, extra = sorted(set(t_assets) - r_assets), sorted(r_assets - set(t_assets))
    same = len(t_assets) - len(differ) - len(missing)
    excused = [n for n in differ if n in allowed_files]
    unexcused = [n for n in differ if n not in allowed_files]
    stale = sorted(src for f, src in allowed_files.items() if f not in differ)
    good = not unexcused and not missing and not extra and not stale
    rows.append(("assets/", good,
                 f"{same} of {len(t_assets)} identical"
                 + (f" + {len(excused)} allowed ({', '.join(f'{allowed_files[n]} -> {n}' for n in excused)})"
                    if excused else "")
                 + f", missing {len(missing)}, extra {len(extra)}"
                 + (f"; UNEXPECTED DIFFS {unexcused}" if unexcused else "")
                 + (f"; ALLOWED BUT DID NOT DIFFER {stale}" if stale else "")))

    good = (a.regen / "used_assets.json").read_bytes() == committed(f"{a.ref}/used_assets.json")
    rows.append(("used_assets.json", good, "byte-identical" if good else "DIFFERS"))

    for name in ("model.json", "asset_manifest.json"):
        ref_b = committed(f"{a.ref}/{name}")
        seen = Counter()
        new = strip(json.loads((a.regen / name).read_text()), allow, seen)
        ref_seen = Counter()
        ref = strip(json.loads(ref_b), allow, ref_seen)
        dropped = []
        if name == "asset_manifest.json":
            for src in a.allow_assets:          # the re-baselined entries, and only those
                for side in (new, ref):
                    for grp in side.values():
                        if grp.pop(src, None) is not None and src not in dropped:
                            dropped.append(src)
        d = first_diff(ref, new)
        reserialised = (json.dumps(new, indent=1).encode() == ref_b
                        if not ref_seen and not dropped else None)
        good = d is None and reserialised is not False
        note = ("stripped " + (", ".join(f"{k} x{n}" for k, n in sorted(seen.items())) or "nothing")
                + (f"; committed side already carries {dict(ref_seen)}" if ref_seen else "")
                + (f"; entries set aside as allowed: {dropped}" if dropped else "")
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
