"""Weird and wild stats, computed from every game and lineup. Used by build.py."""
from collections import defaultdict
import statistics

NAMES = {}  # filled by build.py with key -> full name


def nm(k):
    return " & ".join(NAMES.get(x, x) for x in k.split("+"))


def owners(side):
    return side.split("+")


def f2(x):
    return f"{x:,.2f}"


def card(sec, t, v, who, ctx, cls=""):
    return {"sec": sec, "t": t, "v": v, "who": who, "ctx": ctx, "cls": cls}


def top_people(counter):
    if not counter:
        return 0, []
    m = max(counter.values())
    return m, sorted(k for k, v in counter.items() if v == m)


def ties(d, pick):
    v = pick(d.values())
    return v, sorted(k for k, x in d.items() if round(x, 3) == round(v, 3))


def credit(counter, side, n=1):
    for o in owners(side):
        counter[o] += n


def eligible(pos):
    return set((pos or "").replace(" ", "").split(","))


def optimal(players, slots):
    """Best possible starting lineup under that season's slots (greedy, flex last)."""
    pool = [(p[3] or 0, eligible(p[1]), i) for i, p in enumerate(players) if p[2] != "IR"]
    pool.sort(key=lambda x: -x[0])
    used, total = set(), 0.0
    order = [s for s in slots if s[0] not in ("W/R/T",)] + [s for s in slots if s[0] == "W/R/T"]
    for pos, cnt in order:
        ok = {"RB", "WR", "TE"} if pos == "W/R/T" else {pos}
        for _ in range(cnt):
            for pts, el, i in pool:
                if i not in used and el & ok:
                    used.add(i)
                    total += pts
                    break
    return round(total, 2)


