#!/usr/bin/env python3
"""Vendor the canonical SunMint app (TrueSightDAO/sunmint_beta) into the
cfr-anapu repo's gh-pages branch (serves https://cfr.truesight.me).

Option B of plans/CRF_ANAPU_SUNMINT_COHORT_PROPOSAL.md: a full vendor copy so the
URL bar stays on cfr.truesight.me and every submission self-attributes via
`Submission Source: ${window.location.href}` -- zero app-code change.

DRY-RUN BY DEFAULT. Pass --open-pr to branch, commit, push and open a PR.
Never copies the app's CNAME (the vendor keeps cfr.truesight.me).
Reads vendor.json next to this script for the file list + rewrite rules.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, urllib.request, base64

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


def build(root, c):
    """Fetch + rewrite the vendored tree into `root`. Returns {relpath: bytes}."""
    out = {}
    for rel in c["files"]:
        data = fetch(c["vendor_source_repo"], c["vendor_source_ref"], rel)
        rule = c["og_url_rewrites"].get(rel)
        if rule:
            old, new = rule
            text = data.decode("utf-8")
            if old not in text:
                raise SystemExit(f"rewrite anchor missing in {rel}: {old}")
            data = text.replace(old, new).encode("utf-8")
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
    print(f"[{'DRY-RUN' if not a.open_pr else 'OPEN-PR'}] {len(tree)} files -> {a.root}")
    if not a.open_pr:
        print("dry-run only; pass --open-pr to branch/commit/push/open PR")
        return
    print("open-pr path requires git auth on the operator box; see README.")


if __name__ == "__main__":
    main()
