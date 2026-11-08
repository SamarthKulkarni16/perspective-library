#!/usr/bin/env python3
# CEO 2026-10-23: applies the quality patch to lang_build.py and lang_test.py. Every edit is anchored on exact text and asserted; any miss = nothing is written.
# usage: d23_pl_patch.py SCRIPTS_DIR      exit 0 = patched (or already patched), 1 = an anchor was not found
import sys, os, io

D = sys.argv[1]


def rep1(text, old, new, count=1):
    n = text.count(old)
    assert n == count, "anchor found %d times (want %d): %r" % (n, count, old[:80])
    return text.replace(old, new)


def rd(p):
    return io.open(p, encoding="utf-8").read()


def wr(p, t):
    io.open(p, "w", encoding="utf-8").write(t)


# ------------------------------------------------------------------ lang_build.py
p = os.path.join(D, "lang_build.py")
t = rd(p)
if "import pl_quality as Q" in t:
    print("lang_build.py already patched")
else:
    # 1. style + rules + hindi UI overrides (before st())
    t = rep1(t, "def st(en, lang):\n",
             "import pl_quality as Q\n"
             "for _l in LANGINFO:\n"
             "    LANGINFO[_l][\"style\"] = LANGINFO[_l][\"style\"] + \" \" + Q.STYLE_EXTRA[_l]\n"
             "SYS = SYS + Q.RULES_EXTRA\n"
             "Q.apply_ui_overrides(S)\n\n\n"
             "def st(en, lang):\n")
    # 2. old validator becomes the base; new valid() adds the extra rules
    t = rep1(t, "def valid(src, out, lang, is_html):", "def _valid_base(src, out, lang, is_html):")
    t = rep1(t, "class Engine:\n",
             "def valid(src, out, lang, is_html, kind=\"p\"):\n"
             "    ok, why = _valid_base(src, out, lang, is_html)\n"
             "    if not ok:\n"
             "        return ok, why\n"
             "    return Q.valid_extra(src, out, lang, kind)\n\n\n"
             "class Engine:\n")
    # 3. llm() takes an optional note (feedback from a rejected attempt)
    t = rep1(t, "    def llm(self, text, temperature):", "    def llm(self, text, temperature, note=\"\"):")
    t = rep1(t, "{\"role\": \"system\", \"content\": self.system}", "{\"role\": \"system\", \"content\": self.system + note}")
    t = rep1(t, "        self.failures = []\n", "        self.failures = []\n        self.soft = []\n")
    # 4. Engine.tr is replaced by a thin wrapper around pl_quality.tr_impl
    a = t.index("    def tr(self, src, is_html):")
    b = t.index("\n\nBLOCK_RE = re.compile(")
    assert a < b
    t = t[:a] + "    def tr(self, src, is_html, kind=\"p\"):\n        return Q.tr_impl(self, src, is_html, kind, valid)" + t[b:]
    # 5. headings and table cells are validated as headings; Arabic: Latin names isolated
    t = rep1(t, "        return m.group(1) + eng.tr(inner, True) + m.group(4)",
             "        val = eng.tr(inner, True, \"h\" if m.group(2).lower() in (\"h2\", \"h3\", \"th\", \"td\") else \"p\")\n"
             "        if eng.lang == \"ar\":\n"
             "            val = Q.wrap_ltr(val)\n"
             "        return m.group(1) + val + m.group(4)")
    t = rep1(t, "        return sec\n    post, n_seo = re.subn(",
             "        if lang == \"ar\":\n            sec = Q.wrap_ltr(sec)\n        return sec\n    post, n_seo = re.subn(")
    # 6. leftover English UI text (empty state, e-mail placeholder)
    t = rep1(t, "    handled = set()\n",
             "    pairs += [\n"
             "        ('<h2>The shelves are empty.</h2>', '<h2>%s</h2>' % HE(Q.EXTRA_UI[lang][\"empty_h\"])),\n"
             "        ('<p>Books will appear here once they\\'re added to the <code style=\"background:#1e1e1e;padding:2px 6px;border-radius:4px;font-size:11px\">ARTICLES</code> array in the source code.</p>', '<p>%s</p>' % Q.EXTRA_UI[lang][\"empty_p\"]),\n"
             "        ('placeholder=\"you@example.com\"', 'placeholder=\"%s\"' % Q.EXTRA_UI[lang][\"email_ph\"]),\n"
             "    ]\n"
             "    handled = set()\n")
    # 7. reading-progress document id: per language and per book slug (the old one collapsed every non-Latin title to the same id)
    t = rep1(t, "    post = post.replace(ORIG_BASE, site_base(lang))\n",
             "    post = post.replace(ORIG_BASE, site_base(lang))\n"
             "    _pd = \"return sanitize(email) + '_' + sanitize(title);\"\n"
             "    if _pd in post:\n"
             "        post = post.replace(_pd, \"const _a = ARTICLES.find(x => x.title === title); return sanitize(email) + '_%s_' + sanitize(_a && _a.slug ? _a.slug : title);\" % lang)\n"
             "    else:\n"
             "        rep.setdefault(\"errors\", []).append(\"progressDocId was not patched\")\n")
    # 8. report: soft issues, audit, errors make a build incomplete
    t = rep1(t, "    rep[\"complete\"] = (not eng.failures) and (not rep[\"untranslated\"])",
             "    rep[\"soft_count\"] = len(eng.soft)\n"
             "    rep[\"soft_issues\"] = eng.soft[:80]\n"
             "    rep[\"audit\"] = getattr(eng, \"audit\", [])[:40]\n"
             "    rep[\"complete\"] = (not eng.failures) and (not rep[\"untranslated\"]) and (not rep.get(\"errors\"))")
    compile(t, "lang_build.py", "exec")
    wr(p, t)
    print("lang_build.py patched")

