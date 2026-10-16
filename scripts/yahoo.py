"""Shared Yahoo Fantasy API helpers for the GitHub Action (no browser login)."""
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
API = "https://fantasysports.yahooapis.com/fantasy/v2"
PAUSE = 0.7


def access_token():
    cid, sec, ref = (os.environ.get(k, "").strip() for k in ("YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET", "YAHOO_REFRESH_TOKEN"))
    if not (cid and sec and ref):
        sys.exit("Missing YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET or YAHOO_REFRESH_TOKEN secret.")
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    req = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode({
        "grant_type": "refresh_token", "redirect_uri": "https://localhost:8080/callback", "refresh_token": ref,
    }).encode(), headers={"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit("Yahoo refused the refresh token: " + e.read().decode()[:300])
    if tok.get("refresh_token") and tok["refresh_token"] != ref:
        print("NOTE: Yahoo issued a new refresh token. If future runs fail, update the YAHOO_REFRESH_TOKEN secret.")
    return tok["access_token"]


class Api:
    def __init__(self):
        self.tok = access_token()

    def get(self, path, tries=4):
        url = f"{API}/{path}" + ("&" if "?" in path else "?") + "format=json"
        for attempt in range(tries):
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.tok})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    time.sleep(PAUSE)
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    self.tok = access_token(); continue
                if e.code in (429, 500, 502, 503, 999):
                    time.sleep(5 * (attempt + 1)); continue
                print(f"  skip {path}: HTTP {e.code}")
                return None
            except Exception as err:
                time.sleep(3)
                if attempt == tries - 1:
                    print(f"  skip {path}: {err}")
                    return None
        return None


def find(obj, key):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(v) if k == key else out.extend(find(v, key))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(find(v, key))
    return out


def first(obj, key, default=None):
    v = find(obj, key)
    return v[0] if v else default


def pull_league(api, key, name, season):
    print(f"Pulling {season} {name} ({key})")
    out = {"league_key": key, "name": name, "season": str(season)}
    settings = api.get(f"league/{key}/settings")
    s = first(settings, "settings") or {}
    if isinstance(s, list):
        s = s[0] if s else {}
    out["is_finished"] = first(settings, "is_finished")
    out["renew"] = first(settings, "renew")
    out["settings"] = {
        "scoring_type": first(settings, "scoring_type"),
        "start_week": first(settings, "start_week"), "end_week": first(settings, "end_week"),
        "playoff_start_week": s.get("playoff_start_week"), "num_playoff_teams": s.get("num_playoff_teams"),
        "roster_positions": [{"position": p.get("position"), "count": p.get("count")}
                             for p in [x.get("roster_position", x) for x in s.get("roster_positions", [])] if isinstance(p, dict)],
    }
    teams = api.get(f"league/{key}/teams")
    out["teams"] = [{"team_key": first(t, "team_key"), "name": first(t, "name"),
                     "managers": [m.get("nickname") for m in find(t, "manager") if isinstance(m, dict)]}
                    for t in find(teams, "team") if first(t, "team_key")]
    standings = api.get(f"league/{key}/standings")
    out["standings"] = []
    for t in find(standings, "team"):
        tk = first(t, "team_key")
        if not tk:
            continue
        o = first(t, "team_standings") or {}
        w = first(o, "outcome_totals") or {}
        out["standings"].append({"team_key": tk, "rank": o.get("rank"), "wins": w.get("wins"), "losses": w.get("losses"),
                                 "ties": w.get("ties"), "points_for": o.get("points_for"), "points_against": o.get("points_against"),
                                 "playoff_seed": o.get("playoff_seed")})
    try:
        end_week = int(out["settings"]["end_week"] or 17)
    except (TypeError, ValueError):
        end_week = 17
    out["matchups"] = []
    for week in range(1, end_week + 1):
        sb = api.get(f"league/{key}/scoreboard;week={week}")
        for m in find(sb, "matchup") if sb else []:
            keys = find(m, "team_key")
            pts = [p.get("total") for p in find(m, "team_points") if isinstance(p, dict)]
            if len(keys) >= 2 and len(pts) >= 2:
                out["matchups"].append({"week": week, "teams": keys[:2], "points": pts[:2],
                                        "status": first(m, "status"), "winner": first(m, "winner_team_key"),
                                        "is_playoffs": first(m, "is_playoffs"), "is_consolation": first(m, "is_consolation")})
    out["rosters"] = []
    return out
