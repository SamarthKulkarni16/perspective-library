#!/usr/bin/env python3
# CEO 2026-10-23: quality rules for the Perspective Library language builder.
# Imported by lang_build.py (validation, repair, post-fixes, cache re-check) and lang_test.py (site scan).
# usage: python3 pl_quality.py selftest      (offline, no model calls; exit 0 only if every check passes)
import os, re, sys, time, hashlib, html as H


def plain(s):
    return H.unescape(re.sub(r"<[^>]+>", "", s))


def has_letters(s):
    return re.search(r"[A-Za-z]", s) is not None


# ---------------------------------------------------------------- style text added to the model prompt
STYLE_EXTRA = {
    "hi": ("Address the reader as तुम in every sentence (तुम, तुम्हारा, तुम्हारी, तुम्हें, तुमने) and never use आप, आपका, तू or तेरा; "
           "use verb endings that match तुम (करते हो, जानते हो, करो, देखो). "
           "Write English loan words that people really say (brain, plan, energy, group) in Devanagari with one fixed spelling each. "
           "Translate idioms by meaning, not word by word (iron rod = लोहे की छड़). "
           "Check the particle ने and the gender of nouns (किताब, भावना, जलन are feminine) so every sentence is grammatical. "
           "Keep sentences short and conversational. "
           "Glossary: anger = गुस्सा, conflict = टकराव, procrastination = टालमटोल, survival = सर्वाइवल, jealousy = जलन, envy = ईर्ष्या, "
           "fear = डर, sadness = उदासी, want = चाहत, emotion = भावना, resources = संसाधन, brain = दिमाग, prefrontal cortex = प्रीफ्रंटल कॉर्टेक्स."),
    "ar": ("Use only clear, neutral Modern Standard Arabic (simple fusha). No Egyptian, Levantine or Gulf dialect words "
           "(never مش, دلوقتي, كتير, بدي, ليش, شو, هيك, كده). Address the reader in the masculine singular (أنت) consistently. "
           "Never drop a clause or the end of a sentence. "
           "Glossary: procrastination = التسويف, conflict = صراع (plural صراعات), problem = مشكلة, survival = البقاء, anger = الغضب, "
           "fear = الخوف, jealousy = الغيرة, envy = الحسد, sadness = الحزن, want = الرغبة, emotions = المشاعر, resources = الموارد. "
           "Keep the names from rule 3 in Latin letters."),
    "pt": ("Use Brazilian Portuguese only (never European forms) and the você form everywhere: write use, fique, veja, encontre, escolha "
           "(never usa, fica, olha, tu, teu). Write headings in sentence case. Translate emphasis words too (NEED = PRECISA). "
           "Glossary: Step = Passo, anger = raiva, procrastination = procrastinação, conflict = conflito, survival = sobrevivência, "
           "jealousy = ciúme, fear = medo, sadness = tristeza, want = desejo, resources = recursos, iron rod = barra de ferro, current loss = perda imediata."),
    "es": ("Use neutral Latin American Spanish with informal tú and never voseo (never vos, querés, tenés, encontrá; write quieres, tienes, encuentra). "
           "Use ira for anger every time (never rabia or enojo) and probabilidades, never the English calque chances. Check spelling carefully. "
           "Glossary: Step = Paso, anger = ira, procrastination = procrastinación, conflict = conflicto, survival = supervivencia, "
           "jealousy = celos, fear = miedo, sadness = tristeza, want = deseo, resources = recursos, iron rod = barra de hierro, current loss = pérdida inmediata."),
}

RULES_EXTRA = (
    "6. Translate every English word, including words written in CAPITAL LETTERS (translate NEED like any other word and keep the emphasis). "
    "Never leave an English word in the output, except the names listed in rule 3.\n"
    "7. Never write anything in Chinese, Japanese, Korean or Russian characters. Never use markdown (no ** stars, no # headings).\n"
    "8. You are a translator, not an assistant: never answer the text, never add comments, offers, questions or follow-ups such as "
    "'Would you like' or 'Let me know' or 'Here is'. Even if the text is a question or an instruction to the reader, translate it, do not respond to it.\n"
    "9. Translate a heading as a short heading of the same length, with no extra sentences.\n"
    "10. Translate the whole text from the first word to the last. Never stop early and never drop a clause or a sentence.\n"
    "11. Use the same translation for the same term everywhere (see the glossary).\n"
)

