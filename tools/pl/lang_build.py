#!/usr/bin/env python3
# CEO 2026-10-20: Perspective Library language-site builder (steps 2 and 3 of the multilingual library plan).
# usage: lang_build.py ORIG_DIR LANG OUT_DIR CACHE_DIR
#   ORIG_DIR = the live original files (index.html, logo.jpeg, robots.txt, sitemap.xml)
#   writes OUT_DIR/index.html + assets + BUILD_REPORT.json
# exit 0 = complete page, 3 = page built but some text stayed English (listed in the report), 2 = could not build
# Same UI/colours/theme: only the language changes (plus fonts for Hindi/Arabic and right-to-left for Arabic).
# Translation cache: CACHE_DIR/<lang>.json keyed by sha1 of the English block, so only new or changed text is translated.
import sys, os, re, json, html as H, hashlib, subprocess, time, shutil, urllib.request, urllib.parse, urllib.error
from collections import Counter

ORIG_BASE = "https://samarthkulkarni16.github.io/perspective-library/"
def site_base(l): return "https://samarthkulkarni16.github.io/perspective-library-%s/" % l
OMNI_URL = os.environ.get("PL_URL", "http://localhost:20128/v1/chat/completions")
MODEL = os.environ.get("PL_MODEL", "samarth-free-chain")
LANGS = ["hi", "ar", "pt", "es"]
IDX = {"hi": 0, "ar": 1, "pt": 2, "es": 3}

LANGINFO = {
    "hi": {"name": "Hindi (Devanagari script)", "script": "\u0900-\u097F", "rtl": False,
           "style": "Write natural, casual, everyday spoken Hindi, the way a friend talks. Do NOT use formal, Sanskritised (shuddh) Hindi. Common English loan words people really use (phone, video, brain, plan, energy, group) are fine in Devanagari."},
    "ar": {"name": "Arabic", "script": "\u0600-\u06FF", "rtl": True,
           "style": "Write simple, clear, friendly modern standard Arabic that reads naturally, not stiff classical Arabic."},
    "pt": {"name": "Brazilian Portuguese", "script": None, "rtl": False,
           "style": "Use informal Brazilian Portuguese with 'voc\u00ea', friendly and natural."},
    "es": {"name": "Latin American Spanish", "script": None, "rtl": False,
           "style": "Use neutral Latin American Spanish with informal 't\u00fa', friendly and natural."},
}

SYS = ("You are a professional book translator working for the author Samarth Kulkarni. Translate the user's text from English to {name}. {style}\n"
       "Rules:\n"
       "1. Output ONLY the translation. No notes, no quotes around it, no markdown fences, no explanation.\n"
       "2. If the text contains HTML tags, keep every tag exactly as in the source (same tags, same order, same attributes) and translate only the text between them.\n"
       "3. Keep these untranslated, in Latin letters: Samarth Kulkarni, Perspective Library, Instagram, DM, Elais.\n"
       "4. Keep numbers, symbols, emoji, line breaks and blanks like _______ exactly as they are.\n"
       "5. Keep the author's voice: casual, personal, a little humorous. Keep the same meaning; do not summarise, add or remove anything.\n")

EN_STOP = set("the and you is are to of that it in for with this your what when was have not but they will can from there their been which would about".split())

# ---- static UI strings (hand written, order: hi, ar, pt, es) ---------------------------------------------
S = {}
def add(en, hi, ar, pt, es): S[en] = (hi, ar, pt, es)
TITLE = "Perspective Library \u2014 Free Books on Psychology, Emotions & Mindset"
add(TITLE, "Perspective Library \u2014 \u092e\u0928\u094b\u0935\u093f\u091c\u094d\u091e\u093e\u0928, \u092d\u093e\u0935\u0928\u093e\u0913\u0902 \u0914\u0930 \u0938\u094b\u091a \u092a\u0930 \u092e\u0941\u092b\u093c\u094d\u0924 \u0915\u093f\u0924\u093e\u092c\u0947\u0902",
    "Perspective Library \u2014 \u0643\u062a\u0628 \u0645\u062c\u0627\u0646\u064a\u0629 \u0639\u0646 \u0639\u0644\u0645 \u0627\u0644\u0646\u0641\u0633 \u0648\u0627\u0644\u0645\u0634\u0627\u0639\u0631 \u0648\u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u062a\u0641\u0643\u064a\u0631",
    "Perspective Library \u2014 Livros gratuitos sobre psicologia, emo\u00e7\u00f5es e mentalidade",
    "Perspective Library \u2014 Libros gratis sobre psicolog\u00eda, emociones y mentalidad")
