#!/usr/bin/env python3
# CEO 2026-10-23 patch 2 for pl_quality.py (round 1 findings): 
#  1. the "heading has several sentences" rule must not reject a heading whose ENGLISH source already has two sentences (it blocked ar, pt, es)
#  2. fixed (hand-written) translations for the headings shared by the books, so the terms stay consistent (hi conflict/procrastination, Want, Jealousy / Envy ...)
#  3. deterministic fixes: Hindi spelling unification, Arabic typo and A./B. list marks, Portuguese sentence-case headings, first letter capital in headings
# usage: d23_pl_patch2.py SCRIPTS_DIR      exit 0 = patched (or already patched)
import sys, os, io

D = sys.argv[1]
p = os.path.join(D, "pl_quality.py")
t = io.open(p, encoding="utf-8").read()
if "STATIC_H" in t:
    print("pl_quality.py already patched (patch 2)")
    sys.exit(0)


def rep1(text, old, new):
    n = text.count(old)
    assert n == 1, "anchor found %d times (want 1): %r" % (n, old[:80])
    return text.replace(old, new)


# 1. heading rule
t = rep1(t, '        if re.search(r"(?<!\\d)[.!?\\u0964\\u061f]\\s+\\S", po):\n            return False, "heading has several sentences"',
         '        if re.search(r"(?<!\\d)[.!?\\u0964\\u061f]\\s+\\S", po) and not re.search(r"(?<!\\d)[.!?\\u0964\\u061f]\\s+\\S", ps):\n            return False, "heading has several sentences"')

# 2. fixed headings (before _repair)
static_h = '''STATIC_H = {
    "You Don't Get Out of Problems. You Upgrade Them.": {
        "hi": "समस्याओं से तुम बाहर नहीं निकलते। तुम उन्हें अपग्रेड करते हो।",
        "ar": "أنت لا تخرج من المشكلات. أنت ترقّيها.",
        "pt": "Você não sai dos problemas. Você faz upgrade neles.",
        "es": "No sales de los problemas. Los mejoras."},
    "Want": {"hi": "चाहत", "ar": "الرغبة", "pt": "Desejo", "es": "Deseo"},
    "Anger": {"hi": "गुस्सा", "ar": "الغضب", "pt": "Raiva", "es": "Ira"},
    "Fear": {"hi": "डर", "ar": "الخوف", "pt": "Medo", "es": "Miedo"},
    "Sadness": {"hi": "उदासी", "ar": "الحزن", "pt": "Tristeza", "es": "Tristeza"},
    "Jealousy / Envy": {"hi": "जलन / ईर्ष्या", "ar": "الغيرة / الحسد", "pt": "Ciúme / Inveja", "es": "Celos / Envidia"},
    "Emotions": {"hi": "भावनाएँ", "ar": "المشاعر", "pt": "Emoções", "es": "Emociones"},
    "What Are Conflicts?": {"hi": "टकराव क्या होते हैं?"},
    "Everything You Do Is Solving a Conflict": {"hi": "तुम जो कुछ भी करते हो, वो एक टकराव सुलझाना ही है"},
    "Why People Suffer From Things Like Relationship Issues and Mental Issues": {"hi": "लोग रिश्तों की परेशानियों और मानसिक समस्याओं जैसी चीज़ों से क्यों जूझते हैं"},
    "How To Use It — The Steps": {"hi": "इसका इस्तेमाल कैसे करें — स्टेप्स"},
    "Step 1 — Identify Your Current Conflicts": {"hi": "स्टेप 1 — अपने अभी के टकराव पहचानो"},
    "Step 2 — Sort Them": {"hi": "स्टेप 2 — उन्हें छाँटो"},
    "Step 3 — Substitute": {"hi": "स्टेप 3 — बदल दो"},
    "Step 1 — Find Something To Procrastinate": {"hi": "स्टेप 1 — टालने के लिए कुछ ढूँढो", "ar": "الخطوة 1 — ابحث عن شيء تريد تأجيله"},
    "1. What is procrastination?": {"hi": "1. टालमटोल क्या है?"},
    "2. Why does procrastination occur?": {"hi": "2. टालमटोल क्यों होती है?"},
}

_POST_STR["hi"] = [("कन्फ्लिक्ट्स", "टकराव"), ("कॉन्फ्लिक्ट्स", "टकराव"), ("कन्फ्लिक्ट", "टकराव"), ("कॉन्फ्लिक्ट", "टकराव"),
                   ("प्रोक्रास्टिनेशन", "टालमटोल"), ("करतें हों", "करते हो")]
_POST_STR["ar"] = _POST_STR["ar"] + [("لتسويبه", "لتسويفه")]
_NAMES = {"Samarth", "Kulkarni", "Elais", "Instagram", "Perspective", "Library", "DM"}


def _sentence_case(s):
    if "<" in s:
        return s
    out = []
    keep = True
    for tok in re.split(r"(\\s+)", s):
        if not tok or tok.isspace():
            out.append(tok)
            continue
        core = tok.strip(".,:;!?()\\"'")
        if keep or core in _NAMES or (tok.isupper() and len(core) > 1):
            out.append(tok)
        else:
            parts = tok.split("-")
            out.append("-".join([q[:1].lower() + q[1:] for q in parts]))
        keep = bool(re.fullmatch(r"(\\d+|[A-Z])\\.", tok)) or tok.endswith(":") or tok == "\\u2014"
    return "".join(out)


'''
t = rep1(t, "def _repair(eng, core, text, issues, valid, is_html, kind):", static_h + "def _repair(eng, core, text, issues, valid, is_html, kind):")

