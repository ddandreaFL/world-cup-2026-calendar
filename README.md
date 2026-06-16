# World Cup 2026 Calendar

A subscribable `.ics` calendar of every 2026 FIFA World Cup match, with live
scores, goal scorers, assists, and cards pulled from ESPN's public feeds. A
GitHub Action regenerates it every 15 minutes.

## Subscribe

- iPhone (tap to subscribe): `webcal://<OWNER>.github.io/<REPO>/world_cup_2026.ics`
- Anywhere else: `https://<OWNER>.github.io/<REPO>/world_cup_2026.ics`

In macOS Calendar: **File → New Calendar Subscription**, paste the `https://`
URL, set auto-refresh to 15 min.

In Google Calendar: **Other calendars → From URL**, paste the `https://` URL.

## How it works

- `generate.py` walks every day from 2026-06-11 to 2026-07-19, hits ESPN's
  scoreboard for that date, and for any non-pre match also hits ESPN's match
  summary to pull goals, assists, and cards. Output goes to
  `docs/world_cup_2026.ics`.
- `.github/workflows/update.yml` runs every 15 minutes, regenerates, and
  commits only when the calendar actually changed.
- GitHub Pages serves `docs/` so calendar clients can subscribe.

Stdlib only — no `pip install` needed.

## Local run

```
python3 generate.py
```

## After the tournament

The script self-skips after 2026-07-20. You can also disable the workflow in
the Actions tab.
