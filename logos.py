#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Turn real brand SVGs into dot clouds.

No SVG rasteriser is available in this environment, so this module carries a
minimal path flattener (M L H V C S Q T A Z, absolute and relative), fills the
resulting sub-paths with an even-odd XOR so holes survive, and samples the mask
on a jittered grid to produce an evenly spread point cloud.

Logo geometry is pulled from skillicons.dev, which carries the real marks --
including Azure and AWS, which simple-icons has removed.
"""
import os, re, math, json
import numpy as np
from PIL import Image, ImageDraw
import urllib.request

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".logocache")
S = 512  # raster size

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
CMD = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])")


# ------------------------------------------------------------------ fetching
def fetch_svg(name):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name + ".svg")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read()
    url = "https://skillicons.dev/icons?i=%s&theme=dark" % name
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read().decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(txt)
    return txt


def viewbox(svg):
    m = re.search(r'viewBox="([-\d.\s]+)"', svg)
    if m:
        v = [float(x) for x in m.group(1).split()]
        if len(v) == 4:
            return v
    return [0, 0, 256, 256]


def paths_of(svg):
    return re.findall(r'<path[^>]*\sd="([^"]+)"', svg)


# ------------------------------------------------------------------ flattening
def _bezier3(p0, p1, p2, p3, n=18):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
                    u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]))
    return out


def _bezier2(p0, p1, p2, n=14):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0],
                    u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
    return out


def _arc(p0, rx, ry, rot, laf, sf, p1, n=24):
    """SVG endpoint arc -> polyline (endpoint to centre parameterisation)."""
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rot)
    dx2, dy2 = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1 = math.cos(phi) * dx2 + math.sin(phi) * dy2
    y1 = -math.sin(phi) * dx2 + math.cos(phi) * dy2
    lam = (x1*x1) / (rx*rx) + (y1*y1) / (ry*ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx*rx*ry*ry - rx*rx*y1*y1 - ry*ry*x1*x1
    den = rx*rx*y1*y1 + ry*ry*x1*x1
    c = math.sqrt(max(0.0, num / den)) if den else 0.0
    if laf == sf:
        c = -c
    cx1, cy1 = c * rx * y1 / ry, -c * ry * x1 / rx
    cx = math.cos(phi) * cx1 - math.sin(phi) * cy1 + (p0[0] + p1[0]) / 2.0
    cy = math.sin(phi) * cx1 + math.cos(phi) * cy1 + (p0[1] + p1[1]) / 2.0

    def ang(ux, uy, vx, vy):
        d = math.hypot(ux, uy) * math.hypot(vx, vy)
        if d == 0:
            return 0.0
        v = max(-1.0, min(1.0, (ux*vx + uy*vy) / d))
        a = math.acos(v)
        return -a if (ux*vy - uy*vx) < 0 else a

    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sf and dt > 0:
        dt -= 2 * math.pi
    elif sf and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        ex = math.cos(phi) * rx * math.cos(t) - math.sin(phi) * ry * math.sin(t) + cx
        ey = math.sin(phi) * rx * math.cos(t) + math.cos(phi) * ry * math.sin(t) + cy
        out.append((ex, ey))
    return out


def flatten(d):
    """SVG path data -> list of sub-paths, each a list of (x, y)."""
    toks = [t for t in CMD.split(d) if t.strip()]
    subs, cur = [], []
    x = y = sx = sy = 0.0
    px = py = None      # previous control point, for S/T
    i = 0
    prev = ""
    while i < len(toks):
        c = toks[i]
        if not CMD.fullmatch(c):
            i += 1
            continue
        args = []
        if i + 1 < len(toks) and not CMD.fullmatch(toks[i + 1]):
            args = [float(v) for v in NUM.findall(toks[i + 1])]
            i += 2
        else:
            i += 1
        rel = c.islower()
        C = c.upper()

        if C == "M":
            for j in range(0, len(args) - 1, 2):
                nx, ny = args[j], args[j + 1]
                if rel:
                    nx, ny = x + nx, y + ny
                if j == 0:
                    if len(cur) > 1:
                        subs.append(cur)
                    cur = [(nx, ny)]
                    sx, sy = nx, ny
                else:
                    cur.append((nx, ny))
                x, y = nx, ny
            px = py = None
        elif C == "L":
            for j in range(0, len(args) - 1, 2):
                nx, ny = args[j], args[j + 1]
                if rel:
                    nx, ny = x + nx, y + ny
                cur.append((nx, ny)); x, y = nx, ny
            px = py = None
        elif C == "H":
            for v in args:
                nx = x + v if rel else v
                cur.append((nx, y)); x = nx
            px = py = None
        elif C == "V":
            for v in args:
                ny = y + v if rel else v
                cur.append((x, ny)); y = ny
            px = py = None
        elif C == "C":
            for j in range(0, len(args) - 5, 6):
                a = args[j:j + 6]
                if rel:
                    a = [a[0]+x, a[1]+y, a[2]+x, a[3]+y, a[4]+x, a[5]+y]
                cur += _bezier3((x, y), (a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
                px, py = a[2], a[3]
                x, y = a[4], a[5]
        elif C == "S":
            for j in range(0, len(args) - 3, 4):
                a = args[j:j + 4]
                if rel:
                    a = [a[0]+x, a[1]+y, a[2]+x, a[3]+y]
                c1 = (2*x - px, 2*y - py) if px is not None and prev in "CS" else (x, y)
                cur += _bezier3((x, y), c1, (a[0], a[1]), (a[2], a[3]))
                px, py = a[0], a[1]
                x, y = a[2], a[3]
        elif C == "Q":
            for j in range(0, len(args) - 3, 4):
                a = args[j:j + 4]
                if rel:
                    a = [a[0]+x, a[1]+y, a[2]+x, a[3]+y]
                cur += _bezier2((x, y), (a[0], a[1]), (a[2], a[3]))
                px, py = a[0], a[1]
                x, y = a[2], a[3]
        elif C == "T":
            for j in range(0, len(args) - 1, 2):
                a = args[j:j + 2]
                if rel:
                    a = [a[0]+x, a[1]+y]
                c1 = (2*x - px, 2*y - py) if px is not None and prev in "QT" else (x, y)
                cur += _bezier2((x, y), c1, (a[0], a[1]))
                px, py = c1
                x, y = a[0], a[1]
        elif C == "A":
            for j in range(0, len(args) - 6, 7):
                a = args[j:j + 7]
                ex, ey = (x + a[5], y + a[6]) if rel else (a[5], a[6])
                cur += _arc((x, y), a[0], a[1], a[2], int(a[3]), int(a[4]), (ex, ey))
                x, y = ex, ey
            px = py = None
        elif C == "Z":
            if len(cur) > 1:
                cur.append((sx, sy))
                subs.append(cur)
            cur = [(sx, sy)]
            x, y = sx, sy
            px = py = None
        prev = C
    if len(cur) > 1:
        subs.append(cur)
    return subs


# ------------------------------------------------------------------ raster + sample
def mask_of(name):
    """Rasterise a brand mark to a square boolean mask, trimmed and centred."""
    svg = fetch_svg(name)
    vb = viewbox(svg)
    vw, vh = (vb[2] or 256), (vb[3] or 256)
    acc = np.zeros((S, S), dtype=bool)
    for d in paths_of(svg):
        # Even-odd WITHIN one path, so donut holes survive (the Kubernetes helm
        # wheel, the Ansible ring). UNION ACROSS paths -- separate <path>
        # elements are separate filled shapes, and XOR-ing them cancels the
        # overlaps, which silently ate most of the Azure mark.
        one = np.zeros((S, S), dtype=bool)
        for sub in flatten(d):
            if len(sub) < 3:
                continue
            pts = [((px - vb[0]) / vw * (S - 2) + 1,
                    (py - vb[1]) / vh * (S - 2) + 1) for (px, py) in sub]
            im = Image.new("1", (S, S), 0)
            ImageDraw.Draw(im).polygon(pts, fill=1)
            one ^= np.asarray(im, dtype=bool)
        acc |= one
    ys, xs = np.nonzero(acc)
    if len(xs) == 0:
        return acc
    acc = acc[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return acc


def sample(mask, k, seed=0):
    """Even spread of ~k points across the mask, in normalised -1..1 coords."""
    rng = np.random.default_rng(seed)
    h, w = mask.shape
    lo, hi = 1.0, float(max(h, w))
    pts = []
    for _ in range(36):
        pitch = (lo + hi) / 2.0
        cand = []
        gy = int(h / pitch) + 1
        gx = int(w / pitch) + 1
        for iy in range(gy):
            for ix in range(gx):
                cy = (iy + 0.5) * pitch + rng.normal(0, pitch * 0.16)
                cx = (ix + 0.5) * pitch + rng.normal(0, pitch * 0.16)
                yy, xx = int(cy), int(cx)
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx]:
                    cand.append((cx, cy))
        if len(cand) > k:
            lo = pitch
        else:
            hi = pitch
        pts = cand
        if abs(len(cand) - k) <= max(3, k // 60):
            break
    if len(pts) > k:
        idx = rng.choice(len(pts), k, replace=False)
        pts = [pts[i] for i in idx]
    while len(pts) < k and pts:
        pts.append(pts[rng.integers(0, len(pts))])
    a = np.array(pts, dtype=float)
    scale = max(w, h) / 2.0
    a[:, 0] = (a[:, 0] - w / 2.0) / scale
    a[:, 1] = (a[:, 1] - h / 2.0) / scale
    return a


def devops_infinity(k, seed=3, width=0.050):
    """
    The DevOps loop as a thick filled ribbon.

    Sampling points along the lemniscate directly gives a hairline that reads as
    a stray curve rather than a mark. Instead the curve is stroked into a raster
    at real width and then sampled like any other logo, so the dot density
    matches the brand marks beside it.
    """
    S = 420
    img = Image.new("1", (S, S), 0)
    dr = ImageDraw.Draw(img)
    pts = []
    for i in range(721):
        t = 2 * math.pi * i / 720.0
        d = 1 + math.sin(t) ** 2
        x = (math.cos(t) / d) / 0.72
        y = (math.sin(t) * math.cos(t) / d) / 0.36
        pts.append((S / 2 + x * S * 0.40, S / 2 + y * S * 0.40))
    dr.line(pts, fill=1, width=max(3, int(S * width)), joint="curve")
    mask = np.asarray(img, dtype=bool)
    ys, xs = np.nonzero(mask)
    mask = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return sample(mask, k, seed=seed)


def place(pts, cx, cy, scale):
    out = pts.copy()
    out[:, 0] = cx + out[:, 0] * scale
    out[:, 1] = cy + out[:, 1] * scale
    return out


if __name__ == "__main__":
    for n in ("azure", "aws", "terraform", "kubernetes", "ansible"):
        m = mask_of(n)
        print("%-12s mask %sx%s  filled %5.1f%%" % (n, m.shape[1], m.shape[0], 100 * m.mean()))