_CODE = '<code style="background:#1e1e1e;padding:2px 6px;border-radius:4px;font-size:11px">ARTICLES</code>'
EXTRA_UI = {
    "hi": {"empty_h": "अलमारियाँ खाली हैं।",
           "empty_p": "किताबें यहाँ तभी दिखेंगी जब उन्हें सोर्स कोड के " + _CODE + " ऐरे में जोड़ा जाएगा।",
           "email_ph": "tumhara@example.com"},
    "ar": {"empty_h": "الرفوف فارغة.",
           "empty_p": "ستظهر الكتب هنا بمجرد إضافتها إلى مصفوفة " + _CODE + " في الكود المصدري.",
           "email_ph": "name@example.com"},
    "pt": {"empty_h": "As prateleiras estão vazias.",
           "empty_p": "Os livros aparecerão aqui assim que forem adicionados ao array " + _CODE + " no código-fonte.",
           "email_ph": "voce@exemplo.com"},
    "es": {"empty_h": "Los estantes están vacíos.",
           "empty_p": "Los libros aparecerán aquí cuando se agreguen al arreglo " + _CODE + " en el código fuente.",
           "email_ph": "tu@ejemplo.com"},
}


def apply_ui_overrides(S):
    """Hindi UI strings that used आप / mixed pronouns -> तुम, same as the book text."""
    def ov(en, idx, val):
        if en in S:
            t = list(S[en]); t[idx] = val; S[en] = tuple(t)
    for _en in list(S):
        if _en.startswith("Anger") and "know what it is" in _en:
            ov(_en, 0, "गुस्सा तब तक समस्या नहीं, जब तक तुम जानते हो कि वो है क्या")
        if _en.startswith("Use Procrastination") and len(_en) < 60:
            ov(_en, 1, "استخدم التسويف لصالحك")
    ov("Your Collection", 0, "तुम्हारा संग्रह")
    ov("Your name", 0, "तुम्हारा नाम")
    ov("You don't need to escape problems. You need to upgrade them.", 0, "तुम्हें समस्याओं से भागना नहीं है। उन्हें अपग्रेड करना है।")


# ---------------------------------------------------------------- hard rules (reject the translation)
CJK_RE = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff]")
CHATBOT_RE = re.compile(r"(would you like|let me know|i can also|i'd be happy|i would be happy|feel free to|hope this helps|here is the|here's the|dive deeper|as an ai|translation:)", re.I)
CHATBOT_LANG = {
    "hi": re.compile("(क्या आप चाहेंगे|क्या तुम चाहोगे|मैं और विस्तार|यहाँ अनुवाद है)"),
    "ar": re.compile("(هل تريد أن|هل ترغب في|إليك الترجمة|هذه هي الترجمة)"),
    "pt": re.compile(r"(gostaria que|posso aprofundar|aqui est[áa] a tradu)", re.I),
    "es": re.compile(r"(¿te gustaría|puedo profundizar|aquí tienes la traducción|aquí está la traducción)", re.I),
}
ALLOWED_LATIN = {"samarth", "kulkarni", "perspective", "library", "instagram", "dm", "elais", "google", "iq", "ai", "lol", "haha", "tv", "html", "ok", "pdf"}
DEFAULT_EN_CAPS = {"NEED", "JEALOUSY", "ENVY", "AND", "ARE", "NOT", "BAD"}
MIN_RATIO = {"hi": 0.6, "ar": 0.5, "pt": 0.7, "es": 0.7}
END_SRC = set(".!?)}\"'\u201d\u2019")
END_OUT = set(".!?)}\"'\u201d\u2019\u2026\u0964\u061f\u00bb:;")


def _caps_tokens(s):
    return set(re.findall(r"\b[A-Z]{3,}\b", s)) - {"LOL", "HTML", "PDF"}


def caps_tokens(text):
    return _caps_tokens(plain(text))


