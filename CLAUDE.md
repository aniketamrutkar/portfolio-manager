# Portfolio Manager (Broking-Data)

Indian-equity research app: a Python pipeline builds data on NSE/BSE stocks, and step 18 embeds it into one self-contained
HTML app, `Portfolio_Manager.html`, published on GitHub Pages (https://aniketamrutkar.github.io/portfolio-manager/).
See `README.md` for the full pipeline and data dictionary.

## Working here
- Python: `.venv/bin/python` (system python3 has no pandas). Steps live in `pipeline/` and run from that folder, in numeric order (`run_all.sh`).
- App UI = `pipeline/portfolio_template.html`. After editing it, rebuild with `cd pipeline && ../.venv/bin/python 18_build_html.py`.
  Never hand-edit `Portfolio_Manager.html`.
- Tests: open the app with `#selftest`. Headless:
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --virtual-time-budget=30000 --dump-dom "file://$PWD/Portfolio_Manager.html#selftest"`
  and count the `PASS` / `FAIL` lines. Add a self-test check for each new UI feature.
- Deploy = push `main` (GitHub Pages serves the repo root). The repo is **public**: never commit tokens, broker data
  (Angel One / Trendlyne, which is licensed for personal use only) or `pipeline/bhav_hist/` (651 MB NSE history, git-ignored-worthy).
  Commit and push only when the user asks.
- The user's shortlist / marks live in their browser; exports are `~/Downloads/portfolio_state_<date> (n).json` (newest = highest n).
- Returns use fixed start dates (first trading day of October each year) to the data date, the same in every tab: 1/2/3/4/5Y.

## Session history
Handled globally for every folder by `~/.claude/hooks/session-history/` (hooks in `~/.claude/settings.json`): when a session ends its
transcript is copied to `.claude/sessions/` and a summary is added to `.claude/SESSION_LOG.md`; when a session starts the newest
summaries are given to Claude automatically. Both are git-ignored (public repo; transcripts can contain pasted secrets, never quote them).
