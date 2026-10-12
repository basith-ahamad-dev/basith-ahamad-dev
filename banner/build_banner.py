"""Generate the animated profile banner (dark.svg / light.svg).

Run order:  python rasterize_logos.py  ->  python portrait.py  ->  python build_banner.py
Source of truth = this script + data/*.npy (never hand-edit the SVG).

    python build_banner.py                 # writes out/banner-dark.svg + out/banner-light.svg
    python build_banner.py --static logo2  # animation-free frame (portrait|logo1|logo2|logo3) for checks
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans

HERE = Path(__file__).parent
DATA, OUT = HERE / "data", HERE / "out"
OUT.mkdir(exist_ok=True)
SEED = 7

# ---------------------------------------------------------------- profile
HANDLE = "basith-ahamad-dev"
ROWS_A = [  # identity
    ("Subject", "Basith Ahamad"),
    ("Role", "Associate Software Engineer"),
    ("Origin", "Sri Lanka"),
    ("Education", "BSc (Hons) in Computer Science"),
    ("Status", "Building + Learning + Shipping"),
    ("ToolChain", "VS Code, Git, Figma, Canva"),
]
ROWS_B = [  # core stack
    ("Core.Lang", "Python, PHP, JavaScript, TypeScript"),
    ("Core.Frontend", "React, Next.js, Tailwind CSS"),
    ("Core.Backend", "Laravel, FastAPI, Flask"),
    ("Core.Database", "MySQL, PostgreSQL, MongoDB"),
    ("Core.Infra", "Vercel, AWS, cPanel"),
]
ROWS_C = [  # grid / contact
    ("Grid.Mail", "bashithahamed79@gmail.com"),
    ("Grid.Portfolio", "basith-ahamad.vercel.app"),
    ("Grid.LinkedIn", "in/basith-ahamad-872195413"),
    ("Grid.GitHub", f"github.com/{HANDLE}"),
]
HIGHLIGHT = {"Status"}  # values drawn in the accent colour

THEMES = {
    "dark": dict(win="#0A101F", bar="#0F172A", border="#1E2A44", text="#E2E8F0", dim="#64748B",
                 portrait="#A78BFA", chrome="#22D3EE", accent="#10B981", logo="#22D3EE",
                 panel="#0A101F", pilltext="#06202A", leader="#334155"),
    "light": dict(win="#FFFFFF", bar="#EEF2F8", border="#CBD5E1", text="#0F172A", dim="#64748B",
                  portrait="#7C3AED", chrome="#0891B2", accent="#059669", logo="#0891B2",
                  panel="#F8FAFC", pilltext="#FFFFFF", leader="#CBD5E1"),
}

# ---------------------------------------------------------------- geometry
BW, BH = 1180, 610
GW, GH = 300, 340                     # dither grid
PX, PY, PW = 36, 96, 412              # portrait origin + width on the banner
S = PW / GW
FRAME = (24, 56, 436, 530)
CHAR = 8.4                            # monospace advance at 14px
FONT = "'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ---------------------------------------------------------------- timeline (seconds)
T0 = 3.2                              # intro length; loop starts here
P_HOLD, L_HOLD, TR = 3.0, 2.0, 1.3
LOOP = P_HOLD + 3 * L_HOLD + 4 * TR   # 14.2
MARKS = [0, P_HOLD, P_HOLD + TR, P_HOLD + TR + L_HOLD, P_HOLD + 2 * TR + L_HOLD,
         P_HOLD + 2 * TR + 2 * L_HOLD, P_HOLD + 3 * TR + 2 * L_HOLD,
         P_HOLD + 3 * TR + 3 * L_HOLD, LOOP]
EASE = "0.45 0 0.2 1"
N_INTRO, N_TRAV, DRIFT, NOISE_SIGMA = 60, 900, 0.42, 4.0
LOGO_SIZE = 200.0
LOGOS = ["python", "code", "vercel"]
CENTER = (GW / 2, GH / 2)


def fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def keytimes(marks):
    return ";".join(fmt(m / marks[-1]) if 0 < m < marks[-1] else str(int(m / marks[-1])) for m in marks)


def dots_path(pts):
    """pts: iterable of (x, y) grid cells -> compact <path d> of 1x1 cells (stroke trick:
    horizontal 1-wide lines, butt caps). Adjacent cells in a row merge into one run."""
    pts = sorted(set(map(tuple, pts)), key=lambda p: (p[1], p[0]))
    runs = []
    for x, y in pts:
        if runs and runs[-1][1] == y and runs[-1][0] + runs[-1][2] == x:
            runs[-1][2] += 1
        else:
            runs.append([x, y, 1])
    d, cx, cy = [], 0, 0
    for i, (x, y, n) in enumerate(runs):
        if i == 0:
            d.append(f"M{x} {y + 0.5}h{n}")
        else:
            d.append(f"m{x - cx} {y - cy}h{n}")
        cx, cy = x + n, y
    return "".join(d)


# ---------------------------------------------------------------- logos / travellers
def logo_points(name, rng):
    """900 evenly spread points inside the logo mask (k-means centres), cached per logo."""
    cache = DATA / f"logo_pts_{name}.npy"
    if cache.exists():
        return np.load(cache), np.array(CENTER)
    a = np.asarray(Image.open(DATA / f"logo_{name}.png").convert("L")) < 128
    ys, xs = np.nonzero(a)
    pts = np.stack([xs, ys], 1).astype(float)
    sub = pts[rng.choice(len(pts), min(len(pts), 30000), replace=False)]
    km = KMeans(n_clusters=N_TRAV, n_init=1, max_iter=60, random_state=int(rng.integers(1 << 30)))
    c = km.fit(sub).cluster_centers_
    # logo box -> grid coords; centre on the logo's centroid, not its bounding box
    c = (c - pts.mean(0)) / 512.0 * LOGO_SIZE + np.array(CENTER)
    np.save(cache, c)
    return c, np.array(CENTER)


def match(a, b):
    cost = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
    r, c = linear_sum_assignment(cost)
    out = np.empty_like(b)
    out[r] = b[c]
    return out


def build_travellers(dots, rng):
    L = [logo_points(n, rng)[0] for n in LOGOS]
    ys, xs = np.nonzero(dots)
    pick = rng.choice(len(xs), N_TRAV, replace=False)
    start = np.stack([xs[pick] + 0.5, ys[pick] + 0.5], 1).astype(float)
    p1 = match(start, L[0])
    p2 = match(p1, L[1])
    p3 = match(p2, L[2])
    return start, p1, p2, p3


# ---------------------------------------------------------------- metrics
def evenness(groups, pts):
    """mean distance from each group's centroid to the portrait centroid / portrait RMS radius.
    ~0.05 = dots shimmer in everywhere, ~0.7 = patch-by-patch reveal."""
    pts = np.asarray(pts, float)
    c, r = pts.mean(0), np.sqrt(((pts - pts.mean(0)) ** 2).sum(1).mean())
    d = [np.linalg.norm(pts[g].mean(0) - c) / r for g in groups if len(g)]
    return float(np.mean(d))


def straight_boundary(labels_grid):
    """fraction of band-boundary edges that sit in an axis-aligned straight run >= 6 cells.
    ~0.01 = organic, ~0.17 = a grid."""
    L = labels_grid
    edges_h = (L[:, 1:] != L[:, :-1]) & (L[:, 1:] >= 0) & (L[:, :-1] >= 0)   # vertical boundaries
    edges_v = (L[1:, :] != L[:-1, :]) & (L[1:, :] >= 0) & (L[:-1, :] >= 0)   # horizontal boundaries
    total = edges_h.sum() + edges_v.sum()
    if total == 0:
        return 0.0

    def long_runs(e, axis):
        n = 0
        e = e if axis == 0 else e.T
        for col in e.T:  # walk each line
            run = 0
            for v in list(col) + [False]:
                if v:
                    run += 1
                else:
                    if run >= 6:
                        n += run
                    run = 0
        return n

    # a vertical boundary is a straight run if consecutive rows share the same boundary column
    n = long_runs(edges_h, 0) + long_runs(edges_v, 1)
    return n / total


# ---------------------------------------------------------------- svg pieces
def anim_values(vals, marks, attr, kind=None, extra=""):
    kt = keytimes(marks)
    ks = ";".join([EASE] * (len(marks) - 1))
    tag = "animateTransform" if kind else "animate"
    typ = f' type="{kind}"' if kind else ""
    return (f'<{tag} attributeName="{attr}"{typ} values="{";".join(vals)}" keyTimes="{kt}" '
            f'calcMode="spline" keySplines="{ks}" begin="{T0}s" dur="{LOOP}s" repeatCount="indefinite"{extra}/>')


def info_panel(t):
    x0, x1 = 492, 1148
    o = []
    o.append(f'<text x="{x0}" y="76" font-size="13" font-weight="700" letter-spacing="1.5" fill="{t["chrome"]}">SYSTEM.INFO</text>')
    # live badge
    o.append(f'<rect x="{x1 - 62}" y="62" width="62" height="20" rx="10" fill="#EF4444" fill-opacity="0.16" stroke="#EF4444" stroke-opacity="0.7"/>')
    o.append(f'<circle cx="{x1 - 47}" cy="72" r="4" fill="#EF4444"><animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/>'
             f'<animate attributeName="r" values="4;3;4" dur="1.6s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{x1 - 37}" y="76.5" font-size="12" font-weight="700" fill="#EF4444" textLength="{4 * 7.2:.1f}" lengthAdjust="spacingAndGlyphs">LIVE</text>')
    # handle pill
    h = "@" + HANDLE
    pw = len(h) * CHAR + 28
    o.append(f'<rect x="{x0}" y="94" width="{pw:.1f}" height="26" rx="13" fill="{t["chrome"]}"/>')
    o.append(f'<text x="{x0 + 14}" y="111.5" font-size="14" font-weight="700" fill="{t["pilltext"]}" textLength="{len(h) * CHAR:.1f}" lengthAdjust="spacingAndGlyphs">{h}</text>')

    def block(rows, y):
        for label, val in rows:
            lw, vw = len(label) * CHAR, len(val) * CHAR
            vx = x1 - vw
            gap = vx - (x0 + lw) - 12
            n = max(int(gap // CHAR), 0)
            col = t["accent"] if label in HIGHLIGHT else t["text"]
            o.append(f'<text x="{x0}" y="{y}" font-size="14" fill="{t["chrome"]}" textLength="{lw:.1f}" lengthAdjust="spacingAndGlyphs">{label}</text>')
            if n > 0:
                o.append(f'<text x="{x0 + lw + 6:.1f}" y="{y}" font-size="14" fill="{t["leader"]}" textLength="{n * CHAR:.1f}" lengthAdjust="spacing" xml:space="preserve">{"." * n}</text>')
            o.append(f'<text x="{vx:.1f}" y="{y}" font-size="14" fill="{col}" textLength="{vw:.1f}" lengthAdjust="spacingAndGlyphs">{val}</text>')
            y += 23
        return y

    y = block(ROWS_A, 152)
    o.append(f'<line x1="{x0}" y1="{y - 9}" x2="{x1}" y2="{y - 9}" stroke="{t["border"]}" stroke-dasharray="2 4"/>')
    y = block(ROWS_B, y + 10)
    o.append(f'<line x1="{x0}" y1="{y - 9}" x2="{x1}" y2="{y - 9}" stroke="{t["border"]}" stroke-dasharray="2 4"/>')
    y = block(ROWS_C, y + 10)
    # prompt line
    o.append(f'<text x="{x0}" y="568" font-size="14" fill="{t["accent"]}">$</text>')
    o.append(f'<text x="{x0 + 18}" y="568" font-size="14" fill="{t["dim"]}" textLength="{len("whoami --live") * CHAR:.1f}" lengthAdjust="spacingAndGlyphs">whoami --live</text>')
    o.append(f'<rect x="{x0 + 18 + 13 * CHAR + 6:.1f}" y="556" width="8" height="15" fill="{t["accent"]}"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></rect>')
    return "\n".join(o)


def chrome_svg(t, mode):
    fx, fy, fw, fh = FRAME
    s = [f'<rect width="{BW}" height="{BH}" rx="12" fill="{t["win"]}"/>',
         f'<path d="M0 12a12 12 0 0 1 12-12h{BW - 24}a12 12 0 0 1 12 12V40H0z" fill="{t["bar"]}"/>',
         f'<line x1="0" y1="40" x2="{BW}" y2="40" stroke="{t["border"]}"/>',
         f'<circle cx="24" cy="20" r="6" fill="#FF5F57"/><circle cx="44" cy="20" r="6" fill="#FEBC2E"/><circle cx="64" cy="20" r="6" fill="#28C840"/>',
         f'<text x="{BW / 2}" y="25" font-size="13" fill="{t["dim"]}" text-anchor="middle" textLength="{len("profile.sh --live") * 7.8:.1f}" lengthAdjust="spacingAndGlyphs">profile.sh --live</text>',
         f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="8" fill="{t["panel"]}" stroke="{t["chrome"]}" stroke-opacity="0.55"/>',
         f'<text x="{fx + 14}" y="{fy + 20}" font-size="12" font-weight="700" letter-spacing="1.5" fill="{t["chrome"]}">VISUAL.MAP</text>',
         f'<text x="{fx + fw - 14}" y="{fy + 20}" font-size="11" fill="{t["dim"]}" text-anchor="end">{GW}x{GH} / 1-bit</text>',
         f'<rect x="{BW - 12 - 10}" y="0" width="0" height="0"/>',
         f'<rect x="0.5" y="0.5" width="{BW - 1}" height="{BH - 1}" rx="12" fill="none" stroke="{t["border"]}"/>']
    return "\n".join(s)


def build(mode, static=None):
    t = THEMES[mode]
    rng = np.random.default_rng(SEED)
    dots = np.load(DATA / f"dots_{mode}.npy")
    ys, xs = np.nonzero(dots)
    pts = np.stack([xs, ys], 1)
    n = len(pts)
    metrics = {"dots": n}

    # ---- intro groups: stratified random scatter (shuffle, round-robin) -> evenly spread
    perm = rng.permutation(n)
    groups = [perm[i::N_INTRO] for i in range(N_INTRO)]
    metrics["intro_evenness"] = round(evenness(groups, pts), 3)

    # ---- drift bands: noise BEFORE quantising, else linear drift recreates a square grid
    noisy = pts + rng.normal(0, NOISE_SIGMA, pts.shape)
    bx = np.clip((noisy[:, 0] // (GW / 10)).astype(int), 0, 9)
    by = np.clip((noisy[:, 1] // (GH / 10)).astype(int), 0, 9)
    bid = by * 10 + bx
    uniq = np.unique(bid)
    band_idx = [np.nonzero(bid == u)[0] for u in uniq]
    lab = -np.ones((GH, GW), int)
    lab[ys, xs] = np.searchsorted(uniq, bid)
    # fill gaps so boundaries are measured between neighbours, not around holes
    from scipy import ndimage as ndi
    idx = ndi.distance_transform_edt(lab < 0, return_distances=False, return_indices=True)
    filled = lab[tuple(idx)]
    mask = np.load(DATA / "mask.npy") if mode == "dark" else np.ones((GH, GW), bool)
    filled = np.where(mask, filled, -1)
    metrics["bands"] = len(band_idx)
    metrics["straight_boundary"] = round(straight_boundary(filled), 3)
    # sanity: what a noise-free quantisation would give
    clean = np.clip((pts[:, 1] // (GH / 10)).astype(int), 0, 9) * 10 + np.clip((pts[:, 0] // (GW / 10)).astype(int), 0, 9)
    lab2 = -np.ones((GH, GW), int)
    lab2[ys, xs] = clean
    idx2 = ndi.distance_transform_edt(lab2 < 0, return_distances=False, return_indices=True)
    metrics["straight_boundary_no_noise"] = round(straight_boundary(np.where(mask, lab2[tuple(idx2)], -1)), 3)

    # ---- travellers
    start, p1, p2, p3 = build_travellers(dots, rng)
    c = np.array(CENTER)

    col = t["portrait"]
    pstyle = f'fill="none" stroke="{col}" stroke-width="1" shape-rendering="crispEdges"'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BW} {BH}" width="{BW}" height="{BH}" font-family="{FONT}">',
           f'<title>{HANDLE} profile</title>',
           f'<defs><clipPath id="pc"><rect x="{PX}" y="{PY}" width="{PW}" height="{GH * S:.2f}"/></clipPath></defs>',
           chrome_svg(t, mode)]

    def portrait_open():
        return f'<g clip-path="url(#pc)"><g transform="translate({PX} {PY}) scale({S:.5f})">'

    static_portrait = static == "portrait"
    if static is None:
        # intro layer (duplicate portrait, dissolves out when the loop layer takes over)
        out.append(portrait_open() + f'<g id="intro">')
        for i, g in enumerate(groups):
            b = i / (N_INTRO - 1) * 1.5
            out.append(f'<path {pstyle} opacity="0" d="{dots_path(pts[g])}"><animate attributeName="opacity" from="0" to="1" begin="{b:.3f}s" dur="0.5s" fill="freeze"/></path>')
        out.append(f'<set attributeName="opacity" to="0" begin="{T0}s" fill="freeze"/></g></g></g>')
        out.append(portrait_open() + '<g id="loop" opacity="0">'
                   f'<set attributeName="opacity" to="1" begin="{T0}s" fill="freeze"/>')
        for bi in band_idx:
            m = pts[bi].mean(0)
            tv = DRIFT * (c - m)
            tr = f"{fmt(tv[0])} {fmt(tv[1])}"
            out.append(f'<path {pstyle} d="{dots_path(pts[bi])}">'
                       + anim_values(["0 0", "0 0", tr, tr, tr, tr, tr, tr, "0 0"], MARKS, "transform", kind="translate")
                       + anim_values(["1", "1", "0", "0", "0", "0", "0", "0", "1"], MARKS, "opacity")
                       + '</path>')
        out.append('</g></g></g>')
        # travellers
        out.append(portrait_open() + f'<g id="trav" fill="{t["logo"]}" opacity="0">')
        out.append(anim_values(["0", "0", "1", "1", "1", "1", "1", "1", "0"], MARKS, "opacity", extra=""))
        for i in range(N_TRAV):
            vs = [start[i], start[i], p1[i], p1[i], p2[i], p2[i], p3[i], p3[i], start[i]]
            vals = [f"{fmt(v[0])} {fmt(v[1])}" for v in vs]
            out.append('<circle r="1.5">' + anim_values(vals, MARKS, "transform", kind="translate") + '</circle>')
        out.append('</g></g></g>')
    elif static_portrait:
        out.append(portrait_open() + f'<path {pstyle} d="{dots_path(pts)}"/></g></g>')
    else:
        key = {"logo1": p1, "logo2": p2, "logo3": p3}[static]
        out.append(portrait_open() + f'<g fill="{t["logo"]}">'
                   + "".join(f'<circle cx="{fmt(p[0])}" cy="{fmt(p[1])}" r="1.5"/>' for p in key) + '</g></g></g>')

    out.append(info_panel(t))
    out.append("</svg>")
    return "\n".join(out), metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", choices=["portrait", "logo1", "logo2", "logo3"])
    ap.add_argument("--mode", choices=["dark", "light"])
    a = ap.parse_args()
    for mode in ([a.mode] if a.mode else ["dark", "light"]):
        svg, m = build(mode, a.static)
        name = f"banner-{mode}" + (f"-static-{a.static}" if a.static else "") + ".svg"
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg) / 1024:.0f} KB  {m}")


if __name__ == "__main__":
    main()
