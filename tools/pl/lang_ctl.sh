#!/bin/bash
# CEO 2026-10-20: Perspective Library language sites controller.
# usage: lang_ctl.sh preflight | fetch | run | go | sync | shots | report
#   run   = fetch the live original, build all 4 languages, test them (NO deploy)
#   go    = deploy every language that built complete and passed its tests, verify live, install the 10-minute cron
#   sync  = (cron) if the original site changed: rebuild, test, deploy; else do nothing
export PATH=$PATH:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin
OWN=SamarthKulkarni16; HQ=$OWN/perspective-library
W=/home/ubuntu/work/pl; S=$W/scripts; ORIG=$W/orig; OUT=$W/out; CACHE=$W/cache; STATE=$W/state
LANGS="hi ar pt es"
mkdir -p $W $S $ORIG $OUT $CACHE $STATE
log() { echo "$(date '+%F %T') $*"; }
[ -s $W/model.txt ] && export PL_MODEL=$(cat $W/model.txt)

hq_up() { # local file -> hq path
  local SHA; SHA=$(gh api "repos/$HQ/contents/$2" --jq .sha 2>/dev/null)
  gh api -X PUT "repos/$HQ/contents/$2" -f message="pl $(date +%H:%M)" -f content="$(base64 -w0 "$1")" ${SHA:+-f sha="$SHA"} --jq '.commit.sha' >/dev/null 2>&1 && echo "UPLOADED $2" || echo "FAILED $2"
}
red() { sed -E 's/(ghp_|github_pat_|gho_|hf_|sk-)[A-Za-z0-9_-]+/[REDACTED]/g; s/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/x.x.x.x/g' | iconv -c -f utf-8 -t ascii//TRANSLIT; }

preflight() {
  echo "node: $(command -v node || echo MISSING) $(node -v 2>/dev/null)"
  python3 -c "import playwright, PIL; print('python playwright + PIL: ok')" 2>&1 | tail -1
  echo "gh user: $(gh api user --jq .login 2>&1 | head -1)"
  gh auth status 2>&1 | grep -iE 'scopes' | head -1
  echo "crontab: $(command -v crontab || echo MISSING)"
  echo "free disk: $(df -h / | tail -1 | awk '{print $4}')"
  for L in $LANGS; do echo "repo perspective-library-$L: $(gh repo view $OWN/perspective-library-$L --json url --jq .url 2>/dev/null || echo not-created-yet)"; done
  python3 - <<'PY'
import os, sys, json, urllib.request
sys.path.insert(0, "/home/ubuntu/work/pl/scripts")
import lang_build as B
k = B.find_key()
print("omniroute key found:", bool(k))
if not k: sys.exit(0)
ok = None
for m in [os.environ.get("PL_MODEL") or "samarth-free-chain", "samarth-free-chain", "omniroute/samarth-free-chain"]:
    try:
        body = json.dumps({"model": m, "temperature": 0.2, "stream": False, "messages": [{"role": "system", "content": "Translate the user's text from English to Hindi (Devanagari). Output only the translation."}, {"role": "user", "content": "Good morning, my friend. Anger is not a problem if you know what it is."}]}).encode()
        req = urllib.request.Request(B.OMNI_URL, data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer " + k})
        d = json.load(urllib.request.urlopen(req, timeout=120))
        out = d["choices"][0]["message"]["content"]
        print("model %s works -> %s" % (m, out.strip()[:100]))
        ok = m; break
    except Exception as e:
        print("model %s failed: %s" % (m, str(e)[:120]))
if ok: open("/home/ubuntu/work/pl/model.txt", "w").write(ok)
PY
}

fetch() {
  local f
  for f in index.html logo.jpeg robots.txt sitemap.xml; do
    gh api repos/$OWN/perspective-library/contents/$f -H 'Accept: application/vnd.github.raw' > $ORIG/$f.tmp 2>/dev/null && [ -s $ORIG/$f.tmp ] && mv $ORIG/$f.tmp $ORIG/$f || { echo "fetch failed: $f"; return 1; }
  done
  log "fetched original: index.html $(stat -c %s $ORIG/index.html) bytes"
}

build_all() {
  local L
  for L in $LANGS; do
    ( python3 $S/lang_build.py $ORIG $L $OUT/$L $CACHE > $W/log_build_$L.txt 2>&1; echo $? > $W/rc_build_$L ) &
  done
  wait
}

test_all() {
  local L
  rm -rf /tmp/plshots; mkdir -p /tmp/plshots
  for L in $LANGS; do
    if [ "$(cat $W/rc_build_$L 2>/dev/null)" = 0 ]; then
      python3 $S/lang_test.py $OUT/$L $L $ORIG > $W/log_test_$L.txt 2>&1; echo $? > $W/rc_test_$L
    else echo 9 > $W/rc_test_$L; fi
  done
}

report() {
  echo "# PL LANGUAGE SITES $(date '+%F %H:%M IST')"
  local L
  for L in $LANGS; do
    echo; echo "## $L: build rc=$(cat $W/rc_build_$L 2>/dev/null) (0=complete 3=some English left 2=failed), test rc=$(cat $W/rc_test_$L 2>/dev/null)"
    python3 - "$OUT/$L/BUILD_REPORT.json" <<'PY' 2>&1 | cut -c1-1200
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    for k in ("books", "stats", "complete", "engine_key", "model", "last_error", "failures", "missing", "untranslated", "uncovered_ui"):
        if k in d: print(k, "=", d[k])
except Exception as e:
    print("no build report:", e)
PY
    grep -E 'FAIL|RESULT' $W/log_test_$L.txt 2>/dev/null | head -14
    tail -2 $W/log_build_$L.txt 2>/dev/null
  done
}

put() { # repo path localfile
  local R=$1 P=$2 F=$3 L RS
  L=$(git hash-object "$F"); RS=$(gh api "repos/$OWN/$R/contents/$P" --jq .sha 2>/dev/null)
  if [ "$L" = "$RS" ]; then echo "SAME $P"; return 0; fi
  python3 - "$F" "$RS" > $W/payload.json <<'PY'
import sys, json, base64
f, sha = sys.argv[1], sys.argv[2]
d = {"message": "auto-build from perspective-library", "content": base64.b64encode(open(f, "rb").read()).decode()}
if sha: d["sha"] = sha
print(json.dumps(d))
PY
  gh api -X PUT "repos/$OWN/$R/contents/$P" --input $W/payload.json --jq '.commit.sha' >/dev/null && echo "CHANGED $P" || { echo "FAILED $P"; return 1; }
}

deploy() {
  local L=$1 R=perspective-library-$1 f B
  if ! gh repo view $OWN/$R >/dev/null 2>&1; then
    gh repo create $OWN/$R --public --add-readme -d "Perspective Library ($L), auto-built from perspective-library. Do not edit by hand." >/dev/null 2>&1 || { echo "FAILED create $R"; return 1; }
    sleep 4
  fi
  for f in index.html logo.jpeg robots.txt sitemap.xml; do put $R $f $OUT/$L/$f || return 1; done
  B=$(gh api repos/$OWN/$R --jq .default_branch 2>/dev/null); B=${B:-main}
  gh api repos/$OWN/$R/pages >/dev/null 2>&1 || gh api -X POST repos/$OWN/$R/pages -f "source[branch]=$B" -f "source[path]=/" >/dev/null 2>&1 || echo "pages enable failed for $R, check Settings > Pages"
  echo "DEPLOYED $L https://samarthkulkarni16.github.io/$R/"
}

verify_live() {
  local L U i c
  for L in $LANGS; do
    U=https://samarthkulkarni16.github.io/perspective-library-$L/; c=0
    for i in 1 2 3 4 5 6 7 8 9 10; do
      c=$(curl -s -m 20 "$U" | grep -c "lang=\"$L\""); [ "$c" -ge 1 ] && break; sleep 20
    done
    echo "live $L: $([ "$c" -ge 1 ] && echo OK || echo NOT-YET) $U"
  done
}

fingerprint() { local f; for f in index.html logo.jpeg robots.txt sitemap.xml; do gh api repos/$OWN/perspective-library/contents/$f --jq .sha 2>/dev/null; done | tr '\n' ' '; }

install_cron() {
  command -v crontab >/dev/null || { echo "crontab missing: install cron first (sudo apt-get install -y cron)"; return 1; }
  ( crontab -l 2>/dev/null | grep -v 'lang_ctl.sh sync'; echo "*/10 * * * * /bin/bash $S/lang_ctl.sh sync >> $W/sync.log 2>&1" ) | crontab -
  echo "cron installed: $(crontab -l | grep 'lang_ctl.sh sync')"
}

sync() {
  exec 9>/tmp/pl_sync.lock; flock -n 9 || exit 0
  local FP fails last ok L
  FP=$(fingerprint)
  [ -z "${FP// }" ] && { log "github not reachable, skipping"; exit 0; }
  [ "$FP" = "$(cat $STATE/fp 2>/dev/null)" ] && exit 0
  fails=$(cat $STATE/fails 2>/dev/null || echo 0); last=$(cat $STATE/lastfail 2>/dev/null || echo 0)
  if [ "$fails" -ge 3 ] && [ $(( $(date +%s) - last )) -lt 3600 ]; then exit 0; fi
  log "original changed, rebuilding all languages"
  fetch || { log "fetch failed"; exit 0; }
  build_all; test_all
  ok=1
  for L in $LANGS; do
    if [ "$(cat $W/rc_build_$L)" = 0 ] && [ "$(cat $W/rc_test_$L)" = 0 ]; then deploy $L || ok=0; else ok=0; log "$L not deployed (build rc=$(cat $W/rc_build_$L) test rc=$(cat $W/rc_test_$L))"; fi
  done
  if [ $ok = 1 ]; then
    echo "$FP" > $STATE/fp; echo 0 > $STATE/fails
    { echo "# PL SYNC $(date '+%F %H:%M IST'): original changed, all 4 language sites rebuilt, tested and deployed"; echo; report; } | red > $W/sync_status.md; hq_up $W/sync_status.md tools/pl/status/PL_SYNC_LATEST.md
  else
    echo $(( fails + 1 )) > $STATE/fails; date +%s > $STATE/lastfail
    { echo "# PL SYNC FAILED $(date '+%F %H:%M IST'): the language sites were NOT changed (the old versions stay live). Retry on the next cycle (max 3 tries per hour)."; echo; report; } | red > $W/sync_status.md; hq_up $W/sync_status.md tools/pl/status/PL_SYNC_LATEST.md
  fi
}

case "$1" in
  preflight) preflight ;;
  fetch) fetch ;;
  run) fetch && build_all && test_all && report ;;
  report) report ;;
  go)
    for L in $LANGS; do
      if [ "$(cat $W/rc_build_$L 2>/dev/null)" = 0 ] && [ "$(cat $W/rc_test_$L 2>/dev/null)" = 0 ]; then deploy $L; else echo "SKIP $L (build rc=$(cat $W/rc_build_$L 2>/dev/null) test rc=$(cat $W/rc_test_$L 2>/dev/null))"; fi
    done
    verify_live; fingerprint > $STATE/fp; echo 0 > $STATE/fails; install_cron ;;
  sync) sync ;;
  shots) gh release delete pl-lang-shots-d20 --repo $HQ -y --cleanup-tag >/dev/null 2>&1; gh release create pl-lang-shots-d20 --repo $HQ --title "Language site screenshots" --notes "Screenshots of the 4 language sites (shelf, 2 books, sign-in, phone)." /tmp/plshots/*.png 2>&1 | tail -1 ;;
  *) echo "usage: lang_ctl.sh preflight|fetch|run|go|sync|shots|report" ;;
esac
