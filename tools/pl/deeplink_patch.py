#!/usr/bin/env python3
# CEO 2026-10-18: Perspective Library step 1 - every book gets its own URL (#book/<slug>) with NO UI change.
# usage: deeplink_patch.py <in.html> <out.html>
import sys


def rep(s, old, new, count=1):
    assert s.count(old) == count, ("expected %d occurrence(s), found %d" % (count, s.count(old)), old[:80])
    return s.replace(old, new)


HELPERS = '''
// ─── Deep links: every book has its own URL (#book/<slug>) — UI unchanged ────
// Example: https://samarthkulkarni16.github.io/perspective-library/#book/survival
// Query strings (utm_*) are kept. Old links (#survival, #how-to-use-anger-to-your-advantage) still open the book.
function slugOf(a) { return a.slug || legacySlugOf(a); }
function legacySlugOf(a) { return String(a.title).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }
function colorFor(a) { return a.color || DEFAULT_COLORS[ARTICLES.indexOf(a) % DEFAULT_COLORS.length]; }
function findBookByHash() {
  let key = '';
  try { key = decodeURIComponent(location.hash || ''); } catch (e) { key = location.hash || ''; }
  key = key.replace(/^#/, '').replace(/^book\\//, '').toLowerCase();
  if (!key) return null;
  return ARTICLES.find(a => slugOf(a) === key || legacySlugOf(a) === key) || null;
}
function openFromHash() {
  const a = findBookByHash();
  const isOpen = modalOverlay.classList.contains('open');
  if (a) {
    if (isOpen && currentBookTitle === a.title) return;
    if (isOpen) closeModal(true);
    window.scrollTo(0, 0);
    openModal(a, colorFor(a), true);
  } else if (isOpen) {
    closeModal(true);
  }
}
window.addEventListener('hashchange', () => { if (currentUser) openFromHash(); });
'''


def patch(h):
    # 1) a stable slug for each book
    for title, slug in [
        ("How To Use Anger To Your Advantage", "anger"),
        ("Use Procrastination To Your Advantage", "procrastination"),
        ("Use Conflicts To Your Advantage", "conflicts"),
        ("Survival", "survival"),
    ]:
        h = rep(h, '    title: "%s",\n' % title, '    slug: "%s",\n    title: "%s",\n' % (slug, title))
    # 2) search-engine data points at the new per-book URLs
    for old, new in [
        ("#how-to-use-anger-to-your-advantage", "#book/anger"),
        ("#use-procrastination-to-your-advantage", "#book/procrastination"),
        ("#use-conflicts-to-your-advantage", "#book/conflicts"),
        ('perspective-library/#survival"', 'perspective-library/#book/survival"'),
    ]:
        h = rep(h, old, new)
    # 3) after sign-in, open the book named in the URL
    h = rep(h, "  renderBooks();\n}\n\n// ─── Google sign-in", "  renderBooks();\n  openFromHash();\n}\n\n// ─── Google sign-in")
    # 4) opening a book puts it in the URL
    h = rep(h,
            "async function openModal(article, color) {\n  currentBookTitle = article.title;\n  isCompleted      = false;\n",
            "async function openModal(article, color, fromUrl) {\n  currentBookTitle = article.title;\n  isCompleted      = false;\n"
            "  if (!fromUrl) {\n    const want = '#book/' + slugOf(article);\n"
            "    if (location.hash !== want) history.pushState({ book: slugOf(article) }, '', location.pathname + location.search + want);\n  }\n")
    # 5) closing a book takes it out of the URL
    h = rep(h,
            "function closeModal() {\n  modalOverlay.classList.remove('open');\n",
            "function closeModal(fromUrl) {\n  const wasOpen = modalOverlay.classList.contains('open');\n  modalOverlay.classList.remove('open');\n")
    h = rep(h,
            "  if (saveDebounce) {\n    clearTimeout(saveDebounce);\n    saveDebounce = null;\n  }\n}\n\nmodalClose.addEventListener('click', closeModal);",
            "  if (saveDebounce) {\n    clearTimeout(saveDebounce);\n    saveDebounce = null;\n  }\n"
            "  // deep link: take the book out of the URL (no scroll, no reload)\n"
            "  if (wasOpen && !fromUrl && findBookByHash()) {\n"
            "    if (history.state && history.state.book) history.back();\n"
            "    else history.replaceState(null, '', location.pathname + location.search);\n  }\n}\n\n"
            "modalClose.addEventListener('click', () => closeModal());")
    # 6) helpers + back/forward handling
    h = rep(h,
            "document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });",
            "document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });\n" + HELPERS)
    return h


if __name__ == "__main__":
    src = open(sys.argv[1], encoding="utf-8").read()
    out = patch(src)
    open(sys.argv[2], "w", encoding="utf-8").write(out)
    print("patched OK: %d -> %d bytes" % (len(src.encode("utf-8")), len(out.encode("utf-8"))))
