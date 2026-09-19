#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Self-contained contribution stats card.

Replaces github-readme-stats and streak-stats, both of which are shared public
instances that rate-limit and return "Failed to retrieve contributions" or a
bare 503. Everything here is computed from the same public contributions page
the rollout grid uses, so there is no API token, no third-party host, and
nothing that can go down independently of GitHub itself.

Usage:  python stats_card.py [username]
Writes: stats-dark.svg, stats-light.svg
"""
import os, re, sys, html, datetime, urllib.request

USER = (sys.argv[1] if len(sys.argv) > 1 else "rewyekha")
OUT = os.environ.get("GH_OUT", os.path.dirname(os.path.abspath(__file__)))

W, H = 1180, 168
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    "dark": dict(bg="#0A0F1C", panel="#111A2E", stroke="#1E2C47", muted="#4A5A75",
                 label="#7C8FAB", num="#E2E8F0", accent="#38BDF8", ok="#34D399",
                 spark="#1E5F8C"),
    "light": dict(bg="#FFFFFF", panel="#F1F5F9", stroke="#D7DEE8", muted="#94A3B8",
                  label="#64748B", num="#0F172A", accent="#0369A1", ok="#047857",
                  spark="#7DD3FC"),
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_days(user):
    """[(date, count)] for the last year, oldest first."""
    url = "https://github.com/users/%s/contributions" % user
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")

    # id -> date, from the grid cells
    dates = {}
    for m in re.finditer(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"', page):
        dates[m.group(2)] = m.group(1)

    # id -> count, from the tooltips ("No contributions on ..." / "7 contributions on ...")
    counts = {}
    for m in re.finditer(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)', page):
        cid, txt = m.group(1), html.unescape(m.group(2)).strip()
        n = 0
        mm = re.match(r'^([\d,]+)\s+contribution', txt)
        if mm:
            n = int(mm.group(1).replace(",", ""))
        counts[cid] = n

    days = []
    for cid, d in dates.items():
        days.append((d, counts.get(cid, 0)))
    days.sort()
    return days


def streaks(days):
    """(current, longest, longest_end_date) over consecutive active days."""
    cur = best = 0
    best_end = ""
    run = 0
    for d, n in days:
        if n > 0:
            run += 1
            if run > best:
                best, best_end = run, d
        else:
            run = 0
    # current streak: walk back from the most recent day, tolerating a blank today
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    return cur, best, best_end


def build(mode, days):
    T = THEMES[mode]
    total = sum(n for _, n in days)
    active = sum(1 for _, n in days if n > 0)
    cur, best, best_end = streaks(days)
    peak_d, peak_n = max(days, key=lambda t: t[1]) if days else ("", 0)
    # busiest weekday
    wd = [0] * 7
    for d, n in days:
        y, m, dd = (int(x) for x in d.split("-"))
        wd[datetime.date(y, m, dd).weekday()] += n
    busiest = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wd.index(max(wd))] if days else "-"

    tiles = [
        ("%d" % total,  "contributions",   "last 12 months"),
        ("%d" % active, "active days",     "of %d" % len(days)),
        ("%d" % best,   "longest streak",  "consecutive days"),
        ("%d" % peak_n, "best day",        peak_d or "-"),
        (busiest,       "busiest weekday", "by volume"),
    ]
    # The current streak is deliberately not a tile. It is zero on any day you
    # have not pushed yet, which says nothing about the year behind it and is a
    # bad thing to lead a profile with.
    if cur > 2:
        tiles.insert(2, ("%d" % cur, "current streak", "days"))

    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'role="img" aria-label="GitHub contribution statistics">' % (W, H, W, H))
    s.append('<rect width="%d" height="%d" rx="12" fill="%s"/>' % (W, H, T["bg"]))
    s.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="12" fill="none" stroke="%s"/>'
             % (W - 1, H - 1, T["stroke"]))

    n = len(tiles)
    pad = 16
    tw = (W - pad * 2) / n
    for i, (val, lab, sub) in enumerate(tiles):
        cx = pad + tw * i + tw / 2
        if i:
            s.append('<line x1="%.1f" y1="26" x2="%.1f" y2="86" stroke="%s"/>'
                     % (pad + tw * i, pad + tw * i, T["stroke"]))
        s.append('<text x="%.1f" y="58" text-anchor="middle" font-family="%s" font-size="30" '
                 'font-weight="700" fill="%s">%s</text>' % (cx, MONO, T["num"], val))
        s.append('<text x="%.1f" y="76" text-anchor="middle" font-family="%s" font-size="11.5" '
                 'letter-spacing="1.1" fill="%s">%s</text>' % (cx, MONO, T["accent"], lab))
        s.append('<text x="%.1f" y="91" text-anchor="middle" font-family="%s" font-size="10" '
                 'fill="%s">%s</text>' % (cx, MONO, T["muted"], sub))

    # 52-week sparkline of weekly totals
    weeks, cur_w = [], 0
    for idx, (d, c) in enumerate(days):
        cur_w += c
        if (idx + 1) % 7 == 0:
            weeks.append(cur_w)
            cur_w = 0
    if cur_w:
        weeks.append(cur_w)
    mx = max(weeks) if weeks else 1
    bx, by, bw, bh = pad, 106, W - pad * 2, 40
    bar = bw / max(1, len(weeks))
    for i, v in enumerate(weeks):
        h = 2 + (bh - 4) * (v / mx if mx else 0)
        col = T["ok"] if v >= mx * 0.6 else (T["accent"] if v > 0 else T["spark"])
        s.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="1.2" fill="%s" opacity="%s"/>'
                 % (bx + i * bar, by + bh - h, max(1.6, bar - 1.6), h, col, "1" if v else "0.35"))

    s.append('<text x="%d" y="%d" font-family="%s" font-size="10" fill="%s">52 weeks ago</text>'
             % (pad, H - 8, MONO, T["muted"]))
    s.append('<text x="%d" y="%d" text-anchor="end" font-family="%s" font-size="10" fill="%s">today</text>'
             % (W - pad, H - 8, MONO, T["muted"]))
    s.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="10" fill="%s">'
             'weekly contribution volume</text>' % (W // 2, H - 8, MONO, T["muted"]))
    s.append("</svg>")
    return "".join(s)


if __name__ == "__main__":
    days = fetch_days(USER)
    if not days:
        raise SystemExit("no contribution data parsed for %s" % USER)
    os.makedirs(OUT, exist_ok=True)
    for mode in ("dark", "light"):
        p = os.path.join(OUT, "stats-%s.svg" % mode)
        with open(p, "w", encoding="utf-8") as f:
            f.write(build(mode, days))
        print("wrote %-18s %5.1f KB" % (os.path.basename(p), os.path.getsize(p) / 1024))
    cur, best, _ = streaks(days)
    print("total=%d active=%d current=%d longest=%d" %
          (sum(n for _, n in days), sum(1 for _, n in days if n > 0), cur, best))