# ------------------------------------------------------------------ lang_test.py
p = os.path.join(D, "lang_test.py")
t = rd(p)
if "import pl_quality as Q" in t:
    print("lang_test.py already patched")
else:
    t = rep1(t, "from playwright.sync_api import sync_playwright\n",
             "from playwright.sync_api import sync_playwright\n"
             "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
             "import pl_quality as Q\n")
    section7 = (
        "    print(\"== [%s] 7. quality: reading-progress ids, leaks, empty state, placeholder\" % LANG)\n"
        "    ctxo, pgo, _eo = mk(browser)\n"
        "    pgo.goto(BASE + \"/orig/index.html\")\n"
        "    pgo.wait_for_selector(\".book-card\", timeout=8000)\n"
        "    en_text = pgo.evaluate(\"ARTICLES.map(a=>[a.title,a.subtitle,a.content].join(' ')).join(' ')\")\n"
        "    en_caps = Q.caps_tokens(en_text)\n"
        "    ctxo.close()\n"
        "    ctx, page, errs = mk(browser)\n"
        "    page.goto(BASE + \"/site/index.html\")\n"
        "    page.wait_for_selector(\".book-card\", timeout=8000)\n"
        "    ids = page.evaluate(\"ARTICLES.map(a=>progressDocId('a@b.c', a.title))\")\n"
        "    check(\"reading-progress id differs for every book and per language\", len(set(ids)) == len(ids) and all((\"_%s_\" % LANG) in i for i in ids), ids)\n"
        "    allt = page.evaluate(\"ARTICLES.map(a=>[a.title,a.subtitle,a.category,a.content].join(' ')).join(' ')\")\n"
        "    bad = Q.scan_text(allt, LANG, en_caps)\n"
        "    check(\"no leaks in the books (CJK, chatbot text, markdown, English leftovers)\", not bad, bad[:3])\n"
        "    print(\"  INFO style issues in the whole text: %d\" % len(Q.soft_issues(Q.plain(allt), LANG)))\n"
        "    emp = page.evaluate(\"document.getElementById('empty-state').textContent\")\n"
        "    check(\"empty-state text translated\", \"shelves are empty\" not in emp and \"source code\" not in emp, emp[:60])\n"
        "    ph = page.evaluate(\"document.getElementById('field-email').placeholder\")\n"
        "    check(\"email placeholder localised\", ph != \"you@example.com\", ph)\n"
        "    if LANG == \"ar\":\n"
        "        check(\"Latin names isolated for right-to-left reading\", page.evaluate(\"document.querySelectorAll('bdi').length\") > 0)\n"
        "    ctx.close()\n")
    t = rep1(t, "    ctx.close()\n    browser.close()\n", "    ctx.close()\n" + section7 + "    browser.close()\n")
    compile(t, "lang_test.py", "exec")
    wr(p, t)
    print("lang_test.py patched")
print("PATCH OK")
