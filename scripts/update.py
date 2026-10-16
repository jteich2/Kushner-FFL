"""Refresh the current season from Yahoo, and add next season once the league renews."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from yahoo import Api, find, first, pull_league

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "league_data.json")

data = json.load(open(DATA))
leagues = sorted(data["leagues"], key=lambda L: int(L["season"]))
api = Api()

# Look for a renewal of the newest season (next year's league)
latest = leagues[-1]
mine = api.get("users;use_login=1/games;game_codes=nfl/leagues")
renew_id = latest["league_key"].replace(".l.", "_")
for lg in find(mine, "league"):
    if first(lg, "renew") == renew_id and not any(L["league_key"] == first(lg, "league_key") for L in leagues):
        print("Found next season:", first(lg, "season"), first(lg, "name"))
        leagues.append({"league_key": first(lg, "league_key"), "name": first(lg, "name"), "season": str(first(lg, "season"))})

# Re-pull every season that is not finished yet (normally just the current one)
for i, L in enumerate(leagues):
    if str(L.get("is_finished")) == "1" or ("matchups" in L and int(L["season"]) < int(leagues[-1]["season"]) - 1):
        continue
    leagues[i] = pull_league(api, L["league_key"], L["name"], L["season"])

data["leagues"] = leagues
json.dump(data, open(DATA, "w"), ensure_ascii=False, indent=1)
print("Saved", len(leagues), "seasons")