# 3. postfix gets the block kind
t = rep1(t, '''def postfix(out, lang):
    for rx, rep in _POST_COMPILED.get(lang, []):
        out = rx.sub(rep, out)
    for a, b in _POST_STR.get(lang, []):
        out = out.replace(a, b)
    return out''', '''def postfix(out, lang, kind="p"):
    for rx, rep in _POST_COMPILED.get(lang, []):
        out = rx.sub(rep, out)
    for a, b in _POST_STR.get(lang, []):
        out = out.replace(a, b)
    if kind == "h":
        if lang == "pt":
            out = _sentence_case(out)
        if lang in ("pt", "es") and out[:1].islower():
            out = out[:1].upper() + out[1:]
        if lang == "ar":
            out = re.sub(r"^A\\.\\s", "\\u0623. ", out)
            out = re.sub(r"^B\\.\\s", "\\u0628. ", out)
    return out''')
t = rep1(t, '        fixed = postfix(ent["tr"], lang)', '        fixed = postfix(ent["tr"], lang, kind)')
t = rep1(t, "\n            o = postfix(o, lang)\n", "\n            o = postfix(o, lang, kind)\n")
t = rep1(t, "\n        o = postfix(o, lang)\n", "\n        o = postfix(o, lang, kind)\n")
t = rep1(t, "            g = postfix(g, lang)", "            g = postfix(g, lang, kind)")
t = rep1(t, "    core = src.strip()\n    k = hashlib.sha1(",
         "    core = src.strip()\n    if kind == \"h\" and is_html:\n        _sh = STATIC_H.get(core)\n        if _sh and lang in _sh:\n            return lead + _sh[lang] + trail\n    k = hashlib.sha1(")

# selftest additions
tests = '''    print("== patch 2: headings, fixed headings, term fixes")
    HD = "You Don't Get Out of Problems. You Upgrade Them."
    chk("two-sentence heading accepted when the source has two sentences", valid_extra(HD, "Você não sai dos problemas. Você faz upgrade neles.", "pt", "h")[0])
    chk("fixed heading exists for all four languages", all(l in STATIC_H[HD] for l in ("hi", "ar", "pt", "es")))
    chk("fixed headings pass their own rules", all(valid_extra(HD, STATIC_H[HD][l], l, "h")[0] for l in ("hi", "ar", "pt", "es")))
    chk("pt heading sentence case", postfix("A. Seu Córtex Pré-Frontal é Suprimido", "pt", "h") == "A. Seu córtex pré-frontal é suprimido")
    chk("pt numbered heading sentence case", postfix("1. O Que Acontece de Verdade Quando Você Fica Bravo?", "pt", "h") == "1. O que acontece de verdade quando você fica bravo?")
    chk("pt step heading keeps the capital after the dash", postfix("Passo 1 — Encontre Algo Para Procrastinar", "pt", "h") == "Passo 1 — Encontre algo para procrastinar")
    chk("es heading first letter capital", postfix("deseo", "es", "h") == "Deseo")
    chk("ar typo fixed", postfix("ابحث عن شيء لتسويبه", "ar") == "ابحث عن شيء لتسويفه")
    chk("ar A. list mark", postfix("A. القشرة", "ar", "h") == "\\u0623. القشرة")
    chk("hi conflict term unified", postfix("कन्फ्लिक्ट्स क्या होते हैं?", "hi") == "टकराव क्या होते हैं?")
'''
t = rep1(t, '    print("\\nSELFTEST RESULT: %s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))',
         tests + '\n    print("\\nSELFTEST RESULT: %s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))')
compile(t, "pl_quality.py", "exec")
io.open(p, "w", encoding="utf-8").write(t)
print("pl_quality.py patched (patch 2)")
