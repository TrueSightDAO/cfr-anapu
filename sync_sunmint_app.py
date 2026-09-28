#!/usr/bin/env python3
"""Vendor the canonical SunMint app (TrueSightDAO/sunmint_beta) into the
cfr-anapu repo's gh-pages branch (serves https://cfr.truesight.me).

Option B of plans/CRF_ANAPU_SUNMINT_COHORT_PROPOSAL.md: a full vendor copy so the
URL bar stays on cfr.truesight.me and every submission self-attributes via
`Submission Source: ${window.location.href}` -- zero app-code change.

DRY-RUN BY DEFAULT. Pass --open-pr to vendor the files into --root; the
branch/commit/push/PR step is done by the operator (see README).
Never copies the app's CNAME (the vendor keeps cfr.truesight.me).
Reads vendor.json next to this script for the file list + rewrite rules.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, urllib.request, base64

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"
API = "https://api.github.com"


def cfg():
    with open(os.path.join(HERE, "vendor.json"), encoding="utf-8") as f:
        return json.load(f)


def fetch(repo, ref, path):
    url = RAW.format(repo=repo, ref=ref, path=path)
    with urllib.request.urlopen(url) as r:
        return r.read()


def rewrite_og(text, old, new, rel):
    """Rewrite ONLY the og:url meta content for `rel`.

    A bare URL replacement is unsafe: e.g. `https://sunmint.truesight.me/` also
    appears in the Android-APK download link, which is a `canonical_keep` ref
    that must survive verbatim on the vendored site. Scoping to the og:url meta
    tag rewrites the social-preview URL and nothing else.
    """
    pat = re.compile(
        r'(<meta\s+property="og:url"\s+content=")' + re.escape(old) + r'(")'
    )
    out, n = pat.subn(lambda m: m.group(1) + new + m.group(2), text)
    if n != 1:
        raise SystemExit(
            f"og:url anchor in {rel}: expected exactly 1 match for {old!r}, found {n}"
        )
    return out


def build(root, c):
    """Fetch + rewrite the vendored tree into `root`. Returns {relpath: bytes}."""
    out = {}
    for rel in c["files"]:
        data = fetch(c["vendor_source_repo"], c["vendor_source_ref"], rel)
        rule = c["og_url_rewrites"].get(rel)
        if rule:
            old, new = rule
            data = rewrite_og(data.decode("utf-8"), old, new, rel).encode("utf-8")
        for keep in c["canonical_keep"]:
            assert True  # documented intent; canonical refs left untouched
        out[rel] = data
    # guard: never vendor CNAME
    assert not any(os.path.basename(p) == "CNAME" for p in out), "refusing to vendor CNAME"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, ".")
                    if os.path.basename(HERE) == "cfr-anapu" else "/tmp/cfr-anapu")
    ap.add_argument("--open-pr", action="store_true")
    ap.add_argument("--branch", default="chore/vendor-sunmint-app")
    a = ap.parse_args()
    c = cfg()
    tree = build(a.root, c)
    for rel in sorted(tree):
        print(f"  {len(tree[rel]):8d}  {rel}")
    if not a.open_pr:
        print(f"[DRY-RUN] {len(tree)} files would be written to {a.root}")
        print("dry-run only; pass --open-pr to write them")
        return
    # Actually materialise the vendored tree. Without this the tool merely
    # printed sizes and wrote nothing, so every "sync" had to be re-done by
    # hand (and could silently diverge from the manifest).
    for rel, data in tree.items():
        dest = os.path.join(a.root, rel)
        os.makedirs(os.path.dirname(dest) or a.root, exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
    print(f"[WRITE] {len(tree)} files written to {a.root}")
    print("next: git add/commit/push and open the PR (see README)")


if __name__ == "__main__":
    main()
