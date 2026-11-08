#!/bin/bash
# D23 (CEO 2026-10-23) Perspective Library round 3 (cosmetic leftovers): patch 3 + offline self-test, then rebuild/test/deploy all four sites (stage 2, background),
# and check by itself that the changed strings are really in the new build.
# Run:  gh api repos/SamarthKulkarni16/hq/contents/run/d23_pl_stage4.sh -H "Accept: application/vnd.github.raw" > /tmp/d23_pl_stage4.sh && bash /tmp/d23_pl_stage4.sh
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
OK=1
if raw scripts/pl/d23_pl_patch3.py $SC/d23_pl_patch3.py.new; then mv $SC/d23_pl_patch3.py.new $SC/d23_pl_patch3.py; echo "got patch 3 ($(wc -c < $SC/d23_pl_patch3.py) bytes)"; else echo "FAILED to download patch 3"; OK=0; fi
RC=9
if [ $OK = 1 ]; then
  [ -f $SC/pl_quality.py.pre_patch3 ] || cp $SC/pl_quality.py $SC/pl_quality.py.pre_patch3
  python3 $SC/d23_pl_patch3.py $SC && python3 -m py_compile $SC/pl_quality.py && python3 $SC/pl_quality.py selftest 2>&1 | grep -E 'FAIL|RESULT'
  python3 $SC/pl_quality.py selftest >/dev/null 2>&1; RC=$?
  if [ $RC != 0 ]; then cp $SC/pl_quality.py.pre_patch3 $SC/pl_quality.py; echo "RESTORED the previous pl_quality.py"; fi
fi
echo "selftest rc=$RC"
if [ $RC = 0 ]; then
  cp $SC/pl_quality.py $SC/d23_pl_patch3.py $HQDIR/scripts/pl/ 2>/dev/null
  PL_NOWAIT=1 bash $SC/d23_pl_stage2.sh > /tmp/d23_pl_stage2.out 2>&1
  echo "stage 2 finished: $(tail -n 1 /tmp/pl_fix_progress.txt)"
  echo "== string checks in the new builds (counts, expect >= 1 where marked)"
  echo "hi Anger subtitle uses tum (expect 1+): $(grep -c 'जब तक तुम जानते हो' $W/out/hi/index.html)"
  echo "hi Anger subtitle still has aap (expect 0): $(grep -c 'जब तक आप जानते हैं' $W/out/hi/index.html)"
  echo "hi Your Collection is tum (expect 1+): $(grep -c 'तुम्हारा संग्रह' $W/out/hi/index.html)"
  echo "ar procrastination title (expect 1+): $(grep -c 'استخدم التسويف لصالحك' $W/out/ar/index.html)"
  echo "ar old term in a title (expect 0): $(grep -c 'استخدم المماطلة لصالحك' $W/out/ar/index.html)"
  echo "pt Title Case heading left (expect 0): $(grep -c 'O Que Acontece de Verdade' $W/out/pt/index.html)"
  echo "ar Latin A. list mark left (expect 0): $(grep -c '>A\. القشرة' $W/out/ar/index.html)"
  echo "deploy lines:"; grep -E 'DEPLOYED|SKIP' /tmp/pl_fix_deploy.txt
else
  echo "NOT run (see above); the live sites are untouched"
fi
} 2>&1 | sed -E 's/(ghp_|github_pat_|gho_|hf_|sk-)[A-Za-z0-9_-]+/[REDACTED]/g; s/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/x.x.x.x/g' | iconv -c -f utf-8 -t ascii//TRANSLIT | head -c 60000 > $PASTE
up $PASTE status/CEO_PASTE_D23_E_$(date +%H%M).md
echo "Now type: check"
