"""Generate the README illustrations for sandbox-bench as hand-tuned SVG.

Run: uvx --with fonttools --with uharfbuzz python gen.py <out_dir> [capture.txt]

Text in the illustrations is set in Schibsted Grotesk (fonts/, SIL OFL), the typeface of
sbbench.com, and converted to outlines, so every viewer sees the same thing without the font.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path(__file__).resolve().parent / "fonts" / "SchibstedGrotesk.ttf"

LIGHT = dict(
    bg="#F2F6F4", panel="#FFFFFF", ink="#12272B", muted="#4F6467", faint="#7E9193",
    grid="#DCE5E1", rule="#C2CFCA", alive="#0A7A5C", alivefill="#E2F2EB",
    act="#4A54C4", actfill="#E7E9F8", fail="#BB3226", failfill="#FBEAE7",
    cube_t="#4CC297", cube_l="#0A7A5C", cube_r="#075A44",
)
DARK = dict(
    bg="#0F1719", panel="#141F21", ink="#E1EBE7", muted="#9AACA9", faint="#6E8280",
    grid="#1E2C2D", rule="#2D3E3F", alive="#43D19E", alivefill="#10302A",
    act="#9AA2F7", actfill="#1A2036", fail="#F2705F", failfill="#3A1D1A",
    cube_t="#A6EFD2", cube_l="#43D19E", cube_r="#24966F",
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


# ---------------------------------------------------------------- type as outlines
class Type:
    """Shapes text with HarfBuzz (kerning included) and emits glyph outlines as <use>s."""

    def __init__(self):
        self.face = hb.Face(hb.Blob.from_file_path(str(FONT)))
        self.static = {}
        self.defs = {}

    def _glyphs(self, weight):
        if weight not in self.static:
            font = instantiateVariableFont(TTFont(FONT), {"wght": weight})
            self.static[weight] = (font.getGlyphSet(), font.getGlyphOrder())
        return self.static[weight]

    def _shape(self, s, weight):
        font = hb.Font(self.face)
        font.set_variations({"wght": weight})
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, s, size, weight=400, tracking=0.0):
        _, pos = self._shape(s, weight)
        k = size / self.face.upem
        return sum(p.x_advance for p in pos) * k + tracking * (len(pos) - 1)

    def text(self, s, x, y, size, fill, weight=400, anchor="start", tracking=0.0):
        infos, pos = self._shape(s, weight)
        k = size / self.face.upem
        w = self.width(s, size, weight, tracking)
        x -= {"start": 0, "middle": w / 2, "end": w}[anchor]
        glyphs, order = self._glyphs(weight)
        uses, cx = [], x
        for info, p in zip(infos, pos, strict=True):
            key = f"g{weight}-{info.codepoint}"
            if key not in self.defs:
                pen = SVGPathPen(glyphs, ntos=lambda v: f"{round(v)}")
                glyphs[order[info.codepoint]].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
                d = pen.getCommands()
                self.defs[key] = f'<path id="{key}" d="{d}"/>' if d else ""
            if self.defs[key]:
                gx, gy = cx + p.x_offset * k, y - p.y_offset * k
                uses.append(f'<use xlink:href="#{key}" transform="translate({gx:.1f} {gy:.1f}) scale({k:.4f})"/>')
            cx += p.x_advance * k + tracking
        return f'<g fill="{fill}">' + "".join(uses) + "</g>"

    def defs_block(self):
        return "<defs>" + "".join(v for v in self.defs.values() if v) + "</defs>"


def logo(x, y, size, P):
    """The sbbench mark: a sealed cube with the process counter still climbing on its side."""
    k = size / 32
    return (
        f'<g transform="translate({x} {y}) scale({k:.4f})">'
        f'<path d="M16 2 28.5 9 16 16 3.5 9Z" fill="{P["cube_t"]}"/>'
        f'<path d="M3.5 9 16 16v14L3.5 23Z" fill="{P["cube_l"]}"/>'
        f'<path d="M16 16 28.5 9v14L16 30Z" fill="{P["cube_r"]}"/>'
        '<path d="M17.5 26.4 20.6 24.6V20.7L23.8 18.9V15L27 13.2" fill="none" stroke="#ffffff" '
        'stroke-width="1.9" stroke-linejoin="round" stroke-linecap="round"/></g>'
    )


def stairs(x, y, x_end, dx, dy):
    """A counter going up one step at a time: points from (x, y) until x_end."""
    pts = [f"{x:.1f},{y:.1f}"]
    while x < x_end - 0.1:
        x2 = min(x + dx, x_end)
        pts.append(f"{x2:.1f},{y:.1f}")
        x = x2
        if x < x_end - 0.1:
            y -= dy
            pts.append(f"{x:.1f},{y:.1f}")
    return pts, y


def line(pts, color, width=3.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round"{d}/>'
    )


def rect(x, y, w, h, fill, stroke=None, rx=12, sw=1.5):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}/>'


def mark(cx, cy, P, ok=True, r=11):
    """A filled circle with a check (ok) or a cross."""
    c = P["alive"] if ok else P["fail"]
    s = r / 11
    if ok:
        m = f"M{cx - 5 * s:.1f},{cy:.1f} l{4 * s:.1f},{4 * s:.1f} l{7 * s:.1f},{-8 * s:.1f}"
    else:
        m = f"M{cx - 4 * s:.1f},{cy - 4 * s:.1f} l{8 * s:.1f},{8 * s:.1f} M{cx + 4 * s:.1f},{cy - 4 * s:.1f} l{-8 * s:.1f},{8 * s:.1f}"
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'
        f'<path d="{m}" fill="none" stroke="{P["panel"]}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def arrow(x1, y, x2, color):
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2 - 9}" y2="{y}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        f'<path d="M{x2 - 12},{y - 7} L{x2},{y} L{x2 - 12},{y + 7} Z" fill="{color}"/>'
    )


# ---------------------------------------------------------------- 1. hero
def hero(P):
    W, H = 1280, 420
    G = Type()
    b = [rect(0.75, 0.75, W - 1.5, H - 1.5, P["bg"], P["rule"], 20)]

    b.append(logo(60, 50, 112, P))
    b.append(G.text("sandbox-bench", 196, 140, 88, P["ink"], 800, tracking=-1.8))
    b.append(G.text("Does your sandbox keep your agent's process running", 64, 222, 30, P["muted"]))
    b.append(G.text("when you pause, snapshot or fork it?", 64, 262, 30, P["muted"]))

    # One process counter, climbing through a pause, a snapshot and a fork.
    base, dx, dy, x0 = 388, 22, 3.0, 64
    pts, y = stairs(x0, base, 360, dx, dy)
    out = [line(pts, P["alive"])]
    labels = []
    for a, z, name in ((360, 440, "pause"), (660, 740, "snapshot")):
        out.append(line([f"{a},{y:.1f}", f"{z},{y:.1f}"], P["alive"], 3, "1 7"))
        labels.append(((a + z) / 2, y - 22, name))
        nxt = 660 if name == "pause" else 960
        pts, y = stairs(z, y, nxt, dx, dy)
        out.append(line(pts, P["alive"]))
    fork_x, fy = 960, y
    labels.append((fork_x, fy - 22, "fork"))
    pts, yp = stairs(fork_x, fy, 1200, dx, dy)
    out.append(line(pts, P["alive"]))
    off = 40
    out.append(
        f'<path d="M{fork_x},{fy:.1f} C{fork_x + 16},{fy:.1f} {fork_x + 12},{fy + off:.1f} {fork_x + 30},{fy + off:.1f}" '
        f'fill="none" stroke="{P["alive"]}" stroke-width="3.5" stroke-linecap="round"/>'
    )
    pts, yc = stairs(fork_x + 30, fy + off, 1200, dx, dy)
    out.append(line(pts, P["alive"]))
    for cy in (yp, yc):
        out.append(f'<circle cx="1200" cy="{cy:.1f}" r="6" fill="{P["alive"]}"/>')
    out.append(f'<circle cx="{x0}" cy="{base}" r="5" fill="{P["alive"]}"/>')
    for x, y, name in labels:
        out.append(G.text(name, x, y, 21, P["act"], 500, "middle"))
    b += out

    body = G.defs_block() + "\n" + "\n".join(b)
    return svg(
        W, H, body, "sandbox-bench",
        "The sandbox-bench logo, a cube with a rising counter on its side, next to the name. "
        "Does your sandbox keep your agent's process running when you pause, snapshot or fork it? "
        "A process counter keeps climbing through a pause and a snapshot, then forks into two copies "
        "that both keep counting.",
    )


# ---------------------------------------------------------------- 2. memory check
def memory(P):
    W, H = 1200, 420
    G = Type()
    b = []

    # Before
    b.append(rect(0, 20, 330, 380, P["panel"], P["rule"]))
    b.append(G.text("Before", 32, 72, 28, P["ink"], 700))
    rows = (
        ("Start a counter", "a shell loop, +1 every 0.5 s"),
        ("Fill RAM", "32 MiB of random bytes"),
        ("Write down", "PID, RAM hash and count"),
    )
    for i, (head, sub) in enumerate(rows):
        y = 140 + i * 88
        b.append(f'<circle cx="40" cy="{y - 8}" r="5" fill="{P["alive"]}"/>')
        b.append(G.text(head, 58, y, 23, P["ink"], 600))
        b.append(G.text(sub, 58, y + 32, 19, P["muted"]))

    # The action
    for i, s in enumerate(("pause,", "snapshot", "or fork")):
        b.append(G.text(s, 396, 162 + i * 24, 20, P["act"], 500, "middle"))
    b.append(arrow(346, 236, 446, P["act"]))

    # After: two possible outcomes
    def outcome(y, ok):
        color = P["alive"] if ok else P["fail"]
        out = [rect(462, y, 738, 180, P["panel"], color, 12, 2)]
        cx, base = 494, y + 140
        pts, top = stairs(cx, base, cx + 112, 16, 6)
        out.append(line(pts, P["alive"], 3))
        out.append(f'<rect x="{cx + 118}" y="{y + 34}" width="56" height="{base - y - 22}" rx="4" fill="{P["actfill"]}"/>')
        if ok:
            out.append(line([f"{cx + 112},{top}", f"{cx + 180},{top}"], P["alive"], 3, "1 6"))
            pts, _ = stairs(cx + 180, top, cx + 270, 16, 6)
            out.append(line(pts, P["alive"], 3))
        else:
            out.append(line([f"{cx + 180},{top}", f"{cx + 270},{top}"], P["fail"], 3, "7 6"))
        tx = 820
        title = "Process kept: pass" if ok else "Sandbox restarted: fail"
        out.append(G.text(title, tx, y + 48, 25, color, 700))
        checks = ("same process", "same RAM contents", "still counting") if ok else (
            "a new process", "RAM is empty", "the count is stuck")
        for i, c in enumerate(checks):
            cy = y + 84 + i * 32
            out.append(mark(tx + 10, cy - 7, P, ok, 10))
            out.append(G.text(c, tx + 32, cy, 20, P["ink"]))
        return out

    b += outcome(20, True)
    b += outcome(220, False)

    body = G.defs_block() + "\n" + "\n".join(b)
    return svg(
        W, H, body, "The memory check",
        "Before the action, the harness starts a counter that adds 1 every 0.5 s, fills 32 MiB of RAM "
        "with random bytes, and writes down the process ID, the RAM hash and the count. After a pause, "
        "snapshot or fork, it passes only if the same process is running, the RAM is unchanged and the "
        "count is still rising. A restarted sandbox fails: a new process, empty RAM, a stuck count.",
    )


# ---------------------------------------------------------------- 3. how a run works
def run(P):
    W, H = 1200, 220
    G = Type()
    b = []
    steps = (
        ("Start", "A maintainer starts", "the Benchmark run"),
        ("Measure", "10 attempts of every", "probe, per provider"),
        ("Record", "Raw results go to", "the results repo"),
        ("Score", "sbx report builds", "the leaderboard"),
    )
    w, gap = 252, 64
    for i, (head, l1, l2) in enumerate(steps):
        x = i * (w + gap)
        b.append(rect(x, 20, w, 180, P["panel"], P["rule"]))
        b.append(f'<circle cx="{x + 42}" cy="{66}" r="18" fill="{P["alive"]}"/>')
        b.append(G.text(str(i + 1), x + 42, 74, 22, P["panel"], 700, "middle"))
        b.append(G.text(head, x + 74, 75, 27, P["ink"], 700))
        b.append(G.text(l1, x + 24, 136, 20, P["muted"]))
        b.append(G.text(l2, x + 24, 166, 20, P["muted"]))
        if i < len(steps) - 1:
            b.append(arrow(x + w + 12, 110, x + w + gap - 12, P["faint"]))

    body = G.defs_block() + "\n" + "\n".join(b)
    return svg(
        W, H, body, "How a run works",
        "1, Start: a maintainer starts the Benchmark run workflow. 2, Measure: 10 attempts of every "
        "probe on each provider. 3, Record: the raw results go to the results repo. 4, Score: sbx "
        "report builds the leaderboard.",
    )


def T(x, y, s, P, size=20, fill="ink", weight=400, anchor="start", font=SANS, extra=""):
    color = P.get(fill, fill)
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}"{extra}>{escape(s)}</text>'
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


LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>.t{fill:#4cc297}.l{fill:#0a7a5c}'
    ".r{fill:#075a44}@media (prefers-color-scheme:dark){.t{fill:#a6efd2}.l{fill:#43d19e}.r{fill:#24966f}}"
    '</style><path class="t" d="M16 2 28.5 9 16 16 3.5 9Z"/><path class="l" d="M3.5 9 16 16v14L3.5 23Z"/>'
    '<path class="r" d="M16 16 28.5 9v14L16 30Z"/><path d="M17.5 26.4 20.6 24.6V20.7L23.8 18.9V15L27 13.2" '
    'fill="none" stroke="#fff" stroke-width="1.9" stroke-linejoin="round" stroke-linecap="round"/></svg>\n'
)

if __name__ == "__main__":
    (OUT / "logo.svg").write_text(LOGO)
    for nm, P in (("light", LIGHT), ("dark", DARK)):
        (OUT / f"hero-{nm}.svg").write_text(hero(P))
        (OUT / f"memory-check-{nm}.svg").write_text(memory(P))
        (OUT / f"how-a-run-works-{nm}.svg").write_text(run(P))
    cap = Path(sys.argv[2]).read_text().rstrip("\n").split("\n") if len(sys.argv) > 2 else []
    if cap:
        (OUT / "sbx-check-freestyle.svg").write_text(terminal(cap))
