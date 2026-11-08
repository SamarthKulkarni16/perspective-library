#!/usr/bin/env python3
# CEO 2026-10-23 patch 3 for pl_quality.py: the three cosmetic leftovers found in round 2.
#  1. the plain-text book (Anger) has its headings as short plain lines: treat short plain lines without a final full stop as headings
#     (-> Portuguese sentence case, Arabic A./B. -> أ./ب., fixed headings apply)
#  2. Hindi A./B. list marks -> ए./बी.
#  3. static UI strings: Hindi Anger subtitle used आप (-> तुम); Arabic Procrastination title used المماطلة (-> التسويف like the body)
# usage: d23_pl_patch3.py SCRIPTS_DIR
import sys, os, io

D = sys.argv[1]
p = os.path.join(D, "pl_quality.py")
t = io.open(p, encoding="utf-8").read()
if "AUTO_H" in t:
    print("pl_quality.py already patched (patch 3)")
    sys.exit(0)


def rep1(text, old, new):
    n = text.count(old)
    assert n == 1, "anchor found %d times (want 1): %r" % (n, old[:80])
    return text.replace(old, new)


t = rep1(t, '    if kind == "h" and is_html:\n        _sh = STATIC_H.get(core)',
         '    if kind == "p" and not is_html and len(core) < 70 and "\\n" not in core and not core.endswith("."):  # AUTO_H: short plain lines are headings\n'
         '        kind = "h"\n'
         '    if kind == "h":\n        _sh = STATIC_H.get(core)')
t = rep1(t, '        if lang == "ar":\n            out = re.sub(',
         '        if lang == "hi":\n'
         '            out = re.sub(r"^A\\.\\s", "ए. ", out)\n'
         '            out = re.sub(r"^B\\.\\s", "बी. ", out)\n'
         '        if lang == "ar":\n            out = re.sub(')
t = rep1(t, '    ov("Your Collection", 0, "तुम्हारा संग्रह")\n',
         '    for _en in list(S):\n'
         '        if _en.startswith("Anger") and "know what it is" in _en:\n'
         '            ov(_en, 0, "गुस्सा तब तक समस्या नहीं, जब तक तुम जानते हो कि वो है क्या")\n'
         '        if _en.startswith("Use Procrastination") and len(_en) < 60:\n'
         '            ov(_en, 1, "استخدم التسويف لصالحك")\n'
         '    ov("Your Collection", 0, "तुम्हारा संग्रह")\n')
tests = '''    print("== patch 3")
    chk("hi A. list mark", postfix("A. प्रीफ्रंटल कॉर्टेक्स", "hi", "h") == "ए. प्रीफ्रंटल कॉर्टेक्स")
    chk("ar B. list mark", postfix("B. اندفاع", "ar", "h") == "ب. اندفاع")
'''
t = rep1(t, '    print("\\nSELFTEST RESULT: %s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))',
         tests + '\n    print("\\nSELFTEST RESULT: %s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))')
compile(t, "pl_quality.py", "exec")
io.open(p, "w", encoding="utf-8").write(t)
print("pl_quality.py patched (patch 3)")
