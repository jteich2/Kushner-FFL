# Kushner FFL league history

The league history site. A GitHub Action pulls the latest scores from Yahoo every Tuesday morning, rebuilds the page and republishes it.

- `data/seasons_static.json`: final standings for 2017 to 2025 (from the spreadsheet, checked against Yahoo)
- `data/league_data.json`: every weekly game from Yahoo, updated automatically
- `site/template.html`: the page itself
- `scripts/update.py`: pulls the current season from Yahoo
- `scripts/build.py`: builds `public/index.html` from the template and data

## Updating by hand
Actions tab, then "Update league site", then "Run workflow".

## If a run fails
- **"Yahoo refused the refresh token"**: on your Mac, run the old `pull_yahoo.py` once to log in again, then copy the new refresh token into the `YAHOO_REFRESH_TOKEN` secret.
- **"Unknown manager"**: someone new joined. Add their Yahoo nickname to `MANAGERS` in `scripts/build.py`.
- **Scheduled runs stopped**: GitHub pauses schedules after 60 days with no activity, usually in the offseason. Turn it back on from the Actions tab.
