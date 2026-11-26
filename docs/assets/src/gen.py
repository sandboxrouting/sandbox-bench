"""Generate the README illustrations for sandbox-bench as hand-tuned SVG.

Run: uvx --with fonttools python gen.py <out_dir>
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

LIGHT = dict(
    bg="#F2F6F4", panel="#FFFFFF", ink="#12272B", muted="#4F6467", faint="#7E9193",
    grid="#DCE5E1", rule="#C2CFCA", alive="#0A7A5C", alivefill="#E2F2EB",
    act="#4A54C4", actfill="#E7E9F8", fail="#BB3226", failfill="#FBEAE7",
)
DARK = dict(
    bg="#0F1719", panel="#141F21", ink="#E1EBE7", muted="#9AACA9", faint="#6E8280",
    grid="#1E2C2D", rule="#2D3E3F", alive="#43D19E", alivefill="#10302A",
    act="#9AA2F7", actfill="#1A2036", fail="#F2705F", failfill="#3A1D1A",
)
SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"


def svg(w, h, body, title, desc):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="t d">\n'
        f"<title id=\"t\">{escape(title)}</title>\n<desc id=\"d\">{escape(desc)}</desc>\n"
        + body
        + "\n</svg>\n"
    )


# ---------------------------------------------------------------- glyph paths (hero only)
FONT_DIR = "/usr/share/fonts/adobe-source-code-pro-fonts/"


class Glyphs:
    """Source Code Pro (OFL) outlines as <defs>, so the hero needs no installed font."""

    def __init__(self):
        self.fonts = {}
        self.defs = {}

    def font(self, weight):
        if weight not in self.fonts:
            self.fonts[weight] = TTFont(FONT_DIR + f"SourceCodePro-{weight}.otf")
        return self.fonts[weight]

    def gid(self, weight, ch):
        f = self.font(weight)
        name = f.getBestCmap()[ord(ch)]
        key = f"g{weight[0]}{ord(ch):x}"
        if key not in self.defs:
            gs = f.getGlyphSet()
            pen = SVGPathPen(gs, ntos=lambda v: f"{round(v)}")
            gs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            d = pen.getCommands()
            self.defs[key] = f'<path id="{key}" d="{d}"/>' if d else ""
        return key if self.defs[key] else None

    def text(self, s, x, y, size, weight="Regular", fill="#000", anchor="start", spacing=0.0):
        adv = 600 * size / 1000 + spacing  # monospaced: 600 units
        width = adv * len(s) - spacing
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        k = size / 1000
        uses = []
        for i, ch in enumerate(s):
            g = self.gid(weight, ch)
            if g:
                gx = x + i * adv
                uses.append(f'<use xlink:href="#{g}" transform="translate({gx:.1f} {y}) scale({k:.4f})"/>')
        return f'<g fill="{fill}">' + "".join(uses) + "</g>", width

    def defs_block(self):
        return "<defs>" + "".join(v for v in self.defs.values() if v) + "</defs>"


# ---------------------------------------------------------------- 1. hero
def hero(P):
    W, H = 1280, 470
    G = Glyphs()
    b = []
    b.append(f'<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="18" fill="{P["bg"]}" stroke="{P["rule"]}" stroke-width="1.5" stroke-opacity="0.6"/>')
    # trace area
    x0, base, dx, dy = 64, 420, 24, 4.4
    for gy in range(260, 421, 40):
        b.append(f'<line x1="{x0}" y1="{gy}" x2="1216" y2="{gy}" stroke="{P["grid"]}" stroke-width="1"/>')
    for tx in range(x0, 1217, 48):
        b.append(f'<line x1="{tx}" y1="{base + 6}" x2="{tx}" y2="{base + 14}" stroke="{P["rule"]}" stroke-width="1.5"/>')

    bands = [(376, 496, "pause → resume"), (664, 784, "snapshot → restore")]
    for (a, z, label) in bands:
        b.append(f'<rect x="{a}" y="250" width="{z - a}" height="{base + 14 - 250}" fill="{P["actfill"]}"/>')
        b.append(f'<line x1="{a}" y1="250" x2="{a}" y2="{base + 14}" stroke="{P["act"]}" stroke-width="1.5" stroke-dasharray="3 5"/>')
        b.append(f'<line x1="{z}" y1="250" x2="{z}" y2="{base + 14}" stroke="{P["act"]}" stroke-width="1.5" stroke-dasharray="3 5"/>')
        t, _ = G.text(label, (a + z) / 2, 238, 20, "Medium", P["act"], "middle")
        b.append(t)
    fork_x = 928
    b.append(f'<line x1="{fork_x}" y1="250" x2="{fork_x}" y2="{base + 14}" stroke="{P["act"]}" stroke-width="1.5" stroke-dasharray="3 5"/>')
    t, _ = G.text("fork", fork_x, 238, 20, "Medium", P["act"], "middle")
    b.append(t)

    def stairs(x, v, x_end):
        pts = []
        while x < x_end - 0.1:
            y = base - v * dy
            pts += [f"{x},{y}", f"{x + dx},{y}"]
            x += dx
            v += 1
            pts.append(f"{x},{base - v * dy}")
        return pts, v

    line = f'fill="none" stroke="{P["alive"]}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"'
    held = f'fill="none" stroke="{P["alive"]}" stroke-width="3" stroke-dasharray="1 7" stroke-linecap="round"'
    p1, v = stairs(x0, 0, 376)
    b.append(f'<polyline points="{" ".join(p1)}" {line}/>')
    yv = base - v * dy
    b.append(f'<line x1="376" y1="{yv}" x2="496" y2="{yv}" {held}/>')
    held_vals = [(376, 496, v)]
    p2, v = stairs(496, v, 664)
    b.append(f'<polyline points="{" ".join(p2)}" {line}/>')
    yv = base - v * dy
    b.append(f'<line x1="664" y1="{yv}" x2="784" y2="{yv}" {held}/>')
    held_vals.append((664, 784, v))
    p3, v = stairs(784, v, fork_x)
    b.append(f'<polyline points="{" ".join(p3)}" {line}/>')
    vf = v
    # parent
    p4, vp = stairs(fork_x, vf, 1120)
    b.append(f'<polyline points="{" ".join(p4)}" {line}/>')
    # child: drops into its own lane, same value, keeps counting
    off = 52
    yf = base - vf * dy
    b.append(
        f'<path d="M{fork_x},{yf} C{fork_x + 18},{yf} {fork_x + 14},{yf + off} {fork_x + 34},{yf + off}" {line}/>'
    )
    p5, vc = stairs(fork_x + 34, vf, 1120)
    p5 = [f"{px},{float(py) + off}" for px, py in (q.split(",") for q in p5)]
    b.append(f'<polyline points="{" ".join(p5)}" {line}/>')
    # continuity dots at each hand-over
    for (a, z, vv) in held_vals:
        t, _ = G.text(f"i={vv}", (a + z) / 2, base - vv * dy - 14, 17, "Medium", P["alive"], "middle")
        b.append(t)
    for cx, cy in ((x0, base),):
        b.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{P["alive"]}"/>')
    for cy in (base - vp * dy, base - vc * dy + off):
        b.append(f'<circle cx="1120" cy="{cy}" r="11" fill="{P["alive"]}" opacity="0.18"/>')
        b.append(f'<circle cx="1120" cy="{cy}" r="5.5" fill="{P["alive"]}"/>')
        t, _ = G.text("pid 2008", 1142, cy + 7, 19, "Medium", P["alive"])
        b.append(t)

    # type
    t, _ = G.text("sandbox-bench", 62, 120, 74, "Bold", P["ink"], spacing=-2)
    b.append(t)
    q1 = "Does your sandbox really keep your agent's running process"
    q2 = "when you pause, snapshot or fork it, and how fast?"
    for i, q in enumerate((q1, q2)):
        t, _ = G.text(q, 66, 172 + i * 38, 26, "Regular", P["muted"])
        b.append(t)

    body = G.defs_block() + "\n" + "\n".join(b)
    return svg(
        W, H, body, "sandbox-bench",
        "Does your sandbox really keep your agent's running process when you pause, snapshot or fork it, "
        "and how fast? A process counter keeps rising through pause, snapshot and fork; after the fork, "
        "parent and child both still run pid 2008.",
    )


# ---------------------------------------------------------------- shared diagram helpers
def T(x, y, s, P, size=20, fill="ink", weight=400, anchor="start", font=SANS, extra=""):
    color = P.get(fill, fill)
    size = round(size * P.get("fs", 1), 1)
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}"{extra}>{escape(s)}</text>'
    )


def M(x, y, s, P, size=17, fill="muted", weight=400, anchor="start"):
    return T(x, y, s, P, size, fill, weight, anchor, MONO)


def card(x, y, w, h, P, stroke="rule", fill="panel", rx=10, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{P.get(fill, fill)}" '
        f'stroke="{P.get(stroke, stroke)}" stroke-width="{sw}"{d}/>'
    )


def arrow_defs(P):
    out = []
    for name in ("ink", "alive", "act", "fail", "faint"):
        out.append(
            f'<marker id="a-{name}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="9" markerHeight="9" '
            f'orient="auto-start-reverse"><path d="M1,1.2 L9,5 L1,8.8 Z" fill="{P[name]}"/></marker>'
        )
    return "<defs>" + "".join(out) + "</defs>"


def tick(cx, cy, P, ok=True):
    c = P["alive"] if ok else P["fail"]
    if ok:
        mark = f'<path d="M{cx - 6},{cy} l4.5,4.5 l8,-9" fill="none" stroke="{P["panel"]}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
    else:
        mark = (
            f'<path d="M{cx - 5},{cy - 5} l10,10 M{cx + 5},{cy - 5} l-10,10" fill="none" stroke="{P["panel"]}" '
            f'stroke-width="2.6" stroke-linecap="round"/>'
        )
    return f'<circle cx="{cx}" cy="{cy}" r="12" fill="{c}"/>' + mark


# ---------------------------------------------------------------- 2. memory check
def memory(P):
    W, H = 1200, 676
    b = [arrow_defs(P)]
    # column heads (a real sequence: before, action, after)
    heads = [(0, "1", "Before the action"), (372, "2", "The action"), (792, "3", "After: all three must hold")]
    for x, n, s in heads:
        b.append(f'<circle cx="{x + 14}" cy="22" r="14" fill="none" stroke="{P["ink"]}" stroke-width="1.5"/>')
        b.append(T(x + 14, 28, n, P, 16, "ink", 600, "middle"))
        b.append(T(x + 38, 29, s, P, 21, "ink", 600))
    b.append(T(410, 56, "pause → resume, snapshot → restore,", P, 17, "act"))
    b.append(T(410, 78, "or fork (checked in the child)", P, 17, "act"))

    # ---- before card
    b.append(card(0, 104, 340, 520, P))
    y = 140
    b.append(T(22, y, "Inside the sandbox, start", P, 18, "muted"))
    b.append(card(22, y + 14, 296, 92, P, "rule", "bg", 6, 1))
    b.append(M(36, y + 42, "sh loop, i in memory:", P, 16, "ink"))
    b.append(M(36, y + 66, "i=$((i+1)); sleep 0.5", P, 16, "alive"))
    b.append(M(36, y + 90, "→ writes i to ~/.sbx/", P, 15, "muted"))
    y = 276
    b.append(card(22, y, 296, 66, P, "rule", "bg", 6, 1))
    b.append(M(36, y + 28, "32 MiB random bytes", P, 16, "ink"))
    b.append(M(36, y + 52, "→ /dev/shm (RAM)", P, 15, "muted"))
    y = 380
    b.append(T(22, y, "Then record", P, 18, "muted"))
    rec = [
        ("PID", "2008"),
        ("start time", "28250874"),
        ("command line", "sh -c …"),
        ("/dev/shm sha256", "2c61e18d…"),
        ("counter v0", "1"),
    ]
    for i, (k, v) in enumerate(rec):
        yy = y + 36 + i * 40
        b.append(T(22, yy, k, P, 17, "ink"))
        b.append(M(318, yy, v, P, 16, "ink", 500, "end"))
        if i < len(rec) - 1:
            b.append(f'<line x1="22" y1="{yy + 14}" x2="318" y2="{yy + 14}" stroke="{P["grid"]}" stroke-width="1"/>')

    # ---- lanes
    def lane(top, ok):
        h = 248
        col = "alive" if ok else "fail"
        b.append(card(372, top, 828, h, P, col, "panel", 10, 1.5))
        b.append(f'<rect x="372" y="{top}" width="6" height="{h}" rx="3" fill="{P[col]}"/>')
        label = "Same process kept: pass" if ok else "Sandbox restarted: fail"
        b.append(T(396, top + 34, label, P, 19, col, 600))
        # plot
        px0, px1 = 396, 760
        base = top + h - 40
        b.append(f'<line x1="{px0}" y1="{base}" x2="{px1}" y2="{base}" stroke="{P["rule"]}" stroke-width="1.5"/>')
        b.append(T(px1, base + 26, "time", P, 15, "faint", 400, "end"))
        ax0, ax1 = 520, 590  # action band
        b.append(f'<rect x="{ax0}" y="{top + 56}" width="{ax1 - ax0}" height="{base - top - 56}" fill="{P["actfill"]}"/>')
        b.append(T((ax0 + ax1) / 2, top + 78, "action", P, 15, "act", 500, "middle"))
        step, rise = 16, 7
        # before: counts up to v0
        pts, x, yv = [], px0, base - 8
        n0 = 7
        for _ in range(n0):
            pts += [f"{x},{yv}", f"{x + step},{yv}"]
            x += step
            yv -= rise
            pts.append(f"{x},{yv}")
        # last step lands just before band
        pts.append(f"{ax0},{yv}")
        y_v0 = yv
        line = f'fill="none" stroke="{P["alive"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"'
        b.append(f'<polyline points="{" ".join(pts)}" {line}/>')
        b.append(f'<circle cx="{ax0 - 14}" cy="{y_v0}" r="5" fill="{P["ink"]}"/>')
        b.append(M(ax0 - 14, y_v0 - 14, "v0", P, 15, "ink", 600, "middle"))
        if ok:
            b.append(f'<line x1="{ax0}" y1="{y_v0}" x2="{ax1}" y2="{y_v0}" fill="none" stroke="{P["alive"]}" stroke-width="2.5" stroke-dasharray="1 6" stroke-linecap="round"/>')
            pts, x, yv = [], ax1, y_v0
            for _ in range(10):
                pts += [f"{x},{yv}", f"{x + step},{yv}"]
                x += step
                yv -= rise * 0.8
                if x < px1 - 4:
                    pts.append(f"{x},{yv}")
            b.append(f'<polyline points="{" ".join(pts)}" {line}/>')
            # r1, r2 reads
            r1x, r2x = ax1 + 3 * step + 8, ax1 + 3 * step + 8 + 96
            r1y = y_v0 - 3 * rise * 0.8
            r2y = y_v0 - 9 * rise * 0.8
            for (rx, ry, nm) in ((r1x, r1y, "r1"), (r2x, r2y, "r2")):
                b.append(f'<circle cx="{rx}" cy="{ry}" r="5" fill="{P["ink"]}"/>')
                b.append(M(rx, ry - 14, nm, P, 15, "ink", 600, "middle"))
            by = base - 16
            b.append(f'<path d="M{r1x},{by - 6} v6 h{r2x - r1x} v-6" fill="none" stroke="{P["muted"]}" stroke-width="1.5"/>')
            b.append(T((r1x + r2x) / 2, by + 18, "≥ 2 s", P, 15, "muted", 500, "middle"))
        else:
            # boot again: nothing writes the counter; the file is stale
            b.append(f'<line x1="{ax1}" y1="{y_v0}" x2="{px1 - 10}" y2="{y_v0}" stroke="{P["fail"]}" stroke-width="2.5" stroke-dasharray="7 6"/>')
            r1x, r2x = ax1 + 3 * step + 8, ax1 + 3 * step + 8 + 96
            for (rx, nm) in ((r1x, "r1"), (r2x, "r2")):
                b.append(f'<circle cx="{rx}" cy="{y_v0}" r="5" fill="{P["fail"]}"/>')
                b.append(M(rx, y_v0 - 14, nm, P, 15, "fail", 600, "middle"))
            b.append(T((r1x + r2x) / 2, y_v0 - 40, "stale counter file", P, 15, "fail", 500, "middle"))
            by = base - 16
            b.append(f'<path d="M{r1x},{by - 6} v6 h{r2x - r1x} v-6" fill="none" stroke="{P["muted"]}" stroke-width="1.5"/>')
            b.append(T((r1x + r2x) / 2, by + 18, "≥ 2 s", P, 15, "muted", 500, "middle"))

        # checks
        cx = 800
        rows = (
            [
                ("Same PID, start time, cmdline", "2008, 28250874 both times"),
                ("Same /dev/shm hash", "2c61e18d… = 2c61e18d…"),
                ("Still counting: v0 ≤ r1 < r2", "1 ≤ 4 < 9"),
            ]
            if ok
            else [
                ("New process start time", "a fresh boot, or no process"),
                ("/dev/shm is empty", "no buffer, no hash to match"),
                ("Not counting: r1 = r2", "only the old counter file left"),
            ]
        )
        b.append(f'<line x1="{cx - 22}" y1="{top + 20}" x2="{cx - 22}" y2="{top + h - 20}" stroke="{P["grid"]}" stroke-width="1.5"/>')
        for i, (k, v) in enumerate(rows):
            yy = top + 54 + i * 66
            b.append(tick(cx + 12, yy - 6, P, ok))
            b.append(T(cx + 36, yy, k, P, 18, "ink", 500))
            b.append(M(cx + 36, yy + 24, v, P, 15, "muted"))

    lane(104, True)
    lane(376, False)
    b.append(
        T(0, 664, "Pass-lane values are from a real attempt: freestyle, pause-keeps-memory, run 20261126-120712-d541.",
          P, 15, "faint")
    )
    return svg(
        W, H, "\n".join(b), "The memory check",
        "Before the action the harness starts an sh counter loop and a 32 MiB /dev/shm buffer, and records PID, "
        "start time, command line, buffer hash and the counter value v0. After pause and resume, snapshot and "
        "restore, or fork, it passes only if the same process is running, the buffer hash matches, and two "
        "counter reads at least 2 seconds apart show v0 <= r1 < r2. A restarted sandbox fails all three.",
    )


# ---------------------------------------------------------------- 3. how a run works
def run(P):
    W, H = 1200, 506
    b = [arrow_defs(P)]

    def head(x, y, s, size=20, col="ink"):
        b.append(T(x, y, s, P, size, col, 600))

    def numbered(cx, cy, n):
        b.append(f'<circle cx="{cx}" cy="{cy}" r="13" fill="{P["bg"]}" stroke="{P["ink"]}" stroke-width="1.5"/>')
        b.append(T(cx, cy + 5.5, n, P, 15, "ink", 600, "middle"))

    # Row 1: the measuring loop
    b.append(T(0, 22, "Started by a maintainer, from one workflow", P, 16, "faint", 500))
    b.append(card(0, 40, 290, 196, P))
    head(22, 76, "Runner")
    b.append(T(22, 106, "GitHub Actions, from main", P, 17, "muted"))
    b.append(T(22, 132, "started by hand", P, 17, "muted"))
    b.append(card(22, 152, 246, 62, P, "rule", "bg", 6, 1))
    b.append(M(36, 178, "sbx run", P, 16, "ink", 600))
    b.append(M(36, 200, "10 attempts per probe", P, 14, "muted"))

    b.append(card(400, 40, 280, 196, P))
    head(422, 76, "Adapters")
    b.append(T(422, 106, "one per provider", P, 17, "muted"))
    for i, nm in enumerate(("daytona.py", "freestyle.py", "<you>.py")):
        b.append(card(422, 124 + i * 34, 236, 28, P, "rule", "bg", 5, 1, "4 4" if i == 2 else None))
        b.append(M(434, 143 + i * 34, nm, P, 15, "ink" if i < 2 else "faint"))

    # providers: stacked cloud sandboxes
    b.append(card(830, 40, 370, 196, P))
    head(852, 76, "Providers")
    b.append(T(852, 106, "every sandbox 2 vCPU / 4 GiB", P, 17, "muted"))
    for i, nm in enumerate(("Daytona", "Freestyle", "…")):
        x = 852 + i * 114
        b.append(card(x, 124, 104, 90, P, "alive" if i < 2 else "rule", "bg", 8, 1.5, None if i < 2 else "4 4"))
        b.append(T(x + 52, 150, nm, P, 15, "ink" if i < 2 else "faint", 500, "middle"))
        if i < 2:
            # little live counter inside each sandbox
            pts, xx, yy = [], x + 18, 200
            for _ in range(4):
                pts += [f"{xx},{yy}", f"{xx + 17},{yy}"]
                xx += 17
                yy -= 8
                pts.append(f"{xx},{yy}")
            b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{P["alive"]}" stroke-width="2.5" stroke-linejoin="round"/>')

    # arrows row 1
    for x1, x2, top_label, bottom_label in (
        (290, 400, "probes", "timings"),
        (680, 830, "pause, fork…", "responses"),
    ):
        b.append(f'<line x1="{x1 + 6}" y1="128" x2="{x2 - 6}" y2="128" stroke="{P["ink"]}" stroke-width="2" marker-end="url(#a-ink)"/>')
        b.append(f'<line x1="{x2 - 6}" y1="150" x2="{x1 + 6}" y2="150" stroke="{P["faint"]}" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#a-faint)"/>')
        b.append(T((x1 + x2) / 2, 114, top_label, P, 14, "ink", 500, "middle"))
        b.append(T((x1 + x2) / 2, 172, bottom_label, P, 14, "muted", 400, "middle"))
    numbered(345, 88, "1")
    b.append(T(755, 96, "create, exec,", P, 14, "ink", 500, "middle"))
    b.append(T(408, 264, "Probes run shuffled, one operation in flight.", P, 15, "muted"))
    b.append(T(408, 286, "A failing provider is a result: the run carries on.", P, 15, "muted"))

    # Row 2: publish
    y2 = 312
    b.append(card(0, y2, 452, 190, P))
    head(22, y2 + 36, "Results repo")
    b.append(T(22, y2 + 64, "raw run records, append-only, never edited", P, 17, "muted"))
    b.append(card(22, y2 + 84, 408, 84, P, "rule", "bg", 6, 1))
    b.append(M(36, y2 + 112, "runs/2026/11/26/", P, 15, "muted"))
    b.append(M(54, y2 + 136, "20261126-120712-d541.json", P, 15, "ink", 500))
    b.append(M(54, y2 + 158, "… one RunRecord per run", P, 14, "faint"))

    b.append(card(552, y2 + 50, 220, 90, P, "act", "panel", 10, 1.5))
    b.append(M(662, y2 + 88, "sbx report", P, 17, "act", 600, "middle"))
    b.append(M(662, y2 + 114, "runs --out board", P, 15, "act", 400, "middle"))

    b.append(card(900, y2, 300, 190, P))
    head(922, y2 + 36, "Leaderboard")
    b.append(M(922, y2 + 64, "board/leaderboard.md", P, 14, "muted"))
    b.append(M(922, y2 + 86, "board/results.json", P, 14, "muted"))
    # mini table
    for i, w in enumerate((210, 168, 120)):
        yy = y2 + 108 + i * 22
        b.append(f'<rect x="922" y="{yy}" width="16" height="14" rx="3" fill="{P["faint"]}" opacity="0.5"/>')
        b.append(f'<rect x="946" y="{yy}" width="{w}" height="14" rx="3" fill="{P["alive"] if i == 0 else P["rule"]}" opacity="{0.9 if i == 0 else 1}"/>')

    # runner -> results repo (elbow)
    b.append(f'<line x1="150" y1="236" x2="150" y2="{y2 - 6}" stroke="{P["ink"]}" stroke-width="2" marker-end="url(#a-ink)"/>')
    numbered(150, 272, "2")
    b.append(T(176, 278, "raw run record", P, 14, "ink", 500))
    b.append(f'<line x1="458" y1="{y2 + 95}" x2="546" y2="{y2 + 95}" stroke="{P["ink"]}" stroke-width="2" marker-end="url(#a-ink)"/>')
    numbered(502, y2 + 70, "3")
    b.append(T(502, y2 + 128, "all runs", P, 14, "muted", 400, "middle"))
    b.append(f'<line x1="778" y1="{y2 + 95}" x2="894" y2="{y2 + 95}" stroke="{P["ink"]}" stroke-width="2" marker-end="url(#a-ink)"/>')
    numbered(836, y2 + 70, "4")
    b.append(T(836, y2 + 128, "commit, push", P, 14, "muted", 400, "middle"))
    return svg(
        W, H, "\n".join(b), "How a run works",
        "A maintainer starts the Benchmark run workflow, which runs sbx run: adapters drive each provider's "
        "sandboxes through 10 attempts of every offered probe. The raw run record is written to a separate "
        "results repo, sbx report scores it, and the leaderboard tables are committed and pushed.",
    )


# ---------------------------------------------------------------- 4. sbx check capture
def terminal(lines):
    P = DARK
    fs, lh = 15, 23
    cw = fs * 0.6
    width_chars = max(len(s) for s in lines) + 2
    W = int(48 + width_chars * cw + 24)
    top = 58
    H = top + lh * len(lines) + 30
    b = [f'<rect width="{W}" height="{H}" rx="12" fill="#0B1214"/>']
    b.append(f'<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="11.5" fill="none" stroke="#24333A" stroke-width="1.5"/>')
    b.append(f'<path d="M0.75,38 H{W - 0.75}" stroke="#1B272B" stroke-width="1"/>')
    for i, c in enumerate(("#3A4A4F", "#3A4A4F", "#3A4A4F")):
        b.append(f'<circle cx="{24 + i * 20}" cy="19.5" r="6" fill="{c}"/>')
    b.append(T(W / 2, 25, "sandbox-bench", P, 13, "faint", 500, "middle", MONO))

    ink, dim, green, act, faint = P["ink"], "#5E7472", P["alive"], P["act"], P["faint"]

    def span(s, color, weight=None):
        w = f' font-weight="{weight}"' if weight else ""
        return f'<tspan fill="{color}"{w}>{escape(s)}</tspan>'

    def render(s):
        if s.startswith("$ "):
            return span("$ ", green, 600) + span(s[2:], ink, 600)
        if s.startswith("wrote "):
            return span(s, faint)
        if s.startswith("**"):
            name, rest = s.split("**, ", 1)
            return span("**", dim) + span(name[2:], ink, 700) + span("**, " + rest, faint)
        if s.startswith("|---"):
            return span(s, dim)
        if s.startswith("|"):
            cells = s.split("|")[1:-1]
            out = span("|", dim)
            header = cells[0].strip() == "Probe"
            for c in cells:
                st = c.strip()
                if header:
                    col, wt = ink, 600
                elif st == "pass":
                    col, wt = green, 600
                elif st == "fail":
                    col, wt = P["fail"], 600
                elif "/" in st and st.replace("/", "").isdigit():
                    col, wt = ink, None
                elif st and st[0].isupper():
                    col, wt = act, None
                else:
                    col, wt = ink, None
                out += span(c, col, wt) + span("|", dim)
            return out
        return span(s, faint)

    for i, s in enumerate(lines):
        y = top + 16 + i * lh
        if s:
            b.append(
                f'<text x="24" y="{y}" font-family="{MONO}" font-size="{fs}" xml:space="preserve">{render(s)}</text>'
            )
    return svg(
        W, H, "\n".join(b), "sbx check freestyle",
        "Terminal output of sbx check freestyle from a real run on 2026-11-26: all 11 probes passed, 1 of 1 attempt each.",
    )


if __name__ == "__main__":
    for nm, P in (("light", LIGHT), ("dark", DARK)):
        P = dict(P, fs=1.1)
        (OUT / f"hero-{nm}.svg").write_text(hero(P))
        (OUT / f"memory-check-{nm}.svg").write_text(memory(P))
        (OUT / f"how-a-run-works-{nm}.svg").write_text(run(P))
    cap = Path(sys.argv[2]).read_text().rstrip("\n").split("\n") if len(sys.argv) > 2 else []
    if cap:
        (OUT / "sbx-check-freestyle.svg").write_text(terminal(cap))
