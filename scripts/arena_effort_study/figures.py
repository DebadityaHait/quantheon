"""Inline-SVG small multiples for the effort-curves post (no JS; <title> = hover)."""
import json, math, sys
from collections import defaultdict
from html import escape

D = json.load(open(sys.argv[1]))
TR = [t for t in D["trials"] if t["study"] == "flash-trio"]
AR = [a for a in D["arms"] if a["study"] == "flash-trio"]
MODELS = [("gpt-6-luna", "gpt-6-luna", ["low", "medium", "high", "xhigh"]),
          ("mimo-2-6-flash", "mimo-v2.6-flash", ["low", "medium", "high"]),
          ("deepseek-v4-1-flash", "deepseek-v4.1-flash", ["low", "high", "max"])]
WF = {"risk-limit-breach-day": "risk-limit breach", "ops-settlement-day": "ops settlement",
      "risk-manager-control-day": "risk-manager control", "high-board-portfolio-review-day": "high-board review",
      "trader-rfq-booking-day": "trader RFQ", "confirmation-desk-day": "confirmation desk"}
HUE = "#3b6fb0"                       # the site's semantic `mid` data hue (validated, both surfaces)
SANS = "font-family:var(--sans,-apple-system,'Inter','Segoe UI',Helvetica,Arial,sans-serif)"
W, H = 228, 196
ML, MR, MT, MB = 34, 12, 30, 30
PADX = 16


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def arm(model, eff):
    return [a for a in AR if a["model"] == model and a["effort"] == eff]


def trials(model, eff):
    return [t for t in TR if t["model"] == model and t["effort"] == eff]


def reused(model, eff):
    return eff == "high"              # high comes from #143/#144 for every model


