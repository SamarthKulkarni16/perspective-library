#!/bin/bash
# D23 (CEO 2026-10-23) Perspective Library language sites, stage 1: install the quality code, self-test it OFFLINE, audit the old translation cache against
# the new rules (no model calls, so the Kaggle run is not disturbed), then start stage 2 in the background (it waits for the Kaggle kernel).
# Run:  gh api repos/SamarthKulkarni16/hq/contents/run/d23_pl_stage1.sh -H "Accept: application/vnd.github.raw" > /tmp/d23_pl_stage1.sh && bash /tmp/d23_pl_stage1.sh
export PATH=$PATH:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin
OWN=SamarthKulkarni16
W=/home/ubuntu/work/pl
SC=$W/scripts
PASTE=/tmp/ceo_out.txt
HQDIR=/home/ubuntu/hq
up() { S=$(gh api "repos/SamarthKulkarni16/hq/contents/$2" --jq .sha 2>/dev/null); gh api -X PUT "repos/SamarthKulkarni16/hq/contents/$2" -f message="ceo paste $(date +%H:%M)" -f content="$(base64 -w0 "$1")" ${S:+-f sha="$S"} --jq '.commit.sha' >/dev/null 2>&1 && echo "UPLOADED $2" || echo "FAILED $2"; }
raw() { gh api "repos/$OWN/hq/contents/$1" -H "Accept: application/vnd.github.raw" > "$2" 2>/dev/null && [ -s "$2" ]; }
{
echo "== NOW $(date '+%F %H:%M IST')"
echo "== 1 download the new files"
OK=1
for f in pl_quality.py d23_pl_patch.py d23_pl_stage2.sh; do
  if raw scripts/pl/$f $SC/$f.new; then mv $SC/$f.new $SC/$f; echo "got $f ($(wc -c < $SC/$f) bytes)"; else echo "FAILED to download $f"; OK=0; fi
done
echo "== 2 offline self-test of the new rules"
ST=9
if [ $OK = 1 ]; then python3 $SC/pl_quality.py selftest 2>&1 | grep -E 'FAIL|RESULT|==' ; python3 $SC/pl_quality.py selftest >/dev/null 2>&1; ST=$?; fi
echo "selftest rc=$ST (0 = every rule behaves)"
echo "== 3 patch lang_build.py and lang_test.py (backups: *.pre_d23, cache backup: cache.pre_d23)"
PRC=9
if [ $ST = 0 ]; then
  [ -f $SC/lang_build.py.pre_d23 ] || cp $SC/lang_build.py $SC/lang_build.py.pre_d23
  [ -f $SC/lang_test.py.pre_d23 ] || cp $SC/lang_test.py $SC/lang_test.py.pre_d23
  [ -d $W/cache.pre_d23 ] || cp -a $W/cache $W/cache.pre_d23
  python3 $SC/d23_pl_patch.py $SC; PRC=$?
  python3 -m py_compile $SC/lang_build.py $SC/lang_test.py $SC/pl_quality.py && echo "compile OK" || PRC=8
  if [ $PRC != 0 ]; then cp $SC/lang_build.py.pre_d23 $SC/lang_build.py; cp $SC/lang_test.py.pre_d23 $SC/lang_test.py; echo "RESTORED the old files"; fi
fi
echo "patch rc=$PRC (0 = patched or already patched)"
echo "== 4 audit: how much of the existing translation fails the new rules (no model calls)"
ARC=9
if [ $PRC = 0 ]; then
  . $SC/lang_ctl.sh >/dev/null 2>&1
  fetch
  rm -rf /tmp/pl_audit; mkdir -p /tmp/pl_audit
  for L in hi ar pt es; do
    PL_AUDIT=1 python3 $SC/lang_build.py $ORIG $L /tmp/pl_audit/$L $CACHE > /tmp/pl_audit/log_$L.txt 2>&1
    echo "-- $L (build rc=$?)"
    python3 - /tmp/pl_audit/$L/BUILD_REPORT.json <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    st = d.get("stats", {})
    print("   blocks kept from cache: %s (fixed by the deterministic rules: %s) | would be redone: %s" % (st.get("cache", 0), st.get("cache_fixed", 0), st.get("audit_redo", 0)))
    print("   reasons: %s" % {k: v for k, v in st.items() if k.startswith("cache_rej_")})
    print("   errors: %s | missing: %s" % (d.get("errors"), d.get("missing")))
    for a in d.get("audit", [])[:14]:
        print("   REDO [%s] %s | %s" % (a.get("kind"), a.get("why"), a.get("src")))
except Exception as e:
    print("   no report:", e)
PY
  done
  ARC=0
fi
echo "== 5 stage 2 (waits for the Kaggle kernel, then rebuilds one language at a time, tests, deploys, uploads status/PL_FIX_D23*.md)"
if [ $ARC = 0 ]; then
  cp $SC/pl_quality.py $SC/d23_pl_patch.py $SC/d23_pl_stage2.sh $SC/lang_build.py $SC/lang_test.py $HQDIR/scripts/pl/ 2>/dev/null
  pkill -f d23_pl_stage2.sh 2>/dev/null; sleep 1
  nohup setsid bash $SC/d23_pl_stage2.sh > /tmp/d23_pl_stage2.out 2>&1 &
  sleep 3
  echo "stage 2 pid: $(pgrep -f d23_pl_stage2.sh | head -1 || echo NOT-RUNNING)"
  echo "kernel now: $(kaggle kernels status samarthkulkarni16/long-form-editor-clipper 2>&1 | tr -d '\n')"
else
  echo "stage 2 NOT started (see the lines above); the live sites are untouched"
fi
} 2>&1 | sed -E 's/(ghp_|github_pat_|gho_|hf_|sk-)[A-Za-z0-9_-]+/[REDACTED]/g; s/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/x.x.x.x/g' | iconv -c -f utf-8 -t ascii//TRANSLIT | head -c 60000 > $PASTE
up $PASTE status/CEO_PASTE_D23_B_$(date +%H%M).md
echo "Now type: check"