def compute(G, LU, S, SLOTS):
    """G: [y,w,a,b,pa,pb,k]; LU[y][week][side] = [[name,pos,slot,pts],...]; S: season rows; SLOTS[y] = [(pos,count)]"""
    out = []
    sides = []  # one row per team per game
    for y, w, a, b, pa, pb, k in G:
        sides.append(dict(y=y, w=w, s=a, o=b, p=pa, op=pb, k=k))
        sides.append(dict(y=y, w=w, s=b, o=a, p=pb, op=pa, k=k))
    weeks = defaultdict(list)
    for r in sides:
        if r["k"] == "r":
            weeks[(r["y"], r["w"])].append(r)

    # ---------- Luck
    exp = defaultdict(float); act = defaultdict(int); ng = defaultdict(int)
    buzz = defaultdict(int); steal = defaultdict(int)
    for (y, w), rs in weeks.items():
        sc = sorted((r["p"] for r in rs), reverse=True)
        top = sc[0]
        for r in rs:
            beat = sum(1 for x in rs if x is not r and r["p"] > x["p"])
            key = (y, r["s"])
            exp[key] += beat / (len(rs) - 1)
            act[key] += r["p"] > r["op"]
            ng[key] += 1
            if r["op"] == top and r["p"] < r["op"] and r["p"] >= sc[2]:
                credit(buzz, r["s"])
            if r["p"] > r["op"] and r["p"] <= sc[-3]:
                credit(steal, r["s"])
    luck = {k: act[k] - exp[k] for k in exp if k[0] <= max(r["year"] for r in S)}
    if luck:
        k = min(luck, key=luck.get)
        out.append(card("Luck", "Most robbed season", f"{luck[k]:+.1f} wins", owners(k[1]),
                        f"{k[0]}: went {act[k]}-{ng[k]-act[k]}, but scored like a {exp[k]:.1f} win team against the whole league", "bad"))
        k = max(luck, key=luck.get)
        out.append(card("Luck", "Luckiest season", f"{luck[k]:+.1f} wins", owners(k[1]),
                        f"{k[0]}: went {act[k]}-{ng[k]-act[k]} while scoring like a {exp[k]:.1f} win team", "gold"))
    career = defaultdict(float)
    for (y, s), v in luck.items():
        for o in owners(s):
            career[o] += v
    if career:
        v, ks = ties(career, min)
        out.append(card("Luck", "Unluckiest career", f"{v:+.1f} wins", ks, "Wins below what their weekly scores deserved, every regular season combined", "bad"))
        v, ks = ties(career, max)
        out.append(card("Luck", "Luckiest career", f"{v:+.1f} wins", ks, "Wins above what their weekly scores deserved, every regular season combined", "gold"))
    m, who = top_people(buzz)
    if m:
        out.append(card("Luck", "Ran into a buzzsaw", str(m), who, "Times they posted a top 3 score of the week and still lost, because their opponent had the week's best", "bad"))
    m, who = top_people(steal)
    if m:
        out.append(card("Luck", "Stole one", str(m), who, "Wins with one of the three lowest scores in the league that week", "gold"))

    # ---------- Lineups
    if LU:
        opt_left = defaultdict(float); lost_bench = defaultdict(int); perfect = defaultdict(int)
        zeros = defaultdict(int); kick = defaultdict(int); start_ct = defaultdict(int); roster_ct = defaultdict(int)
        eff_act = defaultdict(float); eff_opt = defaultdict(float)
        worst_flip = None; best_bench = None; best_start = None; worst_start = None; carry = None
        for r in sides:
            L = LU.get(r["y"], {}).get(r["w"], {})
            ps, ops = L.get(r["s"]), L.get(r["o"])
            if not ps:
                continue
            st = [p for p in ps if p[2] not in ("BN", "IR")]
            bn = [p for p in ps if p[2] == "BN"]
            opt = optimal(ps, SLOTS.get(r["y"], []))
            left = max(0.0, opt - r["p"])
            opt_left[(r["y"], r["s"])] += left
            for o in owners(r["s"]):
                eff_act[o] += r["p"]; eff_opt[o] += max(opt, r["p"])
            if abs(opt - r["p"]) < 0.05:
                credit(perfect, r["s"])
            if r["p"] < r["op"] and opt > r["op"]:
                credit(lost_bench, r["s"])
                flip = opt - r["op"]
                if not worst_flip or flip > worst_flip[0]:
                    worst_flip = (flip, r, opt)
            for p in st:
                pts = p[3] if p[3] is not None else 0
                if pts <= 0 and p[1] not in ("DEF",):
                    credit(zeros, r["s"])
                for o in owners(r["s"]):
                    start_ct[(o, p[0])] += 1
                if not best_start or pts > best_start[0]:
                    best_start = (pts, p, r)
                if not worst_start or pts < worst_start[0]:
                    worst_start = (pts, p, r)
                if r["p"] > 0 and (not carry or pts / r["p"] > carry[0]):
                    carry = (pts / r["p"], p, r)
            for p in ps:
                roster_ct[p[0]] += 1
            for p in bn:
                pts = p[3] or 0
                if not best_bench or pts > best_bench[0]:
                    best_bench = (pts, p, r)
            sts = [p for p in st if p[3] is not None]
            if sts and max(sts, key=lambda p: p[3])[1] == "K":
                credit(kick, r["s"])
        if worst_flip:
            flip, r, opt = worst_flip
            out.append(card("Lineup blunders", "Most costly lineup", f"lost by {f2(r['op']-r['p'])}", owners(r["s"]),
                            f"{r['y']} week {r['w']} vs {nm(r['o'])}: the best lineup on their own roster would have scored {f2(opt)} and won by {f2(flip)}", "bad"))
        m, who = top_people(lost_bench)
        if m:
            out.append(card("Lineup blunders", "Lost with a winner on the bench", str(m), who, "Losses where a better lineup from their own roster would have won", "bad"))
        k = max(opt_left, key=opt_left.get)
        out.append(card("Lineup blunders", "Most points left on the bench, one season", f2(opt_left[k]), owners(k[1]), f"{k[0]}, compared with the best possible lineup every week", "bad"))
        if best_bench:
            pts, p, r = best_bench
            out.append(card("Lineup blunders", "Biggest game on the bench", f2(pts), owners(r["s"]),
                            f"{p[0]} ({p[1]}) sat on the bench in {r['y']} week {r['w']}. They {'still won' if r['p']>r['op'] else 'lost'}, {f2(r['p'])} to {f2(r['op'])}", "bad"))
        m, who = top_people(zeros)
        if m:
            out.append(card("Lineup blunders", "Started a zero", str(m), who, "Starters who scored zero or less, usually a bye week or a scratch nobody caught", "bad"))
        eff = {o: eff_act[o] / eff_opt[o] for o in eff_opt if eff_opt[o] > 5000}
        if eff:
            v, ks = ties(eff, max)
            out.append(card("Lineup blunders", "Lineup genius", f"{v*100:.1f}%", ks, "Share of the best possible points they actually started, every game combined", "gold"))
            v, ks = ties(eff, min)
            out.append(card("Lineup blunders", "Set it and forget it", f"{v*100:.1f}%", ks, "Lowest share of the best possible points actually started", "bad"))
        m, who = top_people(perfect)
        if m:
            out.append(card("Lineup blunders", "Most perfect lineups", str(m), who, "Weeks where they started the best possible lineup on their roster", "gold"))

        if best_start:
            pts, p, r = best_start
            out.append(card("Players", "Best single game by a starter", f2(pts), owners(r["s"]), f"{p[0]} ({p[1]}), {r['y']} week {r['w']} vs {nm(r['o'])}", "gold"))
        if carry:
            sh, p, r = carry
            out.append(card("Players", "Biggest carry job", f"{sh*100:.0f}%", owners(r["s"]),
                            f"{p[0]} scored {f2(p[3])} of the team's {f2(r['p'])} in {r['y']} week {r['w']}, and they {'won' if r['p']>r['op'] else 'lost anyway'}", "gold"))
        if worst_start:
            pts, p, r = worst_start
            out.append(card("Players", "Worst start ever", f2(pts), owners(r["s"]), f"{p[0]} ({p[1]}), {r['y']} week {r['w']}", "bad"))
        m, who = top_people(kick)
        if m:
            out.append(card("Players", "Kicker was the MVP", str(m), who, "Weeks where their kicker was the team's top scoring starter"))
        (o, pl), n = max(start_ct.items(), key=lambda kv: kv[1])
        out.append(card("Players", "Ride or die", f"{n} starts", [o], f"{pl}, the most one manager has ever started a single player"))
        pl, n = max(roster_ct.items(), key=lambda kv: kv[1])
        out.append(card("Players", "The league's favorite player", f"{n} weeks", [], f"{pl} has been on someone's roster more weeks than anyone else"))

    # ---------- Oddities
    games = [r for r in sides]
    lowc = min(G, key=lambda g: g[4] + g[5])
    out.append(card("Oddities", "Snoozefest", f2(lowc[4] + lowc[5]), owners(lowc[2]) + owners(lowc[3]),
                    f"Lowest combined score ever: {nm(lowc[2])} {f2(lowc[4])}, {nm(lowc[3])} {f2(lowc[5])}, {lowc[0]} week {lowc[1]}", "bad"))
    spread = max(weeks.items(), key=lambda kv: max(r["p"] for r in kv[1]) - min(r["p"] for r in kv[1]))
    (y, w), rs = spread
    hi = max(rs, key=lambda r: r["p"]); lo = min(rs, key=lambda r: r["p"])
    out.append(card("Oddities", "Widest week", f2(hi["p"] - lo["p"]), owners(hi["s"]) + owners(lo["s"]),
                    f"{y} week {w}: {nm(hi['s'])} scored {f2(hi['p'])} while {nm(lo['s'])} scored {f2(lo['p'])}"))
    per = defaultdict(list)
    for r in sides:
        if r["k"] == "r":
            per[(r["y"], r["s"])].append(r["p"])
    sd = {k: statistics.pstdev(v) for k, v in per.items() if len(v) >= 10}
    k = min(sd, key=sd.get)
    out.append(card("Oddities", "Mr. Consistent", f"±{sd[k]:.1f}", owners(k[1]), f"Steadiest weekly scoring of any season, {k[0]}"))
    k = max(sd, key=sd.get)
    out.append(card("Oddities", "Rollercoaster", f"±{sd[k]:.1f}", owners(k[1]), f"Wildest week to week swings of any season, {k[0]}"))
    big = defaultdict(int)
    for r in sides:
        if r["p"] >= 150:
            credit(big, r["s"])
    m, who = top_people(big)
    if m:
        out.append(card("Oddities", "150 club", str(m), who, "Most games of 150 points or more", "gold"))

    # streaks across seasons, every non consolation game in order
    seq = defaultdict(list)
    for r in sorted(sides, key=lambda r: (r["y"], r["w"])):
        if r["k"] == "c":
            continue
        for o in owners(r["s"]):
            seq[o].append((r["p"] > r["op"], r["y"], r["w"]))
    def longest(won):
        best = (0, None, None, None)
        for o, s in seq.items():
            run = 0; start = None
            for v, y, w in s:
                if v == won:
                    run += 1
                    start = start or (y, w)
                    if run > best[0]:
                        best = (run, o, start, (y, w))
                else:
                    run = 0; start = None
        return best
    n, o, a, b = longest(True)
    out.append(card("Streaks", "Longest win streak", f"W{n}", [o], f"From {a[0]} week {a[1]} to {b[0]} week {b[1]}", "gold"))
    n, o, a, b = longest(False)
    out.append(card("Streaks", "Longest losing streak", f"L{n}", [o], f"From {a[0]} week {a[1]} to {b[0]} week {b[1]}", "bad"))

    # rivalries
    h2h = defaultdict(lambda: [0, 0])
    for r in sides:
        for o in owners(r["s"]):
            for p in owners(r["o"]):
                h2h[(o, p)][0 if r["p"] > r["op"] else 1] += 1
    cand = [(v[0] / (v[0] + v[1]), v[0], v[1], k) for k, v in h2h.items() if v[0] + v[1] >= 8]
    if cand:
        pc, w_, l_, (a, b) = max(cand, key=lambda x: (x[0], x[1]))
        out.append(card("Streaks", "Owns them", f"{w_}-{l_}", [a, b], f"{NAMES.get(a,a)} against {NAMES.get(b,b)}, the most lopsided rivalry with 8 or more games", "gold"))

    # playoff upsets
    seed = {(r["year"], "+".join(r["owners"])): r["seed"] for r in S}
    ups = []
    for y, w, a, b, pa, pb, k in G:
        if k != "p" or (y, a) not in seed or (y, b) not in seed:
            continue
        win, lose = (a, b) if pa > pb else (b, a)
        ups.append((seed[(y, win)] - seed[(y, lose)], y, w, win, lose))
    if ups:
        d, y, w, win, lose = max(ups)
        if d > 0:
            out.append(card("Streaks", "Biggest playoff upset", f"#{seed[(y,win)]} over #{seed[(y,lose)]}", owners(win), f"{nm(win)} knocked out {nm(lose)}, {y} week {w}", "gold"))

    # team name loyalty
    names = defaultdict(lambda: defaultdict(set))
    for r in S:
        names["+".join(r["owners"])][r["team"].strip().lower().replace("’", "'")].add(r["year"])
    best = max(((len(ys), k, n_) for k, d in names.items() for n_, ys in d.items()))
    real = next(r["team"] for r in S if "+".join(r["owners"]) == best[1] and r["team"].strip().lower().replace("’", "'") == best[2])
    out.append(card("Oddities", "Never changed the name", f"{best[0]} seasons", owners(best[1]), f"{real}"))
    return out
