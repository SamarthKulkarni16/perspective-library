#!/usr/bin/env python3
# CEO 2026-10-20: headless-browser proof for one built language site.
# usage: lang_test.py SITE_DIR LANG ORIG_DIR   (exit 0 only if every test passes)
import sys, os, re, json, time, threading, http.server, socketserver, functools, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pl_quality as Q

SITE, LANG, ORIG = sys.argv[1:4]
ROOT = tempfile.mkdtemp(prefix="pltest_")
os.symlink(os.path.abspath(SITE), ROOT + "/site")
os.symlink(os.path.abspath(ORIG), ROOT + "/orig")
PORT = 8200 + {"hi": 1, "ar": 2, "pt": 3, "es": 4}.get(LANG, 0)
BASE = "http://127.0.0.1:%d" % PORT
SHOTS = "/tmp/plshots"
os.makedirs(SHOTS, exist_ok=True)
SCRIPT = {"hi": "\u0900-\u097F", "ar": "\u0600-\u06FF"}.get(LANG)
EN_STOP = set("the and you is are to of that it in for with this your what when was have not but they will can from there their been which would about".split())

STUB = """
window.__fakeUser = (window.__fakeUser === undefined) ? {email:'t@example.com', displayName:'Tester', photoURL:null} : window.__fakeUser;
(function(){
  var authFn = function(){ return {
    onAuthStateChanged: function(cb){ window.__authCb = cb; setTimeout(function(){ cb(window.__fakeUser); }, 50); },
    signInWithPopup: function(){ return Promise.resolve(); },
    signInWithEmailAndPassword: function(){ return Promise.resolve(); },
    createUserWithEmailAndPassword: function(){ return Promise.resolve({user:{updateProfile:function(){}}}); },
    signOut: function(){ return Promise.resolve(); } }; };
  authFn.GoogleAuthProvider = function(){};
  window.firebase = {
    initializeApp: function(){},
    auth: authFn,
    firestore: function(){ return { collection: function(){ return { doc: function(){ return {
      get: function(){ return Promise.resolve({exists:false}); }, set: function(){ return Promise.resolve(); } }; } }; } }; }
  };
})();
"""


def handler(route):
    u = route.request.url
    if u.startswith(BASE):
        return route.continue_()
    if "firebase-app-compat" in u:
        return route.fulfill(status=200, content_type="application/javascript", body=STUB)
    if "firebasejs" in u:
        return route.fulfill(status=200, content_type="application/javascript", body="")
    return route.abort()


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()

fails = []


def check(name, cond, extra=""):
    print("  %s %s %s" % ("PASS" if cond else "FAIL", name, str(extra)[:160]))
    if not cond:
        fails.append(name)


def mk(browser, user=True, w=1280, h=800):
    ctx = browser.new_context(viewport={"width": w, "height": h})
    if not user:
        ctx.add_init_script("window.__fakeUser = null;")
    errs = []
    page = ctx.new_page()
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.route("**/*", handler)
    return ctx, page, errs


STRUCT = r"""() => { const c=document.getElementById('modal-content'); const q=s=>c.querySelectorAll(s).length;
 return {p:q('p'),h2:q('h2'),h3:q('h3'),table:q('table'),th:q('th'),td:q('td'),li:q('li'),strong:q('strong'),br:q('br'),
         paras:c.textContent.split('\n\n').length, text:c.textContent}; }"""


def lang_ok(text):
    letters = re.findall(r"[^\W\d_]", text)
    if SCRIPT:
        tgt = re.findall("[" + SCRIPT + "]", text)
        return len(tgt) / max(1, len(letters)) >= 0.5, "script ratio %.2f" % (len(tgt) / max(1, len(letters)))
    words = re.findall(r"[A-Za-z']+", text.lower())
    r = sum(w in EN_STOP for w in words) / max(1, len(words))
    return r < 0.12, "english-stopword ratio %.3f" % r


