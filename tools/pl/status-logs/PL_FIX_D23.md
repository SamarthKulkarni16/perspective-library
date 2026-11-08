# PL FIX D23 2026-10-23 17:17 IST (build and test, before deploy)
# PL LANGUAGE SITES 2026-10-23 17:17 IST

## hi: build rc=0 (0=complete 3=some English left 2=failed), test rc=0
books = 4
stats = {'cache': 124, 'cache_fixed': 12}
complete = True
engine_key = True
model = samarth-free-chain
last_error = 
failures = []
missing = []
untranslated = []
uncovered_ui = ['ARTICLES', 'array in the source code.']
LANGTEST [hi] RESULT: ALL PASS
[hi] book survival
[hi] DONE complete=True stats={'cache': 124, 'cache_fixed': 12} missing=[]

## ar: build rc=0 (0=complete 3=some English left 2=failed), test rc=0
books = 4
stats = {'cache': 133, 'cache_fixed': 3}
complete = True
engine_key = True
model = samarth-free-chain
last_error = 
failures = []
missing = []
untranslated = []
uncovered_ui = ['ARTICLES', 'array in the source code.']
LANGTEST [ar] RESULT: ALL PASS
[ar] book survival
[ar] DONE complete=True stats={'cache': 133, 'cache_fixed': 3} missing=[]

## pt: build rc=0 (0=complete 3=some English left 2=failed), test rc=0
books = 4
stats = {'cache': 134, 'cache_fixed': 13}
complete = True
engine_key = True
model = samarth-free-chain
last_error = 
failures = []
missing = []
untranslated = []
uncovered_ui = ['ARTICLES', 'array in the source code.']
LANGTEST [pt] RESULT: ALL PASS
[pt] book survival
[pt] DONE complete=True stats={'cache': 134, 'cache_fixed': 13} missing=[]

## es: build rc=0 (0=complete 3=some English left 2=failed), test rc=0
books = 4
stats = {'cache': 134, 'cache_fixed': 2}
complete = True
engine_key = True
model = samarth-free-chain
last_error = 
failures = []
missing = []
untranslated = []
uncovered_ui = ['ARTICLES', 'array in the source code.']
LANGTEST [es] RESULT: ALL PASS
[es] book survival
[es] DONE complete=True stats={'cache': 134, 'cache_fixed': 2} missing=[]

## deploy
CHANGED index.html
SAME logo.jpeg
SAME robots.txt
SAME sitemap.xml
DEPLOYED hi https://samarthkulkarni16.github.io/perspective-library-hi/
CHANGED index.html
SAME logo.jpeg
SAME robots.txt
SAME sitemap.xml
DEPLOYED ar https://samarthkulkarni16.github.io/perspective-library-ar/
CHANGED index.html
SAME logo.jpeg
SAME robots.txt
SAME sitemap.xml
DEPLOYED pt https://samarthkulkarni16.github.io/perspective-library-pt/
SAME index.html
SAME logo.jpeg
SAME robots.txt
SAME sitemap.xml
DEPLOYED es https://samarthkulkarni16.github.io/perspective-library-es/
live hi: OK https://samarthkulkarni16.github.io/perspective-library-hi/
live ar: OK https://samarthkulkarni16.github.io/perspective-library-ar/
live pt: OK https://samarthkulkarni16.github.io/perspective-library-pt/
live es: OK https://samarthkulkarni16.github.io/perspective-library-es/
