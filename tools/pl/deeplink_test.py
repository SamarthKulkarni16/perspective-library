#!/usr/bin/env python3
# CEO 2026-10-18: headless-browser proof for the Perspective Library deep links.
# usage: deeplink_test.py <dir containing orig.html and index.html>   (exit 0 only if every test passes)
import sys, os, threading, http.server, socketserver, functools, time
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops

D = sys.argv[1]
PORT = 8099
BASE = "http://127.0.0.1:%d" % PORT

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
srv = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=D))
threading.Thread(target=srv.serve_forever, daemon=True).start()

fails = []


def check(name, cond, extra=""):
    print("  %s %s %s" % ("PASS" if cond else "FAIL", name, extra))
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


def is_open(page):
    return page.evaluate("document.getElementById('modal-overlay').classList.contains('open')")


def wait_open(page):
    page.wait_for_selector("#modal-overlay.open", timeout=5000)


def wait_closed(page):
    page.wait_for_function("!document.getElementById('modal-overlay').classList.contains('open')", timeout=5000)


def h(page):
    return page.evaluate("location.hash")


with sync_playwright() as p:
    try:
        browser = p.chromium.launch(headless=True)
    except Exception as e:
        print("default chromium failed (%s), trying system chrome" % str(e)[:100])
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome-stable")

    print("== 1. UI is pixel-identical before and after the patch")
    shots = {}
    for tag in ("orig", "index"):
        ctx, page, errs = mk(browser)
        page.goto("%s/%s.html" % (BASE, tag))
        page.wait_for_selector(".book-card", timeout=8000)
        time.sleep(0.6)
        page.screenshot(path="/tmp/pl_%s_shelf.png" % tag)
        page.click(".book-card >> nth=0")
        wait_open(page)
        time.sleep(0.7)
        page.screenshot(path="/tmp/pl_%s_modal.png" % tag)
        shots[tag] = (errs, page.title())
        ctx.close()
    for what in ("shelf", "modal"):
        a = Image.open("/tmp/pl_orig_%s.png" % what).convert("RGB")
        b = Image.open("/tmp/pl_index_%s.png" % what).convert("RGB")
        diff = ImageChops.difference(a, b).getbbox()
        check("screenshot of %s identical" % what, diff is None, "" if diff is None else "differs in %s" % (diff,))
    check("page title unchanged", shots["orig"][1] == shots["index"][1], shots["index"][1][:50])
    check("no JavaScript errors on the patched page", len(shots["index"][0]) == 0, str(shots["index"][0])[:200])

    print("== 2. deep link opens the right book")
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html#book/survival" % BASE)
    wait_open(page)
    check("#book/survival opens Survival", page.inner_text("#modal-title") == "Survival", page.inner_text("#modal-title"))
    page.click("#modal-close")
    wait_closed(page)
    page.wait_for_function("location.hash === ''", timeout=3000)
    check("closing removes the book from the URL (page loaded directly)", h(page) == "", repr(h(page)))
    ctx.close()

    print("== 3. clicking a book sets the URL, X / Back / Forward behave")
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html" % BASE)
    page.wait_for_selector(".book-card", timeout=8000)
    page.click(".book-card >> nth=0")
    wait_open(page)
    check("clicking card 1 sets #book/anger", h(page) == "#book/anger", h(page))
    page.click("#modal-close")
    wait_closed(page)
    page.wait_for_function("location.hash === ''", timeout=3000)
    check("X closes and clears the URL", h(page) == "", repr(h(page)))
    page.click(".book-card >> nth=1")
    wait_open(page)
    check("card 2 sets #book/procrastination", h(page) == "#book/procrastination", h(page))
    page.go_back()
    wait_closed(page)
    page.wait_for_function("location.hash === ''", timeout=3000)
    check("browser Back closes the book", not is_open(page) and h(page) == "", repr(h(page)))
    page.go_forward()
    wait_open(page)
    check("browser Forward reopens it", page.inner_text("#modal-title") == "Use Procrastination To Your Advantage", page.inner_text("#modal-title")[:40])
    page.keyboard.press("Escape")
    wait_closed(page)
    check("Escape closes the book", not is_open(page))
    ctx.close()

    print("== 4. old links, unknown links, UTM tags")
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html#how-to-use-anger-to-your-advantage" % BASE)
    wait_open(page)
    check("old long link opens Anger", page.inner_text("#modal-title") == "How To Use Anger To Your Advantage")
    check("page is at the top (no jump to the SEO text)", page.evaluate("window.scrollY") == 0, str(page.evaluate("window.scrollY")))
    ctx.close()
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html#survival" % BASE)
    wait_open(page)
    check("old short link #survival opens Survival", page.inner_text("#modal-title") == "Survival")
    check("page is at the top for #survival too", page.evaluate("window.scrollY") == 0, str(page.evaluate("window.scrollY")))
    ctx.close()
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html#book/nope" % BASE)
    page.wait_for_selector(".book-card", timeout=8000)
    time.sleep(0.4)
    check("unknown book id: nothing opens, shelf shown", not is_open(page) and page.locator(".book-card").count() == 4)
    ctx.close()
    ctx, page, errs = mk(browser)
    page.goto("%s/index.html?utm_source=youtube&utm_medium=video&utm_campaign=survival#book/survival" % BASE)
    wait_open(page)
    page.click("#modal-close")
    wait_closed(page)
    time.sleep(0.4)
    q = page.evaluate("location.search")
    check("UTM tags survive open and close", q == "?utm_source=youtube&utm_medium=video&utm_campaign=survival", q)
    page.click(".book-card >> nth=2")
    wait_open(page)
    q2 = page.evaluate("location.search + location.hash")
    check("UTM tags survive clicking a card", q2 == "?utm_source=youtube&utm_medium=video&utm_campaign=survival#book/conflicts", q2)
    ctx.close()

    print("== 5. visitor not signed in: sign-in first, then the book opens")
    ctx, page, errs = mk(browser, user=False)
    page.goto("%s/index.html#book/survival" % BASE)
    page.wait_for_selector("#auth-screen", state="visible", timeout=8000)
    time.sleep(0.4)
    check("sign-in screen shown, no book yet", not is_open(page))
    check("link kept while signing in", h(page) == "#book/survival", h(page))
    page.evaluate("window.__authCb({email:'t@example.com', displayName:'Tester', photoURL:null})")
    wait_open(page)
    check("after sign-in the book opens", page.inner_text("#modal-title") == "Survival")
    ctx.close()
    browser.close()

srv.shutdown()
print("\nDEEPLINK RESULT:", "ALL PASS" if not fails else "FAILED: %s" % fails)
sys.exit(0 if not fails else 1)
