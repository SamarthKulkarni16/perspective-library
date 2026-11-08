#!/bin/bash
# D23 stage 2 (CEO 2026-10-23): wait until the Kaggle kernel is free (the G1 run uses the same model gateway), then rebuild the 4 language sites
# ONE language at a time, test them, deploy the ones that pass, and upload a report plus a heading review to hq.
# PL_NOWAIT=1 skips the waiting. Progress: status/PL_FIX_D23_PROGRESS.md ; results: status/PL_FIX_D23.md and status/PL_FIX_D23_REVIEW.md
export PATH=$PATH:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin
. /home/ubuntu/work/pl/scripts/lang_ctl.sh >/dev/null 2>&1      # only loads the functions and paths (W S ORIG OUT CACHE STATE LANGS)
SLUG=samarthkulkarni16/long-form-editor-clipper
PROG=/tmp/pl_fix_progress.txt; : > $PROG
prog() { echo "$(date '+%F %H:%M IST') $*" >> $PROG; hq_up $PROG status/PL_FIX_D23_PROGRESS.md >/dev/null; }
kern_wait() {
  [ "$PL_NOWAIT" = 1 ] && return 0
  local i s
  for i in $(seq 1 420); do
    s=$(kaggle kernels status $SLUG 2>&1)
    case "$s" in *RUNNING*|*QUEUED*) sleep 60 ;; *) return 0 ;; esac
  done
  return 0
}
exec 8>/tmp/pl_sync.lock
flock -w 120 8 || { prog "could not get the sync lock, abort"; exit 1; }
prog "stage 2 started, waiting for the Kaggle kernel to be free"
kern_wait
fetch || { prog "fetch of the original site failed, abort"; exit 1; }
prog "kernel free, original fetched, building one language at a time"
for L in $LANGS; do
  kern_wait
  prog "build $L start"
  python3 $S/lang_build.py $ORIG $L $OUT/$L $CACHE > $W/log_build_$L.txt 2>&1; echo $? > $W/rc_build_$L
  prog "build $L rc=$(cat $W/rc_build_$L) (0 complete, 3 some text could not be translated, 2 failed)"
done
prog "testing all four in a headless browser"
test_all
for L in $LANGS; do prog "test $L rc=$(cat $W/rc_test_$L) (0 = all checks passed)"; done
{ echo "# PL FIX D23 $(date '+%F %H:%M IST') (build and test, before deploy)"; report; } | red > /tmp/pl_fix_report.md
hq_up /tmp/pl_fix_report.md status/PL_FIX_D23.md >/dev/null

# ---- heading / meta review in UTF-8 (so the CEO can read the real text on GitHub)
python3 - <<'PY'
import json, re, sys, io
sys.path.insert(0, "/home/ubuntu/work/pl/scripts")
import pl_quality as Q
W = "/home/ubuntu/work/pl"
out = ["# PL FIX D23 REVIEW (headings, meta text and rule checks of the freshly built sites)", ""]
for L in ("hi", "ar", "pt", "es"):
    out.append("## " + L)
    try:
        t = io.open("%s/out/%s/index.html" % (W, L), encoding="utf-8").read()
    except Exception as e:
        out.append("no build: %s" % e); continue
    m = re.search(r"<title>(.*?)</title>", t, re.S); out.append("title: " + (m.group(1) if m else "?"))
    m = re.search(r'<meta name="description" content="(.*?)"', t, re.S); out.append("meta description: " + (m.group(1)[:300] if m else "?"))
    i = t.index("const ARTICLES = ") + len("const ARTICLES = ")
    arts, _ = json.JSONDecoder().raw_decode(t[i:])
    alltext = []
    for a in arts:
        out.append("")
        out.append("### %s | %s | %s" % (a.get("slug"), a.get("title"), a.get("subtitle")))
        c = a.get("content", "")
        alltext.append(" ".join([a.get("title", ""), a.get("subtitle", ""), a.get("category", ""), c]))
        if a.get("isHtml"):
            hs = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", c, re.S)
            for h in hs:
                out.append("- " + re.sub(r"<[^>]+>", "", h).strip())
        else:
            short = [l.strip() for l in c.split("\n") if 0 < len(l.strip()) < 70][:14]
            for l in short:
                out.append("- " + l)
    full = " ".join(alltext)
    out.append("")
    out.append("hard scan: " + (", ".join(Q.scan_text(full, L)) or "clean"))
    sc = Q.soft_issues(Q.plain(full), L)
    out.append("style issues left in the whole text: %d" % len(sc))
    try:
        rep = json.load(io.open("%s/out/%s/BUILD_REPORT.json" % (W, L), encoding="utf-8"))
        out.append("build stats: %s" % rep.get("stats"))
        out.append("errors: %s | failures: %s | missing: %s | untranslated: %s" % (rep.get("errors"), rep.get("failures"), rep.get("missing"), rep.get("untranslated")))
        out.append("uncovered UI text: %s" % rep.get("uncovered_ui"))
        out.append("soft issues accepted (%s):" % rep.get("soft_count"))
        for s in (rep.get("soft_issues") or [])[:20]:
            out.append("  - [%s] %s | %s" % (s.get("eng"), s.get("src"), "; ".join(s.get("issues", []))[:160]))
    except Exception as e:
        out.append("no build report: %s" % e)
    out.append("")
io.open("/tmp/pl_fix_review.md", "w", encoding="utf-8").write("\n".join(out))
print("review written")
PY
hq_up /tmp/pl_fix_review.md status/PL_FIX_D23_REVIEW.md >/dev/null

# ---- deploy only the languages that built complete AND passed every test (the others keep their old live version)
DEP=/tmp/pl_fix_deploy.txt; : > $DEP
ALL=1
for L in $LANGS; do
  if [ "$(cat $W/rc_build_$L)" = 0 ] && [ "$(cat $W/rc_test_$L)" = 0 ]; then
    deploy $L >> $DEP 2>&1 || ALL=0
  else
    echo "SKIP $L (build rc=$(cat $W/rc_build_$L) test rc=$(cat $W/rc_test_$L)): the old version stays live" >> $DEP; ALL=0
  fi
done
verify_live >> $DEP 2>&1
if [ $ALL = 1 ]; then fingerprint > $STATE/fp; echo 0 > $STATE/fails; fi
{ cat /tmp/pl_fix_report.md; echo; echo "## deploy"; cat $DEP; } | red > /tmp/pl_fix_final.md
hq_up /tmp/pl_fix_final.md status/PL_FIX_D23.md >/dev/null
prog "DONE all_four_deployed=$ALL"