add("A private reading room.", "\u090f\u0915 \u0928\u093f\u091c\u0940 \u092a\u0922\u093c\u0928\u0947 \u0915\u093e \u0915\u092e\u0930\u093e\u0964", "\u063a\u0631\u0641\u0629 \u0642\u0631\u0627\u0621\u0629 \u062e\u0627\u0635\u0629.", "Uma sala de leitura privada.", "Una sala de lectura privada.")
add("Continue with Google", "Google \u0938\u0947 \u091c\u093e\u0930\u0940 \u0930\u0916\u0947\u0902", "\u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 Google", "Continuar com o Google", "Continuar con Google")
add("or", "\u092f\u093e", "\u0623\u0648", "ou", "o")
add("Name", "\u0928\u093e\u092e", "\u0627\u0644\u0627\u0633\u0645", "Nome", "Nombre")
add("Email", "\u0908\u092e\u0947\u0932", "\u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a", "E-mail", "Correo electr\u00f3nico")
add("Password", "\u092a\u093e\u0938\u0935\u0930\u094d\u0921", "\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631", "Senha", "Contrase\u00f1a")
add("Your name", "\u0906\u092a\u0915\u093e \u0928\u093e\u092e", "\u0627\u0633\u0645\u0643", "Seu nome", "Tu nombre")
add("Enter Library", "\u0932\u093e\u0907\u092c\u094d\u0930\u0947\u0930\u0940 \u092e\u0947\u0902 \u091c\u093e\u090f\u0901", "\u0627\u062f\u062e\u0644 \u0627\u0644\u0645\u0643\u062a\u0628\u0629", "Entrar na biblioteca", "Entrar a la biblioteca")
add("Entering\u2026", "\u092a\u094d\u0930\u0935\u0947\u0936 \u0939\u094b \u0930\u0939\u093e \u0939\u0948\u2026", "\u062c\u0627\u0631\u064d \u0627\u0644\u062f\u062e\u0648\u0644\u2026", "Entrando\u2026", "Entrando\u2026")
add("Sign out", "\u0938\u093e\u0907\u0928 \u0906\u0909\u091f", "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062e\u0631\u0648\u062c", "Sair", "Cerrar sesi\u00f3n")
add("Your Collection", "\u0906\u092a\u0915\u093e \u0938\u0902\u0917\u094d\u0930\u0939", "\u0645\u062c\u0645\u0648\u0639\u062a\u0643", "Sua cole\u00e7\u00e3o", "Tu colecci\u00f3n")
add("The Library", "\u0932\u093e\u0907\u092c\u094d\u0930\u0947\u0930\u0940", "\u0627\u0644\u0645\u0643\u062a\u0628\u0629", "A biblioteca", "La biblioteca")
add("0% completed", "0% \u092a\u0942\u0930\u093e", "0% \u0645\u0643\u062a\u0645\u0644", "0% conclu\u00eddo", "0% completado")
add("% completed", "% \u092a\u0942\u0930\u093e", "% \u0645\u0643\u062a\u0645\u0644", "% conclu\u00eddo", "% completado")
add("Completed \u2713", "\u092a\u0942\u0930\u093e \u0939\u0941\u0906 \u2713", "\u062a\u0645\u0651 \u2713", "Conclu\u00eddo \u2713", "Completado \u2713")
add("{n} min read", "{n} \u092e\u093f\u0928\u091f \u092a\u0922\u093c\u0928\u0947 \u092e\u0947\u0902", "{n} \u062f\u0642\u0627\u0626\u0642 \u0644\u0644\u0642\u0631\u0627\u0621\u0629", "{n} min de leitura", "{n} min de lectura")
add("Reader", "\u092a\u093e\u0920\u0915", "\u0642\u0627\u0631\u0626", "Leitor", "Lector")
add("Book content coming soon.", "\u0915\u093f\u0924\u093e\u092c \u091c\u0932\u094d\u0926 \u0906 \u0930\u0939\u0940 \u0939\u0948\u0964", "\u0645\u062d\u062a\u0648\u0649 \u0627\u0644\u0643\u062a\u0627\u0628 \u0642\u0631\u064a\u0628\u064b\u0627.", "Conte\u00fado do livro em breve.", "Contenido del libro pr\u00f3ximamente.")
add("Please enter a valid email address.", "\u0915\u0943\u092a\u092f\u093e \u0938\u0939\u0940 \u0908\u092e\u0947\u0932 \u092a\u0924\u093e \u0921\u093e\u0932\u0947\u0902\u0964", "\u064a\u0631\u062c\u0649 \u0625\u062f\u062e\u0627\u0644 \u0628\u0631\u064a\u062f \u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a \u0635\u0627\u0644\u062d.", "Digite um e-mail v\u00e1lido.", "Ingresa un correo electr\u00f3nico v\u00e1lido.")
add("This account has been disabled.", "\u092f\u0939 \u0905\u0915\u093e\u0909\u0902\u091f \u092c\u0902\u0926 \u0915\u0930 \u0926\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964", "\u062a\u0645 \u062a\u0639\u0637\u064a\u0644 \u0647\u0630\u0627 \u0627\u0644\u062d\u0633\u0627\u0628.", "Esta conta foi desativada.", "Esta cuenta ha sido deshabilitada.")
add("No account found. Check your email or sign up.", "\u0915\u094b\u0908 \u0905\u0915\u093e\u0909\u0902\u091f \u0928\u0939\u0940\u0902 \u092e\u093f\u0932\u093e\u0964 \u0905\u092a\u0928\u093e \u0908\u092e\u0947\u0932 \u091c\u093e\u0901\u091a\u0947\u0902 \u092f\u093e \u0938\u093e\u0907\u0928 \u0905\u092a \u0915\u0930\u0947\u0902\u0964", "\u0644\u0645 \u064a\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u062d\u0633\u0627\u0628. \u062a\u062d\u0642\u0642 \u0645\u0646 \u0628\u0631\u064a\u062f\u0643 \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a \u0623\u0648 \u0623\u0646\u0634\u0626 \u062d\u0633\u0627\u0628\u064b\u0627.", "Nenhuma conta encontrada. Confira seu e-mail ou cadastre-se.", "No se encontr\u00f3 ninguna cuenta. Revisa tu correo o reg\u00edstrate.")
add("Incorrect password.", "\u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0917\u0932\u0924 \u0939\u0948\u0964", "\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631 \u063a\u064a\u0631 \u0635\u062d\u064a\u062d\u0629.", "Senha incorreta.", "Contrase\u00f1a incorrecta.")
add("An account with this email already exists.", "\u0907\u0938 \u0908\u092e\u0947\u0932 \u0938\u0947 \u092a\u0939\u0932\u0947 \u0938\u0947 \u090f\u0915 \u0905\u0915\u093e\u0909\u0902\u091f \u092e\u094c\u091c\u0942\u0926 \u0939\u0948\u0964", "\u064a\u0648\u062c\u062f \u062d\u0633\u0627\u0628 \u0628\u0647\u0630\u0627 \u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a \u0628\u0627\u0644\u0641\u0639\u0644.", "J\u00e1 existe uma conta com este e-mail.", "Ya existe una cuenta con este correo.")
add("Password must be at least 6 characters.", "\u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0915\u092e \u0938\u0947 \u0915\u092e 6 \u0905\u0915\u094d\u0937\u0930\u094b\u0902 \u0915\u093e \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f\u0964", "\u064a\u062c\u0628 \u0623\u0644\u0627 \u062a\u0642\u0644 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631 \u0639\u0646 6 \u0623\u062d\u0631\u0641.", "A senha deve ter pelo menos 6 caracteres.", "La contrase\u00f1a debe tener al menos 6 caracteres.")
add("Google sign-in was cancelled.", "Google \u0938\u093e\u0907\u0928-\u0907\u0928 \u0930\u0926\u094d\u0926 \u0915\u0930 \u0926\u093f\u092f\u093e \u0917\u092f\u093e\u0964", "\u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644 \u0639\u0628\u0631 Google.", "O login com o Google foi cancelado.", "Se cancel\u00f3 el inicio de sesi\u00f3n con Google.")
add("Network error. Check your connection.", "\u0928\u0947\u091f\u0935\u0930\u094d\u0915 \u092e\u0947\u0902 \u0926\u093f\u0915\u094d\u0915\u0924 \u0939\u0948\u0964 \u0905\u092a\u0928\u093e \u0915\u0928\u0947\u0915\u094d\u0936\u0928 \u091c\u093e\u0901\u091a\u0947\u0902\u0964", "\u062e\u0637\u0623 \u0641\u064a \u0627\u0644\u0634\u0628\u0643\u0629. \u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u062a\u0635\u0627\u0644\u0643.", "Erro de rede. Verifique sua conex\u00e3o.", "Error de red. Revisa tu conexi\u00f3n.")
add("Incorrect email or password.", "\u0908\u092e\u0947\u0932 \u092f\u093e \u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0917\u0932\u0924 \u0939\u0948\u0964", "\u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a \u0623\u0648 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631 \u063a\u064a\u0631 \u0635\u062d\u064a\u062d\u0629.", "E-mail ou senha incorretos.", "Correo o contrase\u00f1a incorrectos.")
add("Too many attempts. Try again later.", "\u092c\u0939\u0941\u0924 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u0915\u094b\u0936\u093f\u0936\u0947\u0902 \u0939\u094b \u0917\u0908\u0902\u0964 \u092c\u093e\u0926 \u092e\u0947\u0902 \u092b\u093f\u0930 \u0915\u094b\u0936\u093f\u0936 \u0915\u0930\u0947\u0902\u0964", "\u0645\u062d\u0627\u0648\u0644\u0627\u062a \u0643\u062b\u064a\u0631\u0629 \u062c\u062f\u064b\u0627. \u062d\u0627\u0648\u0644 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649 \u0644\u0627\u062d\u0642\u064b\u0627.", "Muitas tentativas. Tente novamente mais tarde.", "Demasiados intentos. Int\u00e9ntalo de nuevo m\u00e1s tarde.")
add("Something went wrong. Please try again.", "\u0915\u0941\u091b \u0917\u0921\u093c\u092c\u0921\u093c \u0939\u094b \u0917\u0908\u0964 \u0915\u0943\u092a\u092f\u093e \u092b\u093f\u0930 \u0938\u0947 \u0915\u094b\u0936\u093f\u0936 \u0915\u0930\u0947\u0902\u0964", "\u062d\u062f\u062b \u062e\u0637\u0623 \u0645\u0627. \u064a\u0631\u062c\u0649 \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.", "Algo deu errado. Tente novamente.", "Algo sali\u00f3 mal. Int\u00e9ntalo de nuevo.")
add("Emotions", "\u092d\u093e\u0935\u0928\u093e\u090f\u0901", "\u0627\u0644\u0645\u0634\u0627\u0639\u0631", "Emo\u00e7\u00f5es", "Emociones")
add("Productivity", "\u0909\u0924\u094d\u092a\u093e\u0926\u0915\u0924\u093e", "\u0627\u0644\u0625\u0646\u062a\u0627\u062c\u064a\u0629", "Produtividade", "Productividad")
add("Mindset", "\u0938\u094b\u091a", "\u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u062a\u0641\u0643\u064a\u0631", "Mentalidade", "Mentalidad")
add("Psychology", "\u092e\u0928\u094b\u0935\u093f\u091c\u094d\u091e\u093e\u0928", "\u0639\u0644\u0645 \u0627\u0644\u0646\u0641\u0633", "Psicologia", "Psicolog\u00eda")
add("How To Use Anger To Your Advantage", "\u0917\u0941\u0938\u094d\u0938\u0947 \u0915\u094b \u0905\u092a\u0928\u0947 \u092b\u093c\u093e\u092f\u0926\u0947 \u092e\u0947\u0902 \u0915\u0948\u0938\u0947 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930\u0947\u0902", "\u0643\u064a\u0641 \u062a\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u063a\u0636\u0628 \u0644\u0635\u0627\u0644\u062d\u0643", "Como usar a raiva a seu favor", "C\u00f3mo usar la ira a tu favor")
add("Use Procrastination To Your Advantage", "\u091f\u093e\u0932\u092e\u091f\u094b\u0932 \u0915\u094b \u0905\u092a\u0928\u0947 \u092b\u093c\u093e\u092f\u0926\u0947 \u092e\u0947\u0902 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930\u0947\u0902", "\u0627\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0645\u0645\u0627\u0637\u0644\u0629 \u0644\u0635\u0627\u0644\u062d\u0643", "Use a procrastina\u00e7\u00e3o a seu favor", "Usa la procrastinaci\u00f3n a tu favor")
add("Use Conflicts To Your Advantage", "\u091f\u0915\u0930\u093e\u0935 \u0915\u094b \u0905\u092a\u0928\u0947 \u092b\u093c\u093e\u092f\u0926\u0947 \u092e\u0947\u0902 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930\u0947\u0902", "\u0627\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0635\u0631\u0627\u0639\u0627\u062a \u0644\u0635\u0627\u0644\u062d\u0643", "Use os conflitos a seu favor", "Usa los conflictos a tu favor")
add("Survival", "\u0938\u0930\u094d\u0935\u093e\u0907\u0935\u0932", "\u0627\u0644\u0628\u0642\u0627\u0621", "Sobreviv\u00eancia", "Supervivencia")
add("Anger is not a problem if you know what it is", "\u0917\u0941\u0938\u094d\u0938\u093e \u0924\u092c \u0924\u0915 \u0938\u092e\u0938\u094d\u092f\u093e \u0928\u0939\u0940\u0902, \u091c\u092c \u0924\u0915 \u0906\u092a \u091c\u093e\u0928\u0924\u0947 \u0939\u0948\u0902 \u0915\u093f \u0935\u094b \u0939\u0948 \u0915\u094d\u092f\u093e", "\u0627\u0644\u063a\u0636\u0628 \u0644\u064a\u0633 \u0645\u0634\u0643\u0644\u0629 \u0625\u0630\u0627 \u0643\u0646\u062a \u062a\u0639\u0631\u0641 \u0645\u0627 \u0647\u0648", "A raiva n\u00e3o \u00e9 um problema se voc\u00ea sabe o que ela \u00e9", "La ira no es un problema si sabes lo que es")
add("Stop fighting it. Start redirecting it.", "\u0907\u0938\u0938\u0947 \u0932\u095c\u0928\u093e \u092c\u0902\u0926 \u0915\u0930\u094b\u0964 \u0907\u0938\u0947 \u0938\u0939\u0940 \u0926\u093f\u0936\u093e \u0926\u0947\u0928\u093e \u0936\u0941\u0930\u0942 \u0915\u0930\u094b\u0964", "\u062a\u0648\u0642\u0641 \u0639\u0646 \u0645\u062d\u0627\u0631\u0628\u062a\u0647\u0627. \u0627\u0628\u062f\u0623 \u0628\u062a\u0648\u062c\u064a\u0647\u0647\u0627.", "Pare de lutar contra ela. Comece a redirecion\u00e1-la.", "Deja de pelear con ella. Empieza a redirigirla.")
add("You don't need to escape problems. You need to upgrade them.", "\u0906\u092a\u0915\u094b \u0938\u092e\u0938\u094d\u092f\u093e\u0913\u0902 \u0938\u0947 \u092d\u093e\u0917\u0928\u093e \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 \u0909\u0928\u094d\u0939\u0947\u0902 \u0905\u092a\u0917\u094d\u0930\u0947\u0921 \u0915\u0930\u0928\u093e \u0939\u0948\u0964", "\u0644\u0633\u062a \u0628\u062d\u0627\u062c\u0629 \u0625\u0644\u0649 \u0627\u0644\u0647\u0631\u0648\u0628 \u0645\u0646 \u0627\u0644\u0645\u0634\u0643\u0644\u0627\u062a. \u0623\u0646\u062a \u0628\u062d\u0627\u062c\u0629 \u0625\u0644\u0649 \u062a\u0631\u0642\u064a\u062a\u0647\u0627.", "Voc\u00ea n\u00e3o precisa fugir dos problemas. Precisa fazer upgrade neles.", "No necesitas escapar de los problemas. Necesitas mejorarlos.")
add("Understanding the basic of everything we do.", "\u0939\u092e \u091c\u094b \u0915\u0941\u091b \u092d\u0940 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902, \u0909\u0938\u0915\u0940 \u092c\u0941\u0928\u093f\u092f\u093e\u0926 \u0915\u094b \u0938\u092e\u091d\u0928\u093e\u0964", "\u0641\u0647\u0645 \u0627\u0644\u0623\u0633\u0627\u0633 \u0627\u0644\u0630\u064a \u064a\u0642\u0648\u0645 \u0639\u0644\u064a\u0647 \u0643\u0644 \u0645\u0627 \u0646\u0641\u0639\u0644\u0647.", "Entendendo a base de tudo o que fazemos.", "Entendiendo la base de todo lo que hacemos.")