def valid_extra(src, out, lang, kind="p"):
    """Extra checks on top of the old validator. kind: 'h' = heading/table cell, 'p' = paragraph/other text."""
    ps, po = plain(src), plain(out)
    if CJK_RE.search(po) and not CJK_RE.search(ps):
        return False, "contains Chinese/Japanese/Korean/Cyrillic characters"
    if CHATBOT_RE.search(po) or (lang in CHATBOT_LANG and CHATBOT_LANG[lang].search(po)):
        return False, "chatbot reply instead of a translation"
    if "**" in out and "**" not in src:
        return False, "markdown stars in the text"
    if re.search(r"(^|\n)\s{0,3}#{1,6}\s", out) and not re.search(r"(^|\n)\s{0,3}#{1,6}\s", src):
        return False, "markdown heading in the text"
    kept = sorted(w for w in _caps_tokens(ps) if re.search(r"(?<![A-Za-z])" + w + r"(?![A-Za-z])", po))
    if kept:
        return False, "English word kept in capitals: %s (translate it)" % kept[0]
    if lang in ("hi", "ar"):
        bad = [w for w in re.findall(r"[A-Za-z]{2,}", po) if w.lower() not in ALLOWED_LATIN]
        if bad:
            return False, "English word left in the text: %s (translate it)" % bad[0]
    n = len(ps)
    if kind == "h":
        if "\n" in po.strip():
            return False, "heading has several lines"
        if len(po) > max(60, 2.2 * n):
            return False, "heading too long"
        if re.search(r"(?<!\d)[.!?\u0964\u061f]\s+\S", po) and not re.search(r"(?<!\d)[.!?\u0964\u061f]\s+\S", ps):
            return False, "heading has several sentences"
    elif n >= 60:
        r = len(po) / max(1, n)
        if r < MIN_RATIO.get(lang, 0.6):
            return False, "too short, part of the text is missing (%.2f)" % r
        if r > 2.4:
            return False, "too long, extra text was added (%.2f)" % r
    if kind == "p" and n >= 40:
        e = ps.rstrip()[-1:]
        if e and e in END_SRC and po.rstrip()[-1:] not in END_OUT:
            return False, "tail missing, the last sentence is cut"
    return True, ""


# ---------------------------------------------------------------- soft rules (style; repaired, else accepted and reported)
HI_FORMAL = {"आप", "आपका", "आपकी", "आपके", "आपको", "आपने", "आपसे", "आपमें", "आपलोग", "आपकि"}
HI_TU = {"तू", "तेरा", "तेरी", "तेरे", "तुझे", "तुझसे", "तुझको", "तूने", "तुझमें"}
HI_TOKEN = re.compile("[\u0900-\u0963\u0966-\u097f]+")
AR_TOKEN = re.compile("[\u0600-\u06ff]+")
AR_DIALECT = {"عايز", "عاوز", "عايزة", "ده", "دي", "دا", "ايه", "إيه", "ايش", "إيش", "شو", "هلق", "هلأ", "كتير", "بدي", "بدك", "بده",
              "مش", "لسه", "لسا", "دلوقتي", "دلوقت", "كده", "كدا", "ازاي", "إزاي", "ليش", "ليه", "وين", "فين", "شلون", "شنو", "هيك",
              "هاد", "هاي", "اكتر", "أكتر", "برضه", "برضو", "عشان", "علشان", "بس", "زي", "كمان", "شوية", "شوي", "انو", "إنو"}
ES_VOS = re.compile(r"\b(vos|querés|tenés|sabés|podés|hacés|decís|encontrá|mirá|hacé|decí|fijate|andá|vení|poné|queres|encontra|chances)\b", re.I)
PT_TU = re.compile(r"\b(tu|teu|tua|teus|tuas|contigo|ti|tens|queres|podes|sabes|fazes|vais|estás)\b", re.I)


def soft_issues(out, lang):
    po = plain(out)
    res = []
    if lang == "hi":
        toks = set(HI_TOKEN.findall(po))
        f = sorted(toks & HI_FORMAL)
        if f:
            res.append("uses the formal pronoun %s; rewrite with tum forms (तुम, तुम्हारा, तुम्हें) and matching verb endings" % ", ".join(f))
        t = sorted(toks & HI_TU)
        if t:
            res.append("uses tu forms %s; use tum forms (तुम, तुम्हारा) instead" % ", ".join(t))
    elif lang == "ar":
        d = sorted(set(AR_TOKEN.findall(po)) & AR_DIALECT)
        if d:
            res.append("dialect words %s; use clear Modern Standard Arabic only" % ", ".join(d))
    elif lang == "es":
        m = ES_VOS.search(po)
        if m:
            res.append("voseo or the English calque '%s'; use informal tú forms and probabilidades" % m.group(0))
    elif lang == "pt":
        m = PT_TU.search(po)
        if m:
            res.append("tu form or European Portuguese '%s'; use você forms (Brazilian Portuguese)" % m.group(0))
    return res