with sync_playwright() as p:
    try:
        browser = p.chromium.launch(headless=True)
    except Exception as e:
        print("default chromium failed (%s), trying system chrome" % str(e)[:100])
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome-stable")

    print("== [%s] 1. page loads, structure, language attributes" % LANG)
    ctx, page, errs = mk(browser)
    page.goto(BASE + "/orig/index.html")
    page.wait_for_selector(".book-card", timeout=8000)
    books = page.evaluate("ARTICLES.map(a=>({slug:a.slug,title:a.title,isHtml:!!a.isHtml}))")
    en_cards = page.locator(".book-card").count()
    ctx.close()
    ctx, page, errs = mk(browser)
    page.goto(BASE + "/site/index.html")
    page.wait_for_selector(".book-card", timeout=8000)
    time.sleep(0.5)
    check("same number of books on the shelf", page.locator(".book-card").count() == en_cards, "%d vs %d" % (page.locator(".book-card").count(), en_cards))
    check("html lang attribute", page.evaluate("document.documentElement.lang") == LANG, page.evaluate("document.documentElement.lang"))
    d = page.evaluate("document.documentElement.dir")
    check("text direction", (d == "rtl") if LANG == "ar" else (d in ("", "ltr")), repr(d))
    check("no JavaScript errors", len(errs) == 0, errs)
    check("page title translated", page.title() != "Perspective Library \u2014 Free Books on Psychology, Emotions & Mindset", page.title())
    st1 = page.inner_text("#btn-signout"); h1 = page.inner_text(".lib-heading h1")
    check("sign out + heading translated", st1 != "Sign out" and h1 != "The Library", "%s | %s" % (st1, h1))
    rt = page.inner_text(".book-readtime >> nth=0")
    check("reading time label translated and has a number", "min read" not in rt and re.search(r"\d", rt) is not None, rt)
    page.screenshot(path="%s/%s_shelf.png" % (SHOTS, LANG))
    ctx.close()

    print("== [%s] 2. every book opens, same structure as the English book, translated text" % LANG)
    for i, b in enumerate(books):
        ctx, pg_o, _ = mk(browser)
        pg_o.goto("%s/orig/index.html#book/%s" % (BASE, b["slug"]))
        pg_o.wait_for_selector("#modal-overlay.open", timeout=8000)
        so = pg_o.evaluate(STRUCT)
        ctx.close()
        ctx, pg, errs = mk(browser)
        pg.goto("%s/site/index.html#book/%s" % (BASE, b["slug"]))
        try:
            pg.wait_for_selector("#modal-overlay.open", timeout=8000)
        except Exception:
            check("book %s opens by link" % b["slug"], False); ctx.close(); continue
        time.sleep(0.4)
        sl = pg.evaluate(STRUCT)
        title = pg.inner_text("#modal-title")
        check("%s: opens by link, title translated" % b["slug"], title != b["title"] or LANG == "xx", title)
        keys = ("table", "th", "td", "h2", "h3", "li", "strong", "br") if b["isHtml"] else ("paras",)
        same = all(so[k] == sl[k] for k in keys)
        check("%s: same structure as English" % b["slug"], same, {k: (so[k], sl[k]) for k in keys if so[k] != sl[k]})
        if b["isHtml"]:
            check("%s: same number of paragraphs" % b["slug"], so["p"] == sl["p"], "%d vs %d" % (so["p"], sl["p"]))
        ok, why = lang_ok(sl["text"])
        check("%s: text is in the target language" % b["slug"], ok, why)
        check("%s: no errors" % b["slug"], len(errs) == 0, errs)
        if i in (0, 1):
            time.sleep(0.5)
            pg.screenshot(path="%s/%s_book_%s.png" % (SHOTS, LANG, b["slug"]))
        ctx.close()

    print("== [%s] 3. clicking, URL, UTM tags" % LANG)
    ctx, page, errs = mk(browser)
    page.goto(BASE + "/site/index.html?utm_source=youtube&utm_medium=video&utm_campaign=survival")
    page.wait_for_selector(".book-card", timeout=8000)
    page.click(".book-card >> nth=3")
    page.wait_for_selector("#modal-overlay.open", timeout=5000)
    q = page.evaluate("location.search + location.hash")
    check("click sets #book/<slug> and keeps UTM tags", q == "?utm_source=youtube&utm_medium=video&utm_campaign=survival#book/" + books[3]["slug"], q)
    page.click("#modal-close")
    page.wait_for_function("!document.getElementById('modal-overlay').classList.contains('open')", timeout=5000)
    check("close clears the book from the URL", page.evaluate("location.hash") == "", page.evaluate("location.hash"))
    ctx.close()

    print("== [%s] 4. sign-in screen translated" % LANG)
    ctx, page, errs = mk(browser, user=False)
    page.goto(BASE + "/site/index.html")
    page.wait_for_selector("#auth-screen", state="visible", timeout=8000)
    time.sleep(0.4)
    g = page.inner_text("#btn-google"); e = page.inner_text("#btn-enter"); lab = page.locator(".field label").all_inner_texts()
    check("Google button translated", "Continue with Google" not in g, g)
    check("Enter button translated", e.strip() != "Enter Library", e)
    check("field labels translated", not ({"Name", "Email", "Password"} & set(l.strip() for l in lab)) or LANG in ("pt",) , lab)
    if SCRIPT:
        check("enter button is in the target script", re.search("[" + SCRIPT + "]", e) is not None, e)
    page.screenshot(path="%s/%s_signin.png" % (SHOTS, LANG))
    ctx.close()

    print("== [%s] 5. SEO section and JSON-LD" % LANG)
    ctx, page, errs = mk(browser)
    page.goto(BASE + "/site/index.html")
    page.wait_for_selector(".book-card", timeout=8000)
    s_h1 = page.evaluate("document.querySelector('#seo-preview h1').textContent")
    check("SEO heading translated", "Free Books on Psychology" not in s_h1, s_h1)
    check("SEO article count", page.evaluate("document.querySelectorAll('#seo-preview article').length") == len(books))
    seo_t = page.evaluate("document.getElementById('seo-preview').textContent")
    ok, why = lang_ok(seo_t)
    check("SEO text is in the target language", ok, why)
    try:
        ld = json.loads(page.evaluate("document.querySelector('script[type=\"application/ld+json\"]').textContent"))
        check("JSON-LD language and url", ld.get("inLanguage") == LANG and ("perspective-library-%s" % LANG) in ld.get("url", ""), ld.get("url"))
    except Exception as ex:
        check("JSON-LD parses", False, ex)
    ctx.close()

    print("== [%s] 6. phone width: nothing wider than the screen" % LANG)
    ctx, page, errs = mk(browser, w=390, h=844)
    page.goto(BASE + "/site/index.html")
    page.wait_for_selector(".book-card", timeout=8000)
    time.sleep(0.4)
    check("shelf fits the phone width", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    page.screenshot(path="%s/%s_phone_shelf.png" % (SHOTS, LANG))
    page.click(".book-card >> nth=1")
    page.wait_for_selector("#modal-overlay.open", timeout=5000)
    time.sleep(0.5)
    check("open book fits the phone width", page.evaluate("(function(){var m=document.getElementById('modal-overlay');return m.scrollWidth <= m.clientWidth + 1;})()"))
    page.screenshot(path="%s/%s_phone_book.png" % (SHOTS, LANG))
    ctx.close()
    print("== [%s] 7. quality: reading-progress ids, leaks, empty state, placeholder" % LANG)
    ctxo, pgo, _eo = mk(browser)
    pgo.goto(BASE + "/orig/index.html")
    pgo.wait_for_selector(".book-card", timeout=8000)
    en_text = pgo.evaluate("ARTICLES.map(a=>[a.title,a.subtitle,a.content].join(' ')).join(' ')")
    en_caps = Q.caps_tokens(en_text)
    ctxo.close()
    ctx, page, errs = mk(browser)
    page.goto(BASE + "/site/index.html")
    page.wait_for_selector(".book-card", timeout=8000)
    ids = page.evaluate("ARTICLES.map(a=>progressDocId('a@b.c', a.title))")
    check("reading-progress id differs for every book and per language", len(set(ids)) == len(ids) and all(("_%s_" % LANG) in i for i in ids), ids)
    allt = page.evaluate("ARTICLES.map(a=>[a.title,a.subtitle,a.category,a.content].join(' ')).join(' ')")
    bad = Q.scan_text(allt, LANG, en_caps)
    check("no leaks in the books (CJK, chatbot text, markdown, English leftovers)", not bad, bad[:3])
    print("  INFO style issues in the whole text: %d" % len(Q.soft_issues(Q.plain(allt), LANG)))
    emp = page.evaluate("document.getElementById('empty-state').textContent")
    check("empty-state text translated", "shelves are empty" not in emp and "source code" not in emp, emp[:60])
    ph = page.evaluate("document.getElementById('field-email').placeholder")
    check("email placeholder localised", ph != "you@example.com", ph)
    if LANG == "ar":
        check("Latin names isolated for right-to-left reading", page.evaluate("document.querySelectorAll('bdi').length") > 0)
    ctx.close()
    browser.close()

srv.shutdown()
print("\nLANGTEST [%s] RESULT: %s" % (LANG, "ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(0 if not fails else 1)
