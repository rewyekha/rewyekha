#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
"Rolling deployment" contribution grid, rendered inside a terminal window.

Replaces the contribution snake. Your real contribution calendar is rolled out
the way a Kubernetes Deployment rolls out: every cell starts Pending, a wave
sweeps left to right flipping cells through ContainerCreating into Running, a
live replica counter tracks progress, and the run finishes with the real
`successfully rolled out` line.

Data source is the public contributions endpoint, so this needs NO token and no
API scope -- which is why the workflow that drives it is three steps long.

Usage:  python deploy_grid.py [username]
Writes: deploy-dark.svg, deploy-light.svg
"""
import os, re, sys, urllib.request, datetime

USER = (sys.argv[1] if len(sys.argv) > 1 else "rewyekha")
OUT = os.environ.get("GH_OUT", os.path.dirname(os.path.abspath(__file__)))

W, H = 1180, 372
TITLEBAR = 38
CELL, GAP = 15, 4
PITCH = CELL + GAP
GRID_X, GRID_Y = 104, 150
CYCLE = 15.0
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# rollout timing, as a fraction of the cycle
T_CMD1, T_OUT1, T_CMD2 = 0.02, 0.10, 0.14
T_WAVE_START, T_WAVE_END = 0.22, 0.74
T_DONE = 0.80

THEMES = {
    "dark": dict(
        bg="#0A0F1C", chrome="#111A2E", stroke="#1E2C47", muted="#4A5A75",
        text="#E2E8F0", dim="#7C8FAB", prompt="#38BDF8", ok="#34D399",
        warn="#F59E0B", pending="#16233B", pending_stroke="#243352",
        levels=["#16233B", "#065F46", "#047857", "#10B981", "#34D399"],
    ),
    "light": dict(
        bg="#FFFFFF", chrome="#F1F5F9", stroke="#D7DEE8", muted="#94A3B8",
        text="#0F172A", dim="#475569", prompt="#0369A1", ok="#047857",
        warn="#B45309", pending="#EBEFF4", pending_stroke="#DCE3EC",
        levels=["#EBEFF4", "#A7F3D0", "#34D399", "#059669", "#047857"],
    ),
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ------------------------------------------------------------------ data
def fetch(user):
    url = "https://github.com/users/%s/contributions" % user
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")

    cells = {}
    pat = re.compile(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="contribution-day-component-(\d+)-(\d+)"'
        r'[^>]*data-level="(\d)"')
    for m in pat.finditer(html):
        date, d, w, lvl = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        cells[(w, d)] = (date, lvl)
    if not cells:
        # attribute order differs occasionally; retry with a looser pass
        loose = re.compile(r'id="contribution-day-component-(\d+)-(\d+)"')
        for m in loose.finditer(html):
            d, w = int(m.group(1)), int(m.group(2))
            cells.setdefault((w, d), ("", 0))
    return cells


# ------------------------------------------------------------------ helpers
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def typed(x, y, parts, t0, dur, fs=13.5):
    """Typewriter reveal via an animated clip rectangle."""
    uid = "clip%d" % int(t0 * 100000)
    total = sum(len(p[0]) for p in parts)
    width = total * 8.05 + 10
    spans = "".join('<tspan fill="%s">%s</tspan>' % (c, esc(t)) for t, c in parts)
    return (
        '<defs><clipPath id="%s"><rect x="%d" y="%d" width="0" height="26">'
        '<animate attributeName="width" dur="%.2fs" repeatCount="indefinite" '
        'keyTimes="0;%.4f;%.4f;1" values="0;0;%.0f;%.0f" calcMode="linear"/>'
        '</rect></clipPath></defs>'
        '<text x="%d" y="%d" font-family="%s" font-size="%.1f" clip-path="url(#%s)" '
        'xml:space="preserve">%s</text>'
        % (uid, x - 2, y - 14, CYCLE, t0, t0 + dur, width, width,
           x, y, MONO, fs, uid, spans))


def fade(x, y, parts, t0, fs=13.5, anchor="start"):
    spans = "".join('<tspan fill="%s">%s</tspan>' % (c, esc(t)) for t, c in parts)
    return ('<text x="%d" y="%d" font-family="%s" font-size="%.1f" text-anchor="%s" opacity="0" '
            'xml:space="preserve">%s'
            '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
            'keyTimes="0;%.4f;%.4f;1" values="0;0;1;1"/></text>'
            % (x, y, MONO, fs, anchor, spans, CYCLE, t0, min(0.999, t0 + 0.02)))


# ------------------------------------------------------------------ build
def build(mode, cells):
    T = THEMES[mode]
    weeks = max(w for (w, _) in cells) + 1
    active = sum(1 for v in cells.values() if v[1] > 0)

    s = []
    s.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'role="img" aria-label="Contribution grid rolled out like a Kubernetes deployment">'
             % (W, H, W, H))
    s.append('<rect width="%d" height="%d" rx="12" fill="%s"/>' % (W, H, T["bg"]))
    s.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="12" fill="none" stroke="%s"/>'
             % (W - 1, H - 1, T["stroke"]))

    # ---- title bar
    s.append('<rect x="1" y="1" width="%d" height="%d" rx="11" fill="%s"/>' % (W - 2, TITLEBAR, T["chrome"]))
    s.append('<rect x="1" y="%d" width="%d" height="12" fill="%s"/>' % (TITLEBAR - 11, W - 2, T["chrome"]))
    s.append('<line x1="1" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (TITLEBAR, W - 1, TITLEBAR, T["stroke"]))
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        s.append('<circle cx="%d" cy="%d" r="5.5" fill="%s"/>' % (24 + i * 19, TITLEBAR // 2, c))
    s.append('<text x="%d" y="%d" font-family="%s" font-size="12" fill="%s" text-anchor="middle">'
             'rollout.sh &#8212; reyas@delivery</text>' % (W // 2, TITLEBAR // 2 + 4, MONO, T["muted"]))

    # ---- terminal lines
    s.append(typed(26, 68, [("$ ", T["prompt"]),
                            ("kubectl apply -f contributions.yaml", T["text"])],
                   T_CMD1, 0.055))
    s.append(fade(26, 92, [("deployment.apps/", T["dim"]),
                           ("%s-contributions" % USER, T["text"]),
                           (" configured", T["dim"])], T_OUT1))
    s.append(typed(26, 118, [("$ ", T["prompt"]),
                             ("kubectl rollout status deployment/%s-contributions" % USER, T["text"])],
                   T_CMD2, 0.06))

    # ---- month labels
    first = None
    for (w, d), (date, _) in sorted(cells.items()):
        if date:
            first = date
            break
    if first:
        start = datetime.date(*[int(v) for v in first.split("-")])
        seen = set()
        for w in range(weeks):
            day = start + datetime.timedelta(weeks=w)
            if day.month not in seen and day.day <= 7:
                seen.add(day.month)
                s.append('<text x="%d" y="%d" font-family="%s" font-size="10.5" fill="%s">%s</text>'
                         % (GRID_X + w * PITCH, GRID_Y - 8, MONO, T["muted"], MONTHS[day.month - 1]))

    for i, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.append('<text x="%d" y="%d" font-family="%s" font-size="10.5" fill="%s" text-anchor="end">%s</text>'
                 % (GRID_X - 10, GRID_Y + i * PITCH + 11, MONO, T["muted"], lab))

    # ---- the grid: every cell rolls Pending -> ContainerCreating -> Running
    span = T_WAVE_END - T_WAVE_START
    s.append('<g>')
    for (w, d), (date, lvl) in sorted(cells.items()):
        x = GRID_X + w * PITCH
        y = GRID_Y + d * PITCH
        # wave front sweeps left to right, with a slight vertical rake
        t = T_WAVE_START + span * ((w + d * 0.18) / (weeks + 1.2))
        creating = min(0.995, t + 0.018)
        running = min(0.998, t + 0.042)
        final = T["levels"][lvl]

        # pending base
        s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" stroke="%s" '
                 'stroke-width="0.8"/>' % (x, y, CELL, CELL, T["pending"], T["pending_stroke"]))
        # the pod itself
        s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" opacity="0">'
                 '<animate attributeName="fill" dur="%.2fs" repeatCount="indefinite" '
                 'keyTimes="0;%.4f;%.4f;1" values="%s;%s;%s;%s"/>'
                 '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
                 'keyTimes="0;%.4f;%.4f;%.4f;1" values="0;0;1;1;1"/>'
                 '</rect>'
                 % (x, y, CELL, CELL, T["warn"],
                    CYCLE, creating, running, T["warn"], T["warn"], final, final,
                    CYCLE, max(0.0, t - 0.004), creating, running))
        # scheduling flash on the cells that actually carry contributions
        if lvl > 0:
            s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="none" stroke="%s" '
                     'stroke-width="1.6" opacity="0">'
                     '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
                     'keyTimes="0;%.4f;%.4f;%.4f;1" values="0;0;0.95;0;0"/>'
                     '</rect>'
                     % (x, y, CELL, CELL, T["warn"], CYCLE,
                        max(0.0, t - 0.004), creating, min(0.999, running + 0.02)))
    s.append('</g>')

    # ---- moving wave marker
    gx1 = GRID_X - 6
    gx2 = GRID_X + weeks * PITCH + 2
    s.append('<rect x="%d" y="%d" width="2" height="%d" fill="%s" opacity="0">'
             '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
             'keyTimes="0;%.4f;%.4f;%.4f;1" values="0;0.55;0.55;0;0"/>'
             '<animate attributeName="x" dur="%.2fs" repeatCount="indefinite" '
             'keyTimes="0;%.4f;%.4f;1" values="%d;%d;%d;%d" calcMode="linear"/>'
             '</rect>'
             % (gx1, GRID_Y - 4, 7 * PITCH, T["warn"], CYCLE,
                T_WAVE_START, T_WAVE_END, min(0.999, T_WAVE_END + 0.01),
                CYCLE, T_WAVE_START, T_WAVE_END, gx1, gx1, gx2, gx2))

    # ---- live replica counter
    sy = GRID_Y + 7 * PITCH + 34
    STEPS = 16
    for i in range(STEPS):
        a = T_WAVE_START + span * (i / STEPS)
        b = T_WAVE_START + span * ((i + 1) / STEPS)
        n = int(active * (i + 1) / STEPS)
        s.append('<text x="26" y="%d" font-family="%s" font-size="13.5" opacity="0" xml:space="preserve">'
                 '<tspan fill="%s">Waiting for deployment rollout to finish: </tspan>'
                 '<tspan fill="%s">%d</tspan><tspan fill="%s"> of </tspan>'
                 '<tspan fill="%s">%d</tspan><tspan fill="%s"> updated replicas are available...</tspan>'
                 '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
                 'keyTimes="0;%.4f;%.4f;%.4f;%.4f;1" values="0;0;1;1;0;0"/></text>'
                 % (sy, MONO, T["dim"], T["text"], n, T["dim"], T["text"], active, T["dim"],
                    CYCLE, max(0.0, a - 0.001), a, max(a, b - 0.001), b))

    # ---- success line
    s.append('<text x="26" y="%d" font-family="%s" font-size="13.5" opacity="0" xml:space="preserve">'
             '<tspan fill="%s">deployment "</tspan><tspan fill="%s">%s-contributions</tspan>'
             '<tspan fill="%s">" </tspan><tspan fill="%s">successfully rolled out</tspan>'
             '<animate attributeName="opacity" dur="%.2fs" repeatCount="indefinite" '
             'keyTimes="0;%.4f;%.4f;1" values="0;0;1;1"/></text>'
             % (sy, MONO, T["dim"], T["text"], USER, T["dim"], T["ok"],
                CYCLE, T_DONE - 0.005, T_DONE))

    # ---- summary strip
    s.append(fade(26, sy + 26,
                  [("replicas ", T["muted"]), ("%d/%d" % (active, len(cells)), T["ok"]),
                   ("    strategy ", T["muted"]), ("RollingUpdate", T["text"]),
                   ("    maxSurge ", T["muted"]), ("25%", T["text"]),
                   ("    maxUnavailable ", T["muted"]), ("0", T["text"])],
                  T_DONE + 0.02, fs=12))

    # legend
    lx = W - 250
    s.append('<text x="%d" y="%d" font-family="%s" font-size="11" fill="%s">Less</text>'
             % (lx, sy + 26, MONO, T["muted"]))
    for i, c in enumerate(T["levels"]):
        s.append('<rect x="%d" y="%d" width="11" height="11" rx="2.5" fill="%s" stroke="%s" '
                 'stroke-width="0.7"/>' % (lx + 40 + i * 15, sy + 16, c, T["pending_stroke"]))
    s.append('<text x="%d" y="%d" font-family="%s" font-size="11" fill="%s">More</text>'
             % (lx + 40 + 5 * 15 + 4, sy + 26, MONO, T["muted"]))

    s.append("</svg>")
    return "".join(s)


if __name__ == "__main__":
    cells = fetch(USER)
    if not cells:
        raise SystemExit("no contribution cells parsed for %s" % USER)
    os.makedirs(OUT, exist_ok=True)
    for mode in ("dark", "light"):
        p = os.path.join(OUT, "deploy-%s.svg" % mode)
        with open(p, "w", encoding="utf-8") as f:
            f.write(build(mode, cells))
        print("wrote %-20s %6.1f KB" % (os.path.basename(p), os.path.getsize(p) / 1024))
    print("cells=%d  active=%d  weeks=%d" %
          (len(cells), sum(1 for v in cells.values() if v[1] > 0),
           max(w for (w, _) in cells) + 1))
