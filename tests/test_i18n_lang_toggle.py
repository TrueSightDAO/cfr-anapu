"""Guards the CFR/SunMint PT-EN language toggle + cross-page preference retention.

Written after the 2026-09 change adding a PT/EN toggle to
`cfr-anapu/payout_registration.html`. The project convention is:
  * every user-facing page carries a `.lang-toggle` with #langPt / #langEn
  * the chosen language is persisted under localStorage key `sunmint_lang`
  * the stored value is reapplied on load (setLang(currentLang))
  * every `data-i18n*` / `t('...')` key resolves in BOTH pt and en

These are static (grep-style) invariants -- no browser needed -- so they fail
loudly if a page is added or refactored without the toggle wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LANG_KEY = "sunmint_lang"

# Pages that ship a user-facing UI and MUST have the toggle.
CFR_PAGES = [
    "index.html",
    "instrucoes/index.html",
    "limites-da-fazenda/index.html",
    "monitor-tree-growth/index.html",
    "payout_registration.html",
]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_every_cfr_page_has_the_language_toggle():
    for rel in CFR_PAGES:
        src = _read(rel)
        assert 'class="lang-toggle"' in src, f"{rel} missing .lang-toggle block"
        assert 'id="langPt"' in src and 'id="langEn"' in src, (
            f"{rel} missing PT/EN buttons"
        )


def test_pages_persist_preference_under_shared_key():
    for rel in CFR_PAGES:
        src = _read(rel)
        assert f"localStorage.getItem('{LANG_KEY}')" in src, (
            f"{rel} does not read {LANG_KEY}"
        )
        assert f"localStorage.setItem('{LANG_KEY}'" in src, (
            f"{rel} does not write {LANG_KEY}"
        )


def test_pages_reapply_stored_language_on_load():
    for rel in CFR_PAGES:
        src = _read(rel)
        assert "setLang(currentLang)" in src, f"{rel} never re-applies the stored language"


def test_toggle_defines_a_setlang_function():
    for rel in CFR_PAGES:
        assert re.search(r"function setLang\s*\(", _read(rel)), f"{rel} has no setLang()"


def test_payout_i18n_keys_resolve_in_both_languages():
    src = _read("payout_registration.html")
    used = set(re.findall(r'data-i18n(?:-html|-placeholder)?="([^"]+)"', src))
    used |= set(re.findall(r"\bt\('([^']+)'\)", src))
    assert used, "no i18n keys found in payout_registration.html"

    for lang in ("pt", "en"):
        # Key: value pairs live in the I18N.{pt,en} object literal.
        m = re.search(rf"\b{lang}: \{{(.*?)\n      \}},?\n", src, re.S)
        assert m, f"could not locate I18N.{lang}"
        # A bare `key:` not preceded by a word char or quote (excludes 'Page:' etc.)
        defined = set(re.findall(r"(?<![\w'\"])([A-Za-z][A-Za-z0-9]*):", m.group(1)))
        missing = sorted(used - defined)
        assert not missing, f"I18N.{lang} missing keys: {missing}"


def test_payout_default_language_matches_model_page():
    # mirror the convention used by monitor-tree-growth/: stored pref, else browser language
    src = _read("payout_registration.html")
    assert "DEFAULT_LANG" in src, "payout page should fall back to a navigator-based default"