def panel(title, levels, series, wf_points, y0, y1, yticks, fmt, unit, xlog=None, values=True, labels=None):
    """series: [(x_key, y, tooltip)]; wf_points: [(x_key, y, tooltip)]."""
    pw, ph = W - ML - MR, H - MT - MB
    if xlog:
        lo, hi = math.log10(xlog[0]), math.log10(xlog[1])
        X = lambda k: ML + PADX + (math.log10(k) - lo) / (hi - lo) * (pw - 2 * PADX)
    else:
        step = (pw - 2 * PADX) / (len(levels) - 1)
        X = lambda k: ML + PADX + levels.index(k) * step
    Y = lambda v: MT + (1 - (v - y0) / (y1 - y0)) * ph
    o = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="{escape(title)}" style="max-width:100%;height:auto;{SANS}">',
         f'<text x="{ML}" y="16" style="fill:var(--ink);font-size:12px;font-weight:700">{escape(title)}</text>']
    for v in yticks:                                    # recessive grid + labels
        o.append(f'<line x1="{ML}" x2="{W-MR}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" style="stroke:var(--line);stroke-width:1"/>')
        o.append(f'<text x="{ML-6}" y="{Y(v)+3.5:.1f}" text-anchor="end" style="fill:var(--muted);font-size:10px">{fmt(v)}</text>')
    if xlog:
        for v, lab in ((1e3, "1k"), (1e4, "10k"), (1e5, "100k"), (1e6, "1M")):
            if xlog[0] <= v <= xlog[1]:
                o.append(f'<text x="{X(v):.1f}" y="{H-10}" text-anchor="middle" style="fill:var(--muted);font-size:10px">{lab}</text>')
    else:
        for k in levels:
            o.append(f'<text x="{X(k):.1f}" y="{H-10}" text-anchor="middle" style="fill:var(--muted);font-size:10.5px">{k}</text>')
    for xk, y, tip in wf_points:                        # per-workflow cells: faint, behind
        n = sum(1 for p in wf_points if p[0] == xk and p[1] <= y)
        jx = (n % 3 - 1) * 4
        o.append(f'<circle cx="{X(xk)+jx:.1f}" cy="{Y(y):.1f}" r="3" style="fill:none;stroke:var(--muted);stroke-width:1;opacity:.55"><title>{escape(tip)}</title></circle>')
    pts = [(X(xk), Y(y)) for xk, y, _ in series]
    o.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
             + f'" style="fill:none;stroke:{HUE};stroke-width:2;stroke-linejoin:round"/>')
    for (xk, y, tip), (x, yy) in zip(series, pts):
        hollow = "(re-used" in tip
        fill = "var(--paper,#fff)" if hollow else HUE
        o.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="5" style="fill:{fill};stroke:{HUE if hollow else "var(--paper,#fff)"};stroke-width:2"><title>{escape(tip)}</title></circle>')
        if values:
            o.append(f'<text x="{x:.1f}" y="{yy-9:.1f}" text-anchor="middle" style="fill:var(--ink);font-size:10.5px;font-weight:600;paint-order:stroke;stroke:var(--paper,#fff);stroke-width:3px;stroke-linejoin:round">{fmt(y)}{unit}</text>')
    if labels:                                          # greedy, collision-free placement
        CW, CH = 6.0, 11.0                              # ~10.5px sans: char width, line height
        samples = []                                    # points along the polyline
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            samples += [(x1 + (x2 - x1) * t / 12, y1 + (y2 - y1) * t / 12) for t in range(13)]
        placed = []

        def box(x, y, anchor, text):
            w = len(text) * CW
            x0 = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
            return (x0 - 1, y - CH + 2, x0 + w + 1, y + 2)

        def clear(b):
            hit = lambda px, py, r: b[0] - r < px < b[2] + r and b[1] - r < py < b[3] + r
            return (not any(hit(px, py, 6) for px, py in pts) and not any(hit(px, py, 1) for px, py in samples)
                    and not any(b[0] < q[2] and q[0] < b[2] and b[1] < q[3] and q[1] < b[3] for q in placed)
                    and b[0] >= ML and b[2] <= W - 2 and b[1] >= MT - 4 and b[3] <= H - MB + 2)

        for i, (x, yy) in enumerate(pts):
            text = labels[i]
            for dx, dy, anchor in ((0, -10, "middle"), (0, 18, "middle"), (9, 4, "start"), (-9, 4, "end"),
                                   (0, -22, "middle"), (0, 30, "middle"), (9, -8, "start"), (-9, -8, "end"),
                                   (9, 16, "start"), (-9, 16, "end")):
                b = box(x + dx, yy + dy, anchor, text)
                if clear(b):
                    break
            placed.append(b)
            o.append(f'<text x="{x+dx:.1f}" y="{yy+dy:.1f}" text-anchor="{anchor}" style="fill:var(--ink);font-size:10.5px;font-weight:600;paint-order:stroke;stroke:var(--paper,#fff);stroke-width:3px;stroke-linejoin:round">{text}</text>')
    o.append("</svg>")
    return "".join(o)


def figure(panels, caption):
    return ('<figure class="chart effort-fig"><div style="display:flex;flex-wrap:wrap;gap:6px 14px;justify-content:center">'
            + "".join(panels) + f'</div><figcaption>{caption}</figcaption></figure>')


def fig_score():
    ps = []
    for mid, label, levels in MODELS:
        s, w = [], []
        for e in levels:
            arms = arm(mid, e)
            m = mean([a["objective"] for a in arms])
            s.append((e, m, f"{label} · {e}: mean objective {m:.1f} over 6 workflows"
                      + (" (re-used from #143/#144)" if reused(mid, e) else "")))
            w += [(e, a["objective"], f"{WF[a['workflow']]} · {e}: {a['objective']:.1f}") for a in arms]
        ps.append(panel(label, levels, s, w, 70, 104, [70, 80, 90, 100], lambda v: f"{v:.0f}" if v % 10 == 0 else f"{v:.1f}", ""))
    return figure(ps, "Objective score by reasoning effort. Line = mean over six workflows; faint circles = each "
                      "workflow's cell (2 trials). Hollow marker = <code>high</code>, re-used from runs #143/#144.")


def fig_calls():
    ps = []
    for mid, label, levels in MODELS:
        s, w = [], []
        for e in levels:
            ts = trials(mid, e)
            m = mean([t["tool_calls"] for t in ts])
            s.append((e, m, f"{label} · {e}: {m:.0f} tool calls per trial (mean of {len(ts)} trials)"
                      + (" (re-used from #143/#144)" if reused(mid, e) else "")))
            byw = defaultdict(list)
            for t in ts:
                byw[t["workflow"]].append(t["tool_calls"])
            w += [(e, mean(v), f"{WF[k]} · {e}: {mean(v):.0f} tool calls") for k, v in byw.items()]
        ps.append(panel(label, levels, s, w, 0, 420, [0, 100, 200, 300, 400], lambda v: f"{v:.0f}", ""))
    return figure(ps, "Tool calls per trial by reasoning effort. Line = mean over all trials; faint circles = each "
                      "workflow's mean. Hollow marker = <code>high</code>, re-used from runs #143/#144.")


def fig_tokens():
    ps = []
    for mid, label, levels in MODELS:
        s = []
        for e in levels:
            ts = trials(mid, e)
            rt = mean([t["reasoning_tokens"] for t in ts])
            ob = mean([a["objective"] for a in arm(mid, e)])
            s.append((max(rt, 500), ob, f"{label} · {e}: {rt/1e3:.1f}k reasoning tokens per trial, objective {ob:.1f}"
                      + (" (re-used from #143/#144)" if reused(mid, e) else "")))
        p = panel(label, None, s, [], 88, 98.5, [88, 90, 92, 94, 96, 98], lambda v: f"{v:.0f}", "",
                  xlog=(500, 1e6), values=False, labels=levels)
        ps.append(p)
    return figure(ps, "Objective score against measured reasoning tokens per trial (log scale, shared across panels). "
                      "Same models, read on a common axis: effort labels are vendor-specific, tokens are not.")


out = {"score": fig_score(), "calls": fig_calls(), "tokens": fig_tokens()}
json.dump(out, open(sys.argv[2], "w"))
print({k: len(v) for k, v in out.items()})
