"""Refresh the current season from Yahoo, add next season once the league renews,
and fill in any missing weekly lineups (the first run backfills every season)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from yahoo import Api, find, first, pull_league, pull_rosters, played_weeks

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "league_data.json")


def save(data, leagues):
    data["leagues"] = leagues
    json.dump(data, open(DATA, "w"), ensure_ascii=False, separators=(",", ":"))


data = json.load(open(DATA))
leagues = sorted(data["leagues"], key=lambda L: int(L["season"]))
api = Api()

latest = leagues[-1]
mine = api.get("users;use_login=1/games;game_codes=nfl/leagues")
renew_id = latest["league_key"].replace(".l.", "_")
for lg in find(mine, "league"):
    if first(lg, "renew") == renew_id and not any(L["league_key"] == first(lg, "league_key") for L in leagues):
        print("Found next season:", first(lg, "season"), first(lg, "name"))
        leagues.append({"league_key": first(lg, "league_key"), "name": first(lg, "name"), "season": str(first(lg, "season"))})

newest = int(leagues[-1]["season"])
for i, L in enumerate(leagues):
    finished = str(L.get("is_finished")) == "1" or ("matchups" in L and int(L["season"]) < newest - 1)
    old = {(r["team_key"], r["week"]): r for r in L.get("rosters", [])}
    if not finished:
        L = leagues[i] = pull_league(api, L["league_key"], L["name"], L["season"])
        old = {}  # current season: refresh every finished week, scores can be corrected
    weeks = set(played_weeks(L))
    if finished and old and {w for (_, w) in old} >= weeks:
        continue
    L["rosters"] = pull_rosters(api, L, old)
    save(data, leagues)  # save after each season so progress is never lost

save(data, leagues)
print("Saved", len(leagues), "seasons")
