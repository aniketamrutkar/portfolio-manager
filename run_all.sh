#!/usr/bin/env bash
# Broking-Data pipeline runner. Run from anywhere.
#   ./run_all.sh            rebuild all deliverables from the data already in pipeline/ (offline, ~30 s)
#   ./run_all.sh --refresh  download latest exchange files, wipe raw/*.json, re-fetch everything (~1-1.5 h), rebuild
#   ./run_all.sh --resume   continue an interrupted/throttled fetch (keeps what is already fetched), then rebuild
# Python: uses $PYTHON if set, else .venv/bin/python if present, else python3.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then [[ -x "$ROOT/.venv/bin/python" ]] && PY="$ROOT/.venv/bin/python" || PY=python3; fi
cd "$ROOT/pipeline"
MODE="${1:-}"
FETCH=(01_fetch_nse_equities 02_fetch_nifty500_deep 03_fetch_nse_promoter 04_fetch_etf_reit_invit 05_fetch_bse_only)
BUILD=(10_build_nse_base 11_build_universe 12_build_screen_and_picks 13_build_etf_lists 14_backtest 15_sector_returns 16_sector_picks 17_sector_top10_v3 18_build_html)

if [[ "$MODE" == "--refresh" ]]; then
  "$PY" 00_download_inputs.py
  rm -f raw.json raw2.json raw3.json raw_other.json raw_bse2.json
fi
if [[ "$MODE" == "--refresh" || "$MODE" == "--resume" ]]; then
  for s in "${FETCH[@]}"; do
    echo "=== $s"; "$PY" "$s.py"
    "$PY" "$s.py"        # second pass: resumable, retries only what failed (usually Yahoo throttling)
  done
elif [[ -n "$MODE" ]]; then
  echo "unknown option $MODE (use --refresh or --resume)"; exit 2
fi
for s in "${BUILD[@]}"; do echo "=== $s"; "$PY" "$s.py"; done
echo "Done. Deliverables are in $ROOT"