# ---------------------------------------------------------------- deterministic post-fixes
_POST_RE = {
    "es": [(r"\bchances\b", "probabilidades"), (r"\bChances\b", "Probabilidades"),
           (r"\bPérdida actual\b", "Pérdida inmediata"), (r"\bpérdida actual\b", "pérdida inmediata"),
           (r"\bdel enojo\b", "de la ira"), (r"\bDel enojo\b", "De la ira"), (r"\bal enojo\b", "a la ira"),
           (r"\bel enojo\b", "la ira"), (r"\bEl enojo\b", "La ira"), (r"\bun enojo\b", "una ira"), (r"\bUn enojo\b", "Una ira"),
           (r"\beste enojo\b", "esta ira"), (r"\bese enojo\b", "esa ira"), (r"\bmucho enojo\b", "mucha ira"),
           (r"\benojo\b", "ira"), (r"\bEnojo\b", "Ira"),
           (r"\bla rabia\b", "la ira"), (r"\bLa rabia\b", "La ira"), (r"\buna rabia\b", "una ira"), (r"\bUna rabia\b", "Una ira"),
           (r"\brabia\b", "ira"), (r"\bRabia\b", "Ira")],
    "pt": [(r"\bEtapa(?=\s*\d)", "Passo")],
}
_POST_STR = {
    "ar": [("المماطأة", "التسويف"), ("المماطلة", "التسويف"), ("مماطلة", "تسويف"), ("مماطأة", "تسويف")],
}
_POST_COMPILED = {k: [(re.compile(a), b) for a, b in v] for k, v in _POST_RE.items()}


def postfix(out, lang, kind="p"):
    for rx, rep in _POST_COMPILED.get(lang, []):
        out = rx.sub(rep, out)
    for a, b in _POST_STR.get(lang, []):
        out = out.replace(a, b)
    if kind == "h":
        if lang == "pt":
            out = _sentence_case(out)
        if lang in ("pt", "es") and out[:1].islower():
            out = out[:1].upper() + out[1:]
        if lang == "hi":
            out = re.sub(r"^A\.\s", "ए. ", out)
            out = re.sub(r"^B\.\s", "बी. ", out)
        if lang == "ar":
            out = re.sub(r"^A\.\s", "\u0623. ", out)
            out = re.sub(r"^B\.\s", "\u0628. ", out)
    return out


# ---------------------------------------------------------------- right-to-left: isolate Latin names
LTR_NAMES = re.compile(r"(Samarth Kulkarni|Perspective Library|Instagram|Elais|\bDM\b)")


def wrap_ltr(html_s):
    parts = re.split(r"(<[^>]+>)", html_s)
    for i, p in enumerate(parts):
        if i % 2 == 0 and p:
            parts[i] = LTR_NAMES.sub(lambda m: '<bdi dir="ltr">' + m.group(1) + "</bdi>", p)
    return "".join(parts)


# ---------------------------------------------------------------- whole-text scan (used by lang_test.py and the review)
def scan_text(text, lang, en_caps=None):
    po = plain(text)
    res = []
    if CJK_RE.search(po):
        res.append("Chinese/Japanese/Korean/Cyrillic characters in the text")
    if CHATBOT_RE.search(po) or (lang in CHATBOT_LANG and CHATBOT_LANG[lang].search(po)):
        res.append("chatbot-style reply in the text")
    if "**" in po:
        res.append("markdown stars in the text")
    caps = DEFAULT_EN_CAPS if en_caps is None else en_caps
    kept = sorted(w for w in caps if re.search(r"(?<![A-Za-z])" + w + r"(?![A-Za-z])", po))
    if kept:
        res.append("English capitalised word kept: " + kept[0])
    if lang in ("hi", "ar"):
        bad = sorted({w for w in re.findall(r"[A-Za-z]{2,}", po) if w.lower() not in ALLOWED_LATIN})
        if bad:
            res.append("English words left: " + ", ".join(bad[:5]))
    return res


