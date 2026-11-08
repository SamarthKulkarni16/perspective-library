# Language-site tooling (moved from the hq repo on 2026-11-08)

Builds the four translated copies of this site (perspective-library-hi, -ar, -pt, -es) from this repo's index.html. The language repos are generated: never edit them by hand.

- `lang_build.py` builds one language, `lang_test.py` tests it, `pl_quality.py` holds the quality rules and a selftest.
- `lang_ctl.sh` is the controller (preflight | fetch | run | go | sync | shots | report). It runs on the Oracle VM from `/home/ubuntu/work/pl/scripts/` and a 10-minute cron calls `lang_ctl.sh sync`. Sync status is written to `tools/pl/status/PL_SYNC_LATEST.md` in this repo.
- `deeplink_patch.py`, `deeplink_test.py`: per-book URLs (#book/slug).
- `d23_pl_*.py`, `run/d23_pl_stage*.sh`, `status-logs/`: one-off fix scripts and logs from 2026-10-20 to 2026-10-23 (history).

Full rebuild on the VM: `PL_NOWAIT=1 bash /home/ubuntu/work/pl/scripts/d23_pl_stage2.sh`