import pl_quality as Q
for _l in LANGINFO:
    LANGINFO[_l]["style"] = LANGINFO[_l]["style"] + " " + Q.STYLE_EXTRA[_l]
SYS = SYS + Q.RULES_EXTRA
Q.apply_ui_overrides(S)


def st(en, lang):
    v = S.get(en)
    return v[IDX[lang]] if v else None


# ---- helpers ---------------------------------------------------------------------------------------------
def plain(s): return H.unescape(re.sub(r"<[^>]+>", "", s))
def has_letters(s): return re.search(r"[A-Za-z]", s) is not None

def tagsig(s):
    out = Counter()
    for t in re.findall(r"<[^>]+>", s):
        t = re.sub(r"\s+", " ", t.strip().lower()).replace(" />", ">").replace("/>", ">")
        out[t] += 1
    return out

def find_key():
    k = os.environ.get("OMNIROUTE_API_KEY")
    if k: return k
    p = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        return None
    try:
        cfg = json.loads(txt)
        env = cfg.get("env", {}) or {}
        k = (env.get("vars", {}) or {}).get("OMNIROUTE_API_KEY") or env.get("OMNIROUTE_API_KEY")
        if k: return k
    except Exception:
        pass
    m = re.search(r'OMNIROUTE_API_KEY"?\s*[:=]\s*"([^"]+)"', txt)
    return m.group(1) if m else None