# ---------------------------------------------------------------- the translate step (replaces Engine.tr)
STATIC_H = {
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
    for tok in re.split(r"(\s+)", s):
        if not tok or tok.isspace():
            out.append(tok)
            continue
        core = tok.strip(".,:;!?()\"'")
        if keep or core in _NAMES or (tok.isupper() and len(core) > 1):
            out.append(tok)
        else:
            parts = tok.split("-")
            out.append("-".join([q[:1].lower() + q[1:] for q in parts]))
        keep = bool(re.fullmatch(r"(\d+|[A-Z])\.", tok)) or tok.endswith(":") or tok == "\u2014"
    return "".join(out)


def _repair(eng, core, text, issues, valid, is_html, kind):
    lang = eng.lang
    note = ("\nSPECIAL TASK (this overrides the instruction to translate): the user's text is ALREADY written in %s. "
            "Do not translate it again and do not shorten it. Fix only this problem and return the complete corrected text with the same HTML tags in the same order. "
            "Problem: %s. Output only the corrected text.") % (eng.info["name"], "; ".join(issues))
    best = None
    for t in (0.2, 0.4):
        try:
            o = eng.clean(eng.llm(text, t, note))
        except Exception as e:
            eng.last_err = "llm repair: " + str(e)[:100]
            continue
        o = postfix(o, lang, kind)
        ok, why = valid(core, o, lang, is_html, kind)
        if not ok:
            continue
        s = soft_issues(o, lang)
        if len(s) < len(issues) and (best is None or len(s) < len(best[1])):
            best = (o, s)
        if best is not None and not best[1]:
            break
    return best if best is not None else (None, None)


def tr_impl(eng, src, is_html, kind, valid):
    lang = eng.lang
    if not has_letters(plain(src)):
        return src
    lead = re.match(r"\s*", src).group()
    trail = re.search(r"\s*$", src).group()
    core = src.strip()
    if kind == "p" and not is_html and len(core) < 70 and "\n" not in core and not core.endswith("."):  # AUTO_H: short plain lines are headings
        kind = "h"
    if kind == "h":
        _sh = STATIC_H.get(core)
        if _sh and lang in _sh:
            return lead + _sh[lang] + trail
    k = hashlib.sha1((lang + "|" + ("h" if is_html else "t") + "|" + core).encode("utf-8")).hexdigest()[:20]
    reason = "not in the cache"
    ent = eng.cache.get(k)
    if ent is not None:
        fixed = postfix(ent["tr"], lang, kind)
        ok, why = valid(core, fixed, lang, False if ent.get("eng") == "google" else is_html, kind)
        if (not ok) and ent.get("eng") == "google" and why.startswith("lines"):
            ok = True
        sc = soft_issues(fixed, lang) if ok else []
        if ok and (ent.get("soft") or not sc):
            if fixed != ent["tr"]:
                ent["tr"] = fixed
                eng.stats["cache_fixed"] += 1
            eng.stats["cache"] += 1
            return lead + fixed + trail
        eng.stats["cache_rejected"] += 1
        if not ok:
            reason = why
            eng.stats["cache_rej_" + why.split()[0]] += 1
        else:
            reason = "style: " + sc[0][:60]
            eng.stats["cache_rej_style"] += 1
    if os.environ.get("PL_AUDIT") == "1":
        eng.stats["audit_redo"] += 1
        if not hasattr(eng, "audit"):
            eng.audit = []
        eng.audit.append({"kind": kind, "why": reason[:90], "src": core[:60]})
        return src

    out = None
    eng_name = None
    soft = []
    best = None
    note = ""
    if eng.key:
        for t in (0.2, 0.3, 0.4, 0.5, 0.6):
            try:
                o = eng.clean(eng.llm(core, t, note))
            except Exception as e:
                eng.last_err = "llm: " + str(e)[:120]
                time.sleep(4)
                continue
            o = postfix(o, lang, kind)
            ok, why = valid(core, o, lang, is_html, kind)
            if not ok:
                eng.stats["llm_reject_" + why.split()[0]] += 1
                note = "\nYour previous answer was rejected: %s. Translate again and fix exactly that problem. Output only the translation." % why
                continue
            sc = soft_issues(o, lang)
            if not sc:
                out, eng_name, soft = o, "llm", []
                break
            eng.stats["llm_style"] += 1
            note = "\nYour previous answer was rejected: %s. Translate again and fix exactly that problem. Output only the translation." % "; ".join(sc)
            if best is None or len(sc) < best[0]:
                best = (len(sc), o, sc)
    if out is None:
        cands = []
        g = eng.google(core, is_html)
        if g is not None:
            g = postfix(g, lang, kind)
            ok, why = valid(core, g, lang, False, kind)
            if ok or why.startswith("lines"):
                gs = soft_issues(g, lang)
                if not gs:
                    out, eng_name, soft = g, "google", []
                else:
                    cands.append((len(gs), 1, g, "google_soft", gs))
        if out is None and best is not None:
            cands.append((best[0], 0, best[1], "llm_soft", best[2]))
        if out is None and cands:
            cands.sort(key=lambda c: (c[0], c[1]))
            _n, _p, t0, e0, s0 = cands[0]
            if eng.key:
                rt, rs = _repair(eng, core, t0, s0, valid, is_html, kind)
                if rt is not None:
                    t0, s0, e0 = rt, rs, "llm_repaired"
                    eng.stats["repaired"] += 1
            out, eng_name, soft = t0, e0, s0
    if out is None:
        eng.failures.append(core[:80])
        eng.stats["FAILED"] += 1
        return src
    entry = {"tr": out, "eng": eng_name}
    if soft:
        entry["soft"] = True
        eng.soft.append({"src": core[:60], "eng": eng_name, "issues": soft})
    eng.cache[k] = entry
    eng.stats[eng_name] += 1
    eng.n += 1
    eng.save()
    if eng.n % 10 == 0:
        print("[%s] %d new blocks translated, stats=%s" % (lang, eng.n, dict(eng.stats)), flush=True)
    return lead + out + trail


# ---------------------------------------------------------------- offline self-test
def selftest():
    fails = []

    def chk(name, cond):
        print("  %s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            fails.append(name)

    SRC = "Anger is the emotion you get when you feel something is wrong. It doesn't matter if it is actually right or wrong."
    GOOD = {
        "pt": "A raiva é a emoção que você sente quando acha que algo está errado. Não importa se isso é realmente certo ou errado.",
        "es": "La ira es la emoción que sientes cuando crees que algo está mal. No importa si en realidad está bien o mal.",
        "hi": "गुस्सा वो भावना है जो तुम्हें तब आती है जब तुम्हें लगता है कि कुछ गलत हो रहा है। इससे फ़र्क नहीं पड़ता कि वो सच में सही है या गलत।",
        "ar": "الغضب هو الشعور الذي تحصل عليه عندما تشعر أن هناك شيئًا خاطئًا. لا يهم إن كان صحيحًا أم خاطئًا في الواقع.",
    }
    print("== good translations are accepted")
    for lang, g in GOOD.items():
        ok, why = valid_extra(SRC, g, lang, "p")
        chk("good %s accepted (%s)" % (lang, why), ok)
        chk("good %s has no style issue" % lang, not soft_issues(g, lang))
    chk("good heading pt", valid_extra("Survival", "Sobrevivência", "pt", "h")[0])
    chk("good heading hi", valid_extra("1. What is procrastination?", "1. टालमटोल क्या है?", "hi", "h")[0])
    NEEDSRC = "You can and <strong>NEED</strong> to leave the book now and start just observing."
    chk("emphasis word translated is accepted", valid_extra(NEEDSRC, "Você pode e <strong>PRECISA</strong> deixar o livro agora e começar só a observar.", "pt", "p")[0])

    print("== the real defects of the 10-21 review are rejected")
    chk("Chinese heading (es Want)", not valid_extra("Want", "想要这个东西", "es", "h")[0])
    chk("English chatbot reply as heading (pt Emotions)", not valid_extra("Emotions", "**Emoções** Would you like me to dive deeper?", "pt", "h")[0])
    chk("heading with several sentences", not valid_extra("Emotions", "Emoções. Posso explicar mais sobre cada emoção se quiser aprofundar.", "pt", "h")[0])
    chk("NEED left in English (pt)", not valid_extra(NEEDSRC, "Você pode e <strong>NEED</strong> deixar o livro agora e começar a observar.", "pt", "p")[0])
    chk("cut sentence (tail missing)", not valid_extra(SRC, "A raiva é a emoção que você sente quando acha que algo está errado. Não importa se isso é realmente certo ou", "pt", "p")[0])
    chk("English word inside Hindi", not valid_extra(SRC, GOOD["hi"].replace("भावना", "writing भावना"), "hi", "p")[0])
    chk("far too short", not valid_extra(SRC, "A raiva é a emoção.", "pt", "p")[0])

    print("== style problems are detected")
    chk("hi formal pronoun", bool(soft_issues("आप जानते हैं कि गुस्सा क्या है।", "hi")))
    chk("hi tu forms", bool(soft_issues("तेरा गुस्सा बड़ा है।", "hi")))
    chk("hi tum is clean", not soft_issues("तुम जानते हो कि गुस्सा क्या है।", "hi"))
    chk("es voseo", bool(soft_issues("Encontrá algo que querés hacer.", "es")))
    chk("pt tu form", bool(soft_issues("Tu podes usar a raiva.", "pt")))
    chk("ar dialect", bool(soft_issues("أنا عايز أفهم كده", "ar")))

    print("== deterministic fixes")
    chk("es chances -> probabilidades", postfix("Tus chances de éxito", "es") == "Tus probabilidades de éxito")
    chk("es rabia/enojo -> ira with gender", postfix("La rabia y el enojo", "es") == "La ira y la ira")
    chk("pt Etapa 2 -> Passo 2", postfix("Etapa 2 — Encontre algo", "pt") == "Passo 2 — Encontre algo")
    chk("ar procrastination term", postfix("بالمماطلة", "ar") == "بالتسويف")

    print("== right-to-left name isolation")
    w = wrap_ltr('<p>مرحبا Samarth Kulkarni <a href="https://instagram.com/Instagram">x</a></p>')
    chk("name wrapped in bdi, link untouched", '<bdi dir="ltr">Samarth Kulkarni</bdi>' in w and 'href="https://instagram.com/Instagram"' in w and w.count("<bdi") == 1)

    print("== whole-text scan")
    chk("scan finds Chinese", bool(scan_text("Hola 你好 mundo", "es")))
    chk("scan clean text", not scan_text("Hola mundo.", "es"))
    chk("scan finds NEED", bool(scan_text("Você pode NEED sair.", "pt")))
    chk("scan finds English in Hindi", bool(scan_text("गुस्सा writing है", "hi")))
    chk("scan allows names in Hindi", not scan_text("यह किताब Samarth Kulkarni ने लिखी है। Instagram पर DM करो।", "hi"))

    print("== patch 2: headings, fixed headings, term fixes")
    HD = "You Don't Get Out of Problems. You Upgrade Them."
    chk("two-sentence heading accepted when the source has two sentences", valid_extra(HD, "Você não sai dos problemas. Você faz upgrade neles.", "pt", "h")[0])
    chk("fixed heading exists for all four languages", all(l in STATIC_H[HD] for l in ("hi", "ar", "pt", "es")))
    chk("fixed headings pass their own rules", all(valid_extra(HD, STATIC_H[HD][l], l, "h")[0] for l in ("hi", "ar", "pt", "es")))
    chk("pt heading sentence case", postfix("A. Seu Córtex Pré-Frontal é Suprimido", "pt", "h") == "A. Seu córtex pré-frontal é suprimido")
    chk("pt numbered heading sentence case", postfix("1. O Que Acontece de Verdade Quando Você Fica Bravo?", "pt", "h") == "1. O que acontece de verdade quando você fica bravo?")
    chk("pt step heading keeps the capital after the dash", postfix("Passo 1 — Encontre Algo Para Procrastinar", "pt", "h") == "Passo 1 — Encontre algo para procrastinar")
    chk("es heading first letter capital", postfix("deseo", "es", "h") == "Deseo")
    chk("ar typo fixed", postfix("ابحث عن شيء لتسويبه", "ar") == "ابحث عن شيء لتسويفه")
    chk("ar A. list mark", postfix("A. القشرة", "ar", "h") == "\u0623. القشرة")
    chk("hi conflict term unified", postfix("कन्फ्लिक्ट्स क्या होते हैं?", "hi") == "टकराव क्या होते हैं?")

    print("== patch 3")
    chk("hi A. list mark", postfix("A. प्रीफ्रंटल कॉर्टेक्स", "hi", "h") == "ए. प्रीफ्रंटल कॉर्टेक्स")
    chk("ar B. list mark", postfix("B. اندفاع", "ar", "h") == "ب. اندفاع")

    print("\nSELFTEST RESULT: %s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    print(__doc__ or "usage: pl_quality.py selftest")
