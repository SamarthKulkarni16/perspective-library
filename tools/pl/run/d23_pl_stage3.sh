#!/bin/bash
# D23 (CEO 2026-10-23) Perspective Library round 2: install patch 2 (heading rule fix + fixed headings + term fixes), self-test OFFLINE, then rebuild/test/deploy all four sites
# (stage 2 in the background, no waiting: the Kaggle kernel is finished). Results: status/PL_FIX_D23.md, status/PL_FIX_D23_REVIEW.md, status/PL_FIX_D23_PROGRESS.md
# Run:  gh api repos/SamarthKulkarni16/hq/contents/run/d23_pl_stage3.sh -H "Accept: application/vnd.github.raw" > /tmp/d23_pl_stage3.sh && bash /tmp/d23_pl_stage3.sh
export PATH=$PATH:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin
OWN=SamarthKulkarni16
W=/home/ubuntu/work/pl
SC=$W/scripts
PASTE=/tmp/ceo_out.txt
HQDIR=/home/ubuntu/hq
SLUG=samarthkulkarni16/long-form-editor-clipper
up() { S=$(gh api "repos/SamarthKulkarni16/hq/contents/$2" --jq .sha 2>/dev/null); gh api -X PUT "repos/SamarthKulkarni16/hq/contents/$2" -f message="ceo paste $(date +%H:%M)" -f content="$(base64 -w0 "$1")" ${S:+-f sha="$S"} --jq '.commit.sha' >/dev/null 2>&1 && echo "UPLOADED $2" || echo "FAILED $2"; }
raw() { gh api "repos/$OWN/hq/contents/$1" -H "Accept: application/vnd.github.raw" > "$2" 2>/dev/null && [ -s "$2" ]; }
{
echo "== NOW $(date '+%F %H:%M IST')"
echo "== 1 download patch 2"
OK=1
if raw scripts/pl/d23_pl_patch2.py $SC/d23_pl_patch2.py.new; then mv $SC/d23_pl_patch2.py.new $SC/d23_pl_patch2.py; echo "got d23_pl_patch2.py ($(wc -c < $SC/d23_pl_patch2.py) bytes)"; else echo "FAILED to download"; OK=0; fi
echo "== 2 apply patch 2 to pl_quality.py and self-test"
RC=9
if [ $OK = 1 ]; then
  [ -f $SC/pl_quality.py.pre_patch2 ] || cp $SC/pl_quality.py $SC/pl_quality.py.pre_patch2
  python3 $SC/d23_pl_patch2.py $SC && python3 -m py_compile $SC/pl_quality.py && python3 $SC/pl_quality.py selftest 2>&1 | grep -E 'FAIL|RESULT|==' ; python3 $SC/pl_quality.py selftest >/dev/null 2>&1; RC=$?
  if [ $RC != 0 ]; then cp $SC/pl_quality.py.pre_patch2 $SC/pl_quality.py; echo "RESTORED the previous pl_quality.py"; fi
fi
echo "selftest rc=$RC (0 = every rule behaves)"
echo "== 3 rebuild all four sites (background)"
if [ $RC = 0 ]; then
  cp $SC/pl_quality.py $SC/d23_pl_patch2.py $HQDIR/scripts/pl/ 2>/dev/null
  pkill -f d23_pl_stage2.sh 2>/dev/null; sleep 1
  PL_NOWAIT=1 nohup setsid bash $SC/d23_pl_stage2.sh > /tmp/d23_pl_stage2.out 2>&1 &
  sleep 3
  echo "stage 2 pid: $(pgrep -f d23_pl_stage2.sh | head -1 || echo NOT-RUNNING)"
  echo "kernel now: $(kaggle kernels status $SLUG 2>&1 | tr -d '\n')"
else
  echo "NOT started (see above); the live sites are untouched"
fi
} 2>&1 | sed -E 's/(ghp_|github_pat_|gho_|hf_|sk-)[A-Za-z0-9_-]+/[REDACTED]/g; s/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/x.x.x.x/g' | iconv -c -f utf-8 -t ascii//TRANSLIT | head -c 60000 > $PASTE
up $PASTE status/CEO_PASTE_D23_D_$(date +%H%M).md
echo "Now type: check"