def _valid_base(src, out, lang, is_html):
    if not out or not out.strip(): return False, "empty"
    low = out.strip().lower()[:30]
    if low.startswith(("here is", "here's", "translation:", "sure", "certainly", "okay")): return False, "preamble"
    if is_html and tagsig(src) != tagsig(out): return False, "tags"
    if (not is_html) and src.count("\n") != out.count("\n"): return False, "lines"
    if src.count("___") != out.count("___"): return False, "blanks"
    ps, po = plain(src), plain(out)
    if len(ps) >= 30:
        r = len(po) / max(1, len(ps))
        if not (0.35 <= r <= 3.2): return False, "length %.2f" % r
    letters = re.findall(r"[^\W\d_]", po)
    info = LANGINFO[lang]
    if info["script"] and len(letters) >= 12:
        tgt = re.findall("[" + info["script"] + "]", po)
        thr = 0.3 if len(letters) < 60 else 0.5
        if len(tgt) / len(letters) < thr: return False, "script"
    else:
        words = re.findall(r"[A-Za-z']+", po.lower())
        if len(words) >= 8 and sum(w in EN_STOP for w in words) / len(words) > 0.2: return False, "still english"
        if len(ps) >= 15 and po.strip() == ps.strip(): return False, "unchanged"
    return True, ""


