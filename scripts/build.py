"""Build site/index.html from the template, the fixed 2017 to 2025 history and the Yahoo data."""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
static = json.load(open(os.path.join(ROOT, "data", "seasons_static.json")))
data = json.load(open(os.path.join(ROOT, "data", "league_data.json")))
tpl = open(os.path.join(ROOT, "site", "template.html")).read()

# Yahoo manager nickname -> site key, for seasons after the spreadsheet history.
MANAGERS = {"joshua": "josh", "Ethan": "sinnreich", "Zach": "younger", "Mitch": "mitch", "Ben": "huppert",
            "Nate": "nate", "David": "david", "Brandon": "brandon", "Jacob": "zuck", "Sammy": "maryles"}
CO_TEAM = "daniel+shap+maryles"  # any team managed by Daniel


def owners_for(season, team, static_years):
    if season in static_years:
        rows = [r for r in static if r["year"] == season and r["team"].strip() == team["name"].strip()]
        if not rows:
            raise SystemExit(f"Could not match {season} team {team['name']!r} to the history data")
        return "+".join(rows[0]["owners"])
    if "Daniel" in team["managers"]:
        return CO_TEAM
    for m in team["managers"]:
        if m in MANAGERS:
            return MANAGERS[m]
    raise SystemExit(f"Unknown manager {team['managers']} on {season} team {team['name']!r}. Add them to MANAGERS in scripts/build.py")


static_years = {r["year"] for r in static}
S = list(static)
G, NX, unfinished, LU = [], {}, [], {}
for L in sorted(data["leagues"], key=lambda L: int(L["season"])):
    y = int(L["season"])
    po = int(L["settings"]["playoff_start_week"])
    side = {t["team_key"]: owners_for(y, t, static_years) for t in L["teams"]}
    names = {side[t["team_key"]]: t["name"] for t in L["teams"]}
    for r in L.get("rosters", []):
        LU.setdefault(y, {}).setdefault(str(r["week"]), {})[side[r["team_key"]]] = r["players"]
    for m in L["matchups"]:
        a, b = m["teams"]
        pa, pb = float(m["points"][0] or 0), float(m["points"][1] or 0)
        done = m.get("status") == "postevent" if m.get("status") else (pa or pb)
        if not done or (pa == 0 and pb == 0):
            continue
        k = "r" if m["week"] < po else ("c" if str(m["is_consolation"]) == "1" else "p")
        G.append([y, m["week"], side[a], side[b], round(pa, 2), round(pb, 2), k])
    if y in static_years:
        continue
    if str(L.get("is_finished")) == "1":
        npo = int(L["settings"].get("num_playoff_teams") or 6)
        st = {s["team_key"]: s for s in L["standings"]}
        for t in L["teams"]:
            s = st[t["team_key"]]
            seed = int(s.get("playoff_seed") or 0)
            S.append({"year": y, "rank": int(s["rank"]), "seed": seed, "playoffs": 0 < seed <= npo, "team": t["name"],
                      "w": int(s["wins"]), "l": int(s["losses"]), "t": int(s["ties"] or 0),
                      "pf": float(s["points_for"]), "pa": float(s["points_against"]),
                      "streak": "-", "waiver": "-", "faab_left": "-", "moves": "-",
                      "owners": side[t["team_key"]].split("+"), "prov": False})
    else:
        unfinished.append(y)
        NX[y] = names

S.sort(key=lambda r: (r["year"], r["rank"]))
cur = max(unfinished) if unfinished else 0
html = (tpl.replace("__S__", json.dumps(S, ensure_ascii=False, separators=(",", ":")))
           .replace("__G__", json.dumps(G, ensure_ascii=False, separators=(",", ":")))
           .replace("__NX__", json.dumps(NX, ensure_ascii=False, separators=(",", ":")))
           .replace("__CUR__", str(cur))
           .replace("__LY__", json.dumps(sorted(LU))))
os.makedirs(os.path.join(ROOT, "public"), exist_ok=True)
open(os.path.join(ROOT, "public", "index.html"), "w").write(html)
os.makedirs(os.path.join(ROOT, "public", "lineups"), exist_ok=True)
for yr, weeks in LU.items():
    json.dump(weeks, open(os.path.join(ROOT, "public", "lineups", f"{yr}.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(f"Built public/index.html: {len(S)} season rows, {len(G)} games, lineups for {sorted(LU)}, current season {cur or 'none'}")