def valid(src, out, lang, is_html, kind="p"):
    ok, why = _valid_base(src, out, lang, is_html)
    if not ok:
        return ok, why
    return Q.valid_extra(src, out, lang, kind)


class Engine:
    def __init__(self, lang, cache_dir):
        self.lang = lang
        self.info = LANGINFO[lang]
        os.makedirs(cache_dir, exist_ok=True)
        self.path = os.path.join(cache_dir, lang + ".json")
        try:
            self.cache = json.load(open(self.path, encoding="utf-8"))
        except Exception:
            self.cache = {}
        self.stats = Counter()
        self.failures = []
        self.soft = []
        self.last_err = ""
        self.key = find_key()
        self.system = SYS.format(name=self.info["name"], style=self.info["style"])
        self.n = 0

    def save(self):
        tmp = self.path + ".tmp"
        json.dump(self.cache, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, self.path)

    def llm(self, text, temperature, note=""):
        body = json.dumps({"model": MODEL, "temperature": temperature, "stream": False,
                           "messages": [{"role": "system", "content": self.system + note}, {"role": "user", "content": text}]}).encode()
        req = urllib.request.Request(OMNI_URL, data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        with urllib.request.urlopen(req, timeout=150) as r:
            d = json.load(r)
        return d["choices"][0]["message"]["content"]

    @staticmethod
    def clean(o):
        o = re.sub(r"<think>.*?</think>", "", o or "", flags=re.S).strip()
        o = re.sub(r"^```[a-z]*\n", "", o)
        o = re.sub(r"\n```$", "", o).strip()
        return o

    def gt(self, text):
        chunks, cur = [], ""
        for sent in re.split(r"(?<=[.!?\u0964])\s+", text):
            if len(cur) + len(sent) > 1500 and cur:
                chunks.append(cur); cur = ""
            cur = (cur + " " + sent).strip()
        if cur: chunks.append(cur)
        out = []
        for c in chunks:
            data = urllib.parse.urlencode({"q": c}).encode()
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=%s&dt=t" % self.lang
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    j = json.load(r)
                out.append("".join(seg[0] for seg in j[0] if seg and seg[0]))
            except Exception as e:
                self.last_err = "google: " + str(e)[:120]
                return None
            time.sleep(0.4)
        return " ".join(out)

    def google(self, src, is_html):
        res = []
        for p in re.split(r"(<[^>]+>)", src):
            if p.startswith("<") and p.endswith(">"):
                res.append(p); continue
            if not has_letters(p):
                res.append(p); continue
            lead = re.match(r"\s*", p).group(); trail = re.search(r"\s*$", p).group()
            t = self.gt(H.unescape(p.strip()))
            if t is None: return None
            res.append(lead + (H.escape(t, quote=False) if is_html else t) + trail)
        return "".join(res)

    def tr(self, src, is_html, kind="p"):
        return Q.tr_impl(self, src, is_html, kind, valid)

BLOCK_RE = re.compile(r"(<(p|h2|h3|th|td|li)\b[^>]*>)(.*?)(</\2>)", re.S | re.I)

def tr_html_content(eng, content, rep, slug):
    def f(m):
        inner = m.group(3)
        if not has_letters(plain(inner)): return m.group(0)
        val = eng.tr(inner, True, "h" if m.group(2).lower() in ("h2", "h3", "th", "td") else "p")
        if eng.lang == "ar":
            val = Q.wrap_ltr(val)
        return m.group(1) + val + m.group(4)
    out = BLOCK_RE.sub(f, content)
    left = re.sub(r"<[^>]+>", "", BLOCK_RE.sub("", content))
    if has_letters(left): rep["untranslated"].append("%s: text outside p/h2/h3/td/th/li: %r" % (slug, left.strip()[:60]))
    return out

def tr_plain_content(eng, content):
    return "\n\n".join(eng.tr(p, False) if has_letters(p) else p for p in content.split("\n\n"))


def main():
    if len(sys.argv) < 5:
        print(__doc__ or "usage: lang_build.py ORIG_DIR LANG OUT_DIR CACHE_DIR"); return 2
    orig_dir, lang, out_dir, cache_dir = sys.argv[1:5]
    info = LANGINFO[lang]
    node = shutil.which("node")
    if not node:
        print("FATAL: node not found"); return 2
    os.makedirs(out_dir, exist_ok=True)
    src = open(os.path.join(orig_dir, "index.html"), encoding="utf-8").read()
    rep = {"lang": lang, "missing": [], "untranslated": [], "uncovered_ui": []}
    eng = Engine(lang, cache_dir)
    print("[%s] engine key present: %s, model: %s, cache entries: %d" % (lang, bool(eng.key), MODEL, len(eng.cache)), flush=True)

    def T(en):
        return st(en, lang) or eng.tr(en, False)
    HE = lambda s: H.escape(s, quote=False)

    prefix = "const ARTICLES = "
    a = src.index(prefix + "[")
    b = src.index("\n];", a)
    arr_js = src[a + len(prefix): b + 2]
    pre, post = src[:a], src[b + 3:]

    r = subprocess.run([node, "-e", "const vm=require('vm');let s='';process.stdin.on('data',d=>s+=d).on('end',()=>process.stdout.write(JSON.stringify(vm.runInNewContext('('+s+')'))))"],
                       input=arr_js.encode("utf-8"), capture_output=True, timeout=60)
    if r.returncode != 0:
        print("FATAL: could not read ARTICLES:", r.stderr.decode()[:300]); return 2
    arts = json.loads(r.stdout.decode("utf-8"))
    rep["books"] = len(arts)

    # ---- books ----
    for art in arts:
        slug = art.get("slug") or art.get("title")
        print("[%s] book %s" % (lang, slug), flush=True)
        art["title"] = T(art["title"])
        if art.get("subtitle"): art["subtitle"] = T(art["subtitle"])
        if art.get("category"): art["category"] = T(art["category"])
        c = art.get("content")
        if c:
            art["content"] = tr_html_content(eng, c, rep, slug) if art.get("isHtml") else tr_plain_content(eng, c)
    new_arr = json.dumps(arts, ensure_ascii=False, indent=2).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    mid = prefix + new_arr + ";"

    # titles in original order, for the SEO section and JSON-LD
    orig_arts = json.loads(r.stdout.decode("utf-8"))
    tmap = {o["title"]: n["title"] for o, n in zip(orig_arts, arts)}

    # ---- pre: head + markup ----
    def hrep(text, find, new):
        if find not in text:
            rep["missing"].append("html:" + find[:50]); return text
        return text.replace(find, new)

    pre = pre.replace(ORIG_BASE, site_base(lang))
    pre = hrep(pre, '<html lang="en">', '<html lang="%s"%s>' % (lang, ' dir="rtl"' if info["rtl"] else ""))
    pre = hrep(pre, "<title>" + TITLE + "</title>", "<title>%s</title>" % HE(T(TITLE)))
    for attr in ('name="description"', 'name="keywords"', 'property="og:title"', 'property="og:description"', 'name="twitter:title"', 'name="twitter:description"'):
        pat = re.compile(r'(<meta ' + re.escape(attr) + r' content=")(.*?)(" ?/?>)', re.S)
        m = pat.search(pre)
        if not m:
            rep["missing"].append("meta:" + attr); continue
        val = H.unescape(m.group(2))
        newv = T(val)
        pre = pat.sub(lambda mm: mm.group(1) + H.escape(newv, quote=True) + mm.group(3), pre, count=1)
    pairs = [
        ('>A private reading room.<', '>%s<' % HE(T("A private reading room."))),
        ('Continue with Google', HE(T("Continue with Google"))),
        ('<div class="divider">or</div>', '<div class="divider">%s</div>' % HE(T("or"))),
        ('<label>Name</label>', '<label>%s</label>' % HE(T("Name"))),
        ('<label>Email</label>', '<label>%s</label>' % HE(T("Email"))),
        ('<label>Password</label>', '<label>%s</label>' % HE(T("Password"))),
        ('placeholder="Your name"', 'placeholder="%s"' % H.escape(T("Your name"), quote=True)),
        ('Enter Library</button>', HE(T("Enter Library")) + '</button>'),
        ('Sign out</button>', HE(T("Sign out")) + '</button>'),
        ('>Your Collection<', '>%s<' % HE(T("Your Collection"))),
        ('<h1>The Library</h1>', '<h1>%s</h1>' % HE(T("The Library"))),
        ('>0% completed<', '>%s<' % HE(T("0% completed"))),
        ('>Completed \u2713<', '>%s<' % HE(T("Completed \u2713"))),
    ]
    pairs += [
        ('<h2>The shelves are empty.</h2>', '<h2>%s</h2>' % HE(Q.EXTRA_UI[lang]["empty_h"])),
        ('<p>Books will appear here once they\'re added to the <code style="background:#1e1e1e;padding:2px 6px;border-radius:4px;font-size:11px">ARTICLES</code> array in the source code.</p>', '<p>%s</p>' % Q.EXTRA_UI[lang]["empty_p"]),
        ('placeholder="you@example.com"', 'placeholder="%s"' % Q.EXTRA_UI[lang]["email_ph"]),
    ]
    handled = set()
    for f, n in pairs:
        pre = hrep(pre, f, n)
        handled.add(re.sub(r"<[^>]+>|^>|<$", "", f).strip())
    # JSON-LD
    def ld(m):
        d = json.loads(m.group(1))
        d["inLanguage"] = lang
        if d.get("description"): d["description"] = T(d["description"])
        for part in d.get("hasPart", []):
            part["name"] = tmap.get(part.get("name"), T(part["name"]))
            if part.get("description"): part["description"] = T(part["description"])
            if part.get("genre"): part["genre"] = T(part["genre"])
        return '<script type="application/ld+json">\n  ' + json.dumps(d, ensure_ascii=False, indent=2).replace("</", "<\\/") + "\n  </script>"
    pre, n_ld = re.subn(r'<script type="application/ld\+json">(.*?)</script>', ld, pre, count=1, flags=re.S)
    if not n_ld: rep["missing"].append("json-ld")
    # hreflang alternates (after the base url swap, so x-default keeps the original)
    alts = "".join('\n  <link rel="alternate" hreflang="%s" href="%s" />' % (x, u) for x, u in [("en", ORIG_BASE)] + [(l, site_base(l)) for l in LANGS] + [("x-default", ORIG_BASE)])
    pre, n_c = re.subn(r'(<link rel="canonical"[^>]*>)', lambda m: m.group(1) + alts, pre, count=1)
    if not n_c: rep["missing"].append("canonical")
    # fonts + rtl css
    extra = ""
    if lang == "hi":
        pre = hrep(pre, "&family=Rye&display=swap", "&family=Rye&family=Noto+Sans+Devanagari:wght@300;400;500;600;700&display=swap")
        extra = "html,body{font-family:'Inter','Noto Sans Devanagari',sans-serif}#seo-preview h1{font-family:'Noto Sans Devanagari',serif;font-weight:700}*{letter-spacing:0 !important}"
    if lang == "ar":
        pre = hrep(pre, "&family=Rye&display=swap", "&family=Rye&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap")
        extra = ("html,body{font-family:'Inter','Noto Sans Arabic',sans-serif}#seo-preview h1{font-family:'Noto Sans Arabic',serif;font-weight:700}*{letter-spacing:0 !important}"
                 "[dir=\"rtl\"] .modal-body table th{text-align:right}"
                 "[dir=\"rtl\"] .modal-body ul,[dir=\"rtl\"] .modal-body ol{padding-left:0;padding-right:1.4em}"
                 "[dir=\"rtl\"] .book-cover{border-radius:10px 5px 5px 10px;box-shadow:4px 0 0 0 rgba(0,0,0,0.4),-4px 4px 20px rgba(0,0,0,0.6),inset 3px 0 6px rgba(0,0,0,0.3)}"
                 "[dir=\"rtl\"] .book-cover::before{left:auto;right:0;border-radius:0 5px 5px 0}")
    if extra:
        if "</style>" in pre: pre = pre.replace("</style>", "\n    /* language tweaks */\n    " + extra + "\n  </style>", 1)
        else: rep["missing"].append("style-close")

    # ---- post: script rest + SEO section ----
    post = post.replace(ORIG_BASE, site_base(lang))
    _pd = "return sanitize(email) + '_' + sanitize(title);"
    if _pd in post:
        post = post.replace(_pd, "const _a = ARTICLES.find(x => x.title === title); return sanitize(email) + '_%s_' + sanitize(_a && _a.slug ? _a.slug : title);" % lang)
    else:
        rep.setdefault("errors", []).append("progressDocId was not patched")
    def jsrep(text, en):
        needle = "'" + en + "'"
        if needle not in text:
            rep["missing"].append("js:" + en[:50]); return text
        return text.replace(needle, json.dumps(T(en), ensure_ascii=False))
    for en in ("Reader", "Enter Library", "Entering\u2026", "0% completed", "% completed", "Book content coming soon.",
               "Please enter a valid email address.", "This account has been disabled.", "No account found. Check your email or sign up.",
               "Incorrect password.", "An account with this email already exists.", "Password must be at least 6 characters.",
               "Google sign-in was cancelled.", "Network error. Check your connection.", "Incorrect email or password.",
               "Too many attempts. Try again later.", "Something went wrong. Please try again."):
        post = jsrep(post, en)
    if "${mins} min read" in post:
        post = post.replace("${mins} min read", st("{n} min read", lang).replace("{n}", "${mins}"))
    else:
        rep["missing"].append("js:min read")

    def seo(m):
        sec = m.group(0)
        sec = re.sub(r"<h1>(.*?)</h1>", lambda x: "<h1>%s</h1>" % HE(T(H.unescape(x.group(1)))), sec, flags=re.S)
        sec = re.sub(r'<p class="intro">(.*?)</p>', lambda x: '<p class="intro">%s</p>' % eng.tr(x.group(1), True), sec, flags=re.S)
        sec = re.sub(r'<div class="cat">(.*?)</div>', lambda x: '<div class="cat">%s</div>' % HE(T(H.unescape(x.group(1)))), sec, flags=re.S)
        sec = re.sub(r"<h2>(.*?)</h2>", lambda x: "<h2>%s</h2>" % HE(T(H.unescape(x.group(1)))), sec, flags=re.S)
        sec = re.sub(r'<div class="sub">(.*?)</div>', lambda x: '<div class="sub">%s</div>' % HE(T(H.unescape(x.group(1)))), sec, flags=re.S)
        sec = re.sub(r"<p>(.*?)</p>", lambda x: "<p>%s</p>" % eng.tr(x.group(1), True), sec, flags=re.S)
        sec = re.sub(r'<p class="cta">(.*?)</p>', lambda x: '<p class="cta">%s</p>' % eng.tr(x.group(1), True), sec, flags=re.S)
        if lang == "ar":
            sec = Q.wrap_ltr(sec)
        return sec
    post, n_seo = re.subn(r'<section id="seo-preview">.*?</section>', seo, post, count=1, flags=re.S)
    if not n_seo: rep["missing"].append("seo-section")

    # drift scan on the ORIGINAL: text we do not handle (informational)
    try:
        body = src.split("<body>")[1].split("<script>")[0]
        known = set(S.keys()) | handled | {"Perspective Library", "The shelves are empty."}
        for t in re.findall(r">([^<>]{3,})<", body):
            t = t.strip()
            if has_letters(t) and t not in known and not t.startswith("Books will appear") and len(t) < 120:
                rep["uncovered_ui"].append(t[:60])
    except Exception:
        pass

    out_html = pre + mid + post
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(out_html)
    shutil.copy(os.path.join(orig_dir, "logo.jpeg"), os.path.join(out_dir, "logo.jpeg"))
    for fn in ("robots.txt", "sitemap.xml"):
        try:
            t = open(os.path.join(orig_dir, fn), encoding="utf-8").read().replace(ORIG_BASE, site_base(lang))
        except Exception:
            t = ""
        open(os.path.join(out_dir, fn), "w", encoding="utf-8").write(t)

    rep["stats"] = dict(eng.stats)
    rep["failures"] = eng.failures[:20]
    rep["last_error"] = eng.last_err
    rep["engine_key"] = bool(eng.key)
    rep["model"] = MODEL
    rep["soft_count"] = len(eng.soft)
    rep["soft_issues"] = eng.soft[:80]
    rep["audit"] = getattr(eng, "audit", [])[:40]
    rep["complete"] = (not eng.failures) and (not rep["untranslated"]) and (not rep.get("errors"))
    json.dump(rep, open(os.path.join(out_dir, "BUILD_REPORT.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[%s] DONE complete=%s stats=%s missing=%s" % (lang, rep["complete"], rep["stats"], rep["missing"]), flush=True)
    return 0 if rep["complete"] else 3


if __name__ == "__main__":
    sys.exit(main())
