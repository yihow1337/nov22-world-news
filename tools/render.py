#!/usr/bin/env python3
"""Render entry.png -- an illustrated front page for Sunday 22 November 2026.

Local tool only (needs Pillow). The program the grader runs (main.py) never
imports this; it only copies the committed entry.png.

    python3 tools/render.py        # writes entry.png + preview_300/512.png

Design rule for this poster: it has to be readable when the whole thing is
scaled to 300 px across, i.e. at 0.293x. So nothing carries meaning below
~19 px, there is no running body copy, and every story is a card with its own
drawn picture, a place kicker and a headline of a few words. The supporting
density (numbers strip, locator map, date-check band) is built from short
lines, not paragraphs.

Mechanics worth knowing before editing:
  * Display type (Anton) is set by BASELINE via caps(), so vertical rhythm is
    exact and letter-tracking is explicit.
  * Text copy (Source Sans 3 variable) is drawn word by word with a generous
    explicit word gap -- the font's own spacing collapses into mid-word breaks
    once the poster is downsampled.
  * draw_block(max_lines=...) is a layout assertion: copy that outgrows its
    box raises instead of quietly overlapping.
  * The locator map is a plain equirectangular projection with the SAME
    degrees-per-pixel on both axes, so the continents are not squashed.
"""

import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W = H = 1024
SS = 4  # supersample factor for drawn pictures

GOOGLE = "/usr/share/fonts/truetype/sand-box/google"
ANTON = os.path.join(GOOGLE, "Anton", "Anton-Regular.ttf")
SANS = os.path.join(GOOGLE, "Source Sans 3", "SourceSans3-VariableFont_wght.ttf")

PAPER = (245, 242, 235)
INK = (21, 23, 26)
INK_SOFT = (70, 73, 79)
RED = (178, 33, 28)
SLATE = (38, 64, 90)
GREEN = (36, 92, 70)
CREAM = (252, 250, 246)
TINT = (231, 227, 217)
SEA = (228, 224, 214)

MARGIN = 40
COL = W - 2 * MARGIN  # 944 px of content

_cache = {}


def anton(size):
    key = ("anton", size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(ANTON, size)
    return _cache[key]


def sans(size, weight=400):
    key = ("sans", size, weight)
    if key not in _cache:
        f = ImageFont.truetype(SANS, size)
        f.set_variation_by_axes([weight])
        _cache[key] = f
    return _cache[key]


# --- type helpers -----------------------------------------------------------

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def tokens(text):
    """-> [(word, is_bold)] honouring **emphasis**.

    A chunk that does not start on whitespace is glued to the word before it,
    so "**29**," keeps its comma instead of spacing it off.
    """
    out = []

    def push(chunk, bold, glue):
        words = chunk.split()
        if not words:
            return
        if glue and out:
            prev_word, prev_bold = out[-1]
            out[-1] = (prev_word + words[0], prev_bold)
            words = words[1:]
        for w in words:
            out.append((w, bold))

    pos = 0
    for m in BOLD_RE.finditer(text):
        plain = text[pos:m.start()]
        push(plain, False, bool(plain) and not plain[:1].isspace())
        push(m.group(1), True,
             m.start() > 0 and not text[m.start() - 1].isspace())
        pos = m.end()
    rest = text[pos:]
    push(rest, False, bool(rest) and not rest[:1].isspace())
    return out


def layout(text, max_w, size, weight=400, bold_weight=700, gap=None):
    reg, bld = sans(size, weight), sans(size, bold_weight)
    if gap is None:
        gap = round(size * 0.32)
    lines, cur, cur_w = [], [], 0.0
    for word, is_bold in tokens(text):
        f = bld if is_bold else reg
        ww = f.getlength(word)
        add = ww if not cur else gap + ww
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [(word, f, ww)], ww
        else:
            cur.append((word, f, ww))
            cur_w += add
    if cur:
        lines.append(cur)
    return lines, gap


def balance(text, lines, gap, max_w, size, weight, bold_weight):
    """Re-wrap into the narrowest column that still holds the same number of
    lines, so a two-line headline does not end on a single orphan word."""
    n = len(lines)
    if n < 2:
        return lines
    lo, hi, best = int(max_w * 0.5), int(max_w), lines
    while lo < hi:
        mid = (lo + hi) // 2
        trial, _ = layout(text, mid, size, weight, bold_weight, gap)
        if len(trial) <= n:
            best, hi = trial, mid
        else:
            lo = mid + 1
    return best


def draw_block(d, x, y, text, max_w, size, fill, weight=400, bold_weight=700,
               leading=None, gap=None, max_lines=None, tag="", even=False):
    """Draw wrapped copy from a top-left corner. Returns the y below it."""
    lines, gap = layout(text, max_w, size, weight, bold_weight, gap)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError("%s: %d lines (max %d) for %r"
                         % (tag or "block", len(lines), max_lines, text[:52]))
    if even:
        lines = balance(text, lines, gap, max_w, size, weight, bold_weight)
    if leading is None:
        leading = round(size * 1.28)
    cy = y
    for line in lines:
        cx = x
        for word, font, ww in line:
            d.text((cx, cy), word, font=font, fill=fill)
            cx += ww + gap
        cy += leading
    return cy


def caps(d, x, baseline, text, font, fill, track=0.0):
    """Letter-spaced caps on a baseline, glyph by glyph. Returns the end x."""
    cx = x
    for ch in text:
        d.text((cx, baseline), ch, font=font, fill=fill, anchor="ls")
        cx += font.getlength(ch) + track
    return cx


def caps_w(text, font, track=0.0):
    if not text:
        return 0.0
    return sum(font.getlength(c) + track for c in text) - track


def ink_top(font, text):
    """Height of inked caps above the baseline, measured not guessed."""
    _, y0, _, _ = font.getbbox(text, anchor="ls")
    return -y0


def fit_anton(text, target_w, max_size, track=0.0, min_size=10):
    """Largest Anton size (<= max_size) whose tracked text fits target_w."""
    size = max_size
    while size > min_size and caps_w(text, anton(size), track) > target_w:
        size -= 1
    return size


def fit_caps(d, x, baseline, text, max_w, max_size, fill, track=1.2):
    size = fit_anton(text, max_w, max_size, track)
    caps(d, x, baseline, text, anton(size), fill, track=track)
    return size


# --- drawn pictures ---------------------------------------------------------
# Each is painted on a supersampled RGBA tile and scaled down, so diagonals
# and curves arrive antialiased. Shapes are deliberately chunky: at 300 px a
# card picture is about 44x16 px and only silhouettes survive.

def tile(w, h):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def shrink(t):
    return t.resize((t.width // SS, t.height // SS), Image.LANCZOS)


def place(base, t, x, y):
    base.alpha_composite(shrink(t), (int(x), int(y)))


def pic_block(w, h, accent):
    """Dymer: a long five-storey slab with its centre bay sheared away, and a
    delta-winged drone coming in above it."""
    img, d = tile(w, h)
    s = SS
    ground = (h - 4) * s
    top = int(h * 0.38) * s
    left, right = 6 * s, (w - 6) * s
    d.rectangle([left, top, right, ground], fill=INK)
    rows, cols = 5, 9
    fh = (ground - top) / rows
    cw = (right - left) / cols
    for r in range(rows):
        for c in range(cols):
            wx = left + c * cw + cw * 0.26
            wy = top + r * fh + fh * 0.24
            d.rectangle([wx, wy, wx + cw * 0.46, wy + fh * 0.46], fill=PAPER)
    # the sheared bay: a wedge of missing floors, rubble heaped at its foot
    bx0, bx1 = left + cw * 3.1, left + cw * 5.0
    d.polygon([(bx0, top - 2 * s), (bx1, top - 2 * s), (bx1, ground),
               (bx0, ground)], fill=PAPER)
    d.polygon([(bx0, ground), (bx0, top + fh * 1.1), (bx1, ground)],
              fill=INK_SOFT)
    d.polygon([(bx1, ground), (bx1, top + fh * 2.4), (bx0 + cw * 0.6, ground)],
              fill=INK_SOFT)
    # drone
    dx, dy = int(w * 0.70) * s, int(h * 0.16) * s
    d.polygon([(dx + 17 * s, dy), (dx - 15 * s, dy + 7 * s),
               (dx - 9 * s, dy - 1 * s), (dx - 15 * s, dy - 6 * s)],
              fill=accent)
    d.rectangle([left - 6 * s, ground, right + 6 * s, ground + 3 * s], fill=INK)
    return img


def pic_ship(w, h, accent):
    """Benghazi: a freighter at a quay, flash bursting over its deck."""
    img, d = tile(w, h)
    s = SS
    water = (h - 9) * s
    deck = water - 11 * s
    d.polygon([(10 * s, deck), ((w - 7) * s, deck),
               ((w - 16) * s, water), (19 * s, water)], fill=INK)
    d.rectangle([int(w * 0.22) * s, deck - 13 * s,
                 int(w * 0.40) * s, deck], fill=INK)
    d.rectangle([int(w * 0.27) * s, deck - 20 * s,
                 int(w * 0.33) * s, deck - 13 * s], fill=INK)
    for cx in (0.50, 0.62, 0.74):
        d.rectangle([int(w * cx) * s, deck - 8 * s,
                     int(w * (cx + 0.09)) * s, deck], fill=INK_SOFT)
    bx, by = int(w * 0.63) * s, deck - 20 * s
    pts = []
    for i in range(14):
        a = math.pi * 2 * i / 14 - math.pi / 2
        r = (19 if i % 2 == 0 else 8) * s
        pts.append((bx + math.cos(a) * r, by + math.sin(a) * r * 0.9))
    d.polygon(pts, fill=RED)  # a blast reads red whatever the card accent
    for i in range(2):
        yy = water + (3 + i * 4) * s
        d.line([(4 * s, yy), ((w - 4) * s, yy)], fill=INK_SOFT, width=2 * s)
    return img


def pic_ballot(w, h, accent):
    """Hong Kong: a ticked ballot dropping into the box, and a turnout bar
    stopped a hair short of full."""
    img, d = tile(w, h)
    s = SS
    base = (h - 4) * s
    bx0, bx1 = 10 * s, int(w * 0.40) * s
    top = int(h * 0.52) * s
    d.polygon([(bx0, top), (bx1, top), (bx1 - 4 * s, base),
               (bx0 + 4 * s, base)], fill=INK)
    d.rectangle([bx0 + 6 * s, top - 3 * s, bx1 - 6 * s, top + 3 * s],
                fill=PAPER)
    pap = (bx0 + bx1) // 2
    pw2 = 13 * s
    d.rectangle([pap - pw2, top - 34 * s, pap + pw2, top - 5 * s],
                fill=CREAM, outline=INK, width=3 * s)
    d.line([(pap - 6 * s, top - 20 * s), (pap - 1 * s, top - 13 * s),
            (pap + 7 * s, top - 28 * s)], fill=RED, width=4 * s, joint="curve")
    gx0, gx1 = int(w * 0.48) * s, (w - 8) * s
    gy0, gy1 = int(h * 0.36) * s, int(h * 0.62) * s
    d.rectangle([gx0, gy0, gx1, gy1], fill=PAPER, outline=INK, width=2 * s)
    d.rectangle([gx0 + 2 * s, gy0 + 2 * s,
                 gx0 + 2 * s + (gx1 - gx0 - 4 * s) * 0.9879, gy1 - 2 * s],
                fill=accent)
    d.rectangle([gx0, base - 7 * s, gx1, base - 4 * s], fill=INK_SOFT)
    return img


def pic_car(w, h, accent):
    """Las Vegas: a formula car in profile taking a chequered flag."""
    img, d = tile(w, h)
    s = SS
    base = (h - 5) * s
    axle = base - 9 * s
    # chequered flag on the right
    cell = int(h * 0.17) * s
    fx0, fy0 = int(w * 0.72) * s, 3 * s
    for r in range(3):
        for c in range(4):
            col = INK if (r + c) % 2 == 0 else CREAM
            d.rectangle([fx0 + c * cell, fy0 + r * cell,
                         fx0 + (c + 1) * cell, fy0 + (r + 1) * cell], fill=col)
    d.rectangle([fx0 - 3 * s, fy0, fx0, axle], fill=INK_SOFT)
    # body: nose, cockpit hump, engine cover
    d.polygon([(4 * s, axle), (4 * s, axle - 7 * s),
               (int(w * 0.30) * s, axle - 9 * s),
               (int(w * 0.38) * s, axle - 19 * s),
               (int(w * 0.52) * s, axle - 19 * s),
               (int(w * 0.58) * s, axle - 9 * s),
               (int(w * 0.70) * s, axle - 8 * s),
               (int(w * 0.70) * s, axle)], fill=INK)
    d.polygon([(2 * s, axle - 4 * s), (int(w * 0.14) * s, axle - 12 * s),
               (int(w * 0.14) * s, axle - 6 * s), (2 * s, axle)], fill=accent)
    d.rectangle([int(w * 0.60) * s, axle - 30 * s,
                 int(w * 0.72) * s, axle - 24 * s], fill=accent)
    d.rectangle([int(w * 0.64) * s, axle - 28 * s,
                 int(w * 0.68) * s, axle - 9 * s], fill=INK)
    for cx in (0.22, 0.62):
        px, r = int(w * cx) * s, 10 * s
        d.ellipse([px - r, axle - r, px + r, axle + r], fill=INK)
        d.ellipse([px - 3 * s, axle - 3 * s, px + 3 * s, axle + 3 * s],
                  fill=PAPER)
    d.rectangle([0, base, w * s, base + 3 * s], fill=INK)
    return img


def pic_march(w, h, accent):
    """Europe: a column of marchers, two placards up, third day running."""
    img, d = tile(w, h)
    s = SS
    ground = (h - 4) * s
    n = 9
    step = w / (n + 0.5)
    for i in range(n):
        hx = (step * (i + 0.6)) * s
        r = 4.6 * s
        hy = ground - 21 * s
        d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=INK)
        d.polygon([(hx - 7 * s, ground), (hx - 6 * s, hy + 4 * s),
                   (hx + 6 * s, hy + 4 * s), (hx + 7 * s, ground)], fill=INK)
    pw = step * 2.4
    for frac, col in ((0.09, accent), (0.52, INK)):
        px = w * frac * s
        stem = px + pw * s / 2
        d.rectangle([stem - 2 * s, 18 * s, stem + 2 * s, ground - 15 * s],
                    fill=INK_SOFT)
        d.rectangle([px, 2 * s, px + pw * s, 19 * s], fill=col)
        for ln in range(2):
            d.rectangle([px + 5 * s, (6 + ln * 6) * s,
                         px + pw * s - 5 * s, (9 + ln * 6) * s], fill=CREAM)
    d.rectangle([0, ground, w * s, ground + 3 * s], fill=INK)
    return img


def pic_factory(w, h, accent):
    """Cikande: a burnt-out saw-tooth shed, roof gone, smoke still rising."""
    img, d = tile(w, h)
    s = SS
    base = (h - 4) * s
    top = int(h * 0.46) * s
    x0, x1 = 5 * s, int(w * 0.74) * s
    d.rectangle([x0, top, x1, base], fill=INK)
    step = (x1 - x0) / 4
    for i in range(4):
        sx = x0 + i * step
        d.polygon([(sx, top), (sx + step, top), (sx + step, top - 10 * s)],
                  fill=INK)
    # collapsed section on the right of the shed
    d.polygon([(x1 - step * 1.1, top - 9 * s), (x1, top - 9 * s), (x1, base),
               (x1 - step * 1.1, base)], fill=PAPER)
    d.polygon([(x1 - step * 1.1, base), (x1, base - step * 0.5), (x1, base)],
              fill=INK_SOFT)
    stack = (w - 17) * s
    d.rectangle([stack, int(h * 0.30) * s, stack + 9 * s, base], fill=INK)
    for i, (ox, r) in enumerate(((0, 6), (7, 8), (16, 5.5))):
        cx = stack + (4 + ox) * s
        cy = int(h * 0.22) * s - i * 7 * s
        d.ellipse([cx - r * s, cy - r * s, cx + r * s, cy + r * s],
                  fill=INK_SOFT if i else accent)
    for fx, fw in ((0.16, 0.10), (0.34, 0.08), (0.50, 0.11)):
        d.rectangle([int(w * fx) * s, base - 13 * s,
                     int(w * (fx + fw)) * s, base], fill=PAPER)
    d.rectangle([0, base, w * s, base + 3 * s], fill=INK)
    return img


def stamp(w, h, line1, line2, angle=-5):
    """The lead's picture: a rubber stamp reading NO TEXT / ADOPTED."""
    pad = 26
    img, d = tile(w + pad * 2, h + pad * 2)
    s = SS
    x0, y0 = pad * s, pad * s
    x1, y1 = (pad + w) * s, (pad + h) * s
    d.rectangle([x0, y0, x1, y1], outline=RED, width=5 * s)
    d.rectangle([x0 + 9 * s, y0 + 9 * s, x1 - 9 * s, y1 - 9 * s],
                outline=RED, width=2 * s)
    # size the type from the box, not the other way round: two cap-height
    # lines plus the gap between them have to sit inside the inner rule
    f1 = anton(int(h * 0.30) * s)
    inner = (h - 26) * s
    cap = ink_top(f1, line1)
    while 2 * cap + cap * 0.4 > inner and f1.size > 8 * s:
        f1 = anton(f1.size - 2 * s)
        cap = ink_top(f1, line1)
    f2 = f1
    t1 = caps_w(line1, f1, 3 * s)
    t2 = caps_w(line2, f2, 3 * s)
    cx = (x0 + x1) / 2
    gap = cap * 0.4
    b1 = y0 + (h * s - 2 * cap - gap) / 2 + cap
    b2 = b1 + cap + gap
    caps(d, cx - t1 / 2, b1, line1, f1, RED, track=3 * s)
    caps(d, cx - t2 / 2, b2, line2, f2, RED, track=3 * s)
    # rotate while still supersampled; place() does the downsampling
    return img.rotate(angle, Image.BICUBIC, expand=False)


# --- locator map ------------------------------------------------------------
# Hand-simplified coastlines, (lon, lat), drawn as filled polygons. Coarse on
# purpose: at 300 px the map is 180 px wide and only the big shapes read.

COASTS = [
    # North America incl. Central America and Alaska
    [(-168, 65), (-162, 68), (-152, 71), (-140, 70), (-128, 70), (-115, 69),
     (-105, 68), (-95, 69), (-86, 70), (-80, 73), (-72, 68), (-64, 61),
     (-56, 53), (-62, 47), (-67, 45), (-70, 43), (-74, 40), (-76, 36),
     (-81, 31), (-80, 25), (-84, 30), (-89, 30), (-94, 29), (-97, 26),
     (-97, 21), (-91, 19), (-87, 21), (-88, 16), (-84, 10), (-78, 9),
     (-83, 8), (-87, 13), (-95, 16), (-105, 20), (-110, 23), (-114, 28),
     (-117, 32), (-121, 35), (-124, 41), (-124, 48), (-131, 54), (-138, 59),
     (-148, 60), (-154, 57), (-163, 55), (-166, 60)],
    # Greenland
    [(-45, 60), (-36, 65), (-24, 70), (-19, 75), (-28, 80), (-40, 83),
     (-52, 82), (-58, 76), (-54, 69), (-49, 63)],
    # South America
    [(-78, 8), (-71, 11), (-62, 10), (-52, 5), (-50, 0), (-44, -2),
     (-35, -5), (-38, -13), (-39, -18), (-48, -25), (-54, -34), (-58, -39),
     (-63, -42), (-68, -50), (-70, -55), (-74, -50), (-73, -42), (-71, -30),
     (-70, -23), (-76, -14), (-81, -6), (-80, -2), (-78, 1), (-77, 4)],
    # Africa (its east coast sits a few degrees west of Arabia's, so the
    # Red Sea survives as a gap instead of welding the two together)
    [(-17, 15), (-16, 21), (-11, 27), (-8, 32), (-6, 36), (3, 37), (10, 37),
     (16, 32), (21, 32), (26, 32), (32, 31), (33, 27), (37, 20), (41, 11),
     (45, 11), (48, 11), (46, 5), (42, -1), (40, -10), (35, -19), (32, -26),
     (28, -33), (20, -35), (16, -29), (12, -18), (9, -4), (6, 4), (0, 5),
     (-6, 4), (-11, 7), (-15, 12)],
    # Eurasia: one ring -- Atlantic coast, the Arctic, the Pacific, the
    # Indian Ocean rim, the Red Sea, then back west along the Mediterranean.
    [(-6, 36), (-9, 38), (-9, 43), (-2, 43), (-1, 46), (-4, 48), (-1, 50),
     (2, 51), (4, 53), (8, 54), (8, 57), (11, 58), (10, 59), (5, 60),
     (7, 63), (12, 65), (18, 70), (28, 70), (40, 67), (55, 68), (68, 73),
     (78, 72), (90, 76), (105, 77), (115, 73), (130, 72), (142, 72),
     (158, 70), (170, 66), (180, 65), (178, 62), (165, 60), (158, 57),
     (153, 52), (143, 46), (140, 43), (130, 43), (125, 38), (122, 30),
     (118, 24), (110, 21), (105, 10), (103, 1), (98, 8), (93, 16), (88, 22),
     (84, 18), (80, 13), (77, 8), (73, 16), (70, 21), (65, 24), (61, 25),
     (57, 25),
     (52, 17), (45, 13), (43, 13), (39, 21), (35, 28), (34, 31), (36, 36),
     (30, 36), (26, 38), (23, 38), (20, 40), (16, 38), (15, 40), (12, 45),
     (8, 44), (3, 43), (0, 41), (-3, 37)],
    # British Isles / Ireland
    [(-5, 50), (-6, 53), (-5, 58), (-2, 58), (0, 54), (1, 51)],
    [(-10, 52), (-10, 55), (-6, 55), (-6, 52)],
    # Japan
    [(130, 32), (136, 35), (141, 40), (143, 44), (145, 44), (141, 38),
     (137, 35), (133, 33)],
    # Indonesia / Philippines / Madagascar / Sri Lanka
    [(95, 5), (103, -6), (112, -8), (120, -9), (130, -8), (141, -9),
     (141, -3), (131, -1), (120, 0), (112, -2), (100, 2)],
    [(120, 18), (124, 17), (126, 10), (122, 6), (119, 10), (120, 14)],
    [(44, -12), (50, -15), (48, -25), (44, -22), (43, -16)],
    [(80, 6), (82, 8), (81, 10), (79, 8)],
    # Australia / New Zealand
    [(114, -22), (113, -26), (115, -34), (121, -34), (129, -32), (135, -35),
     (141, -38), (146, -39), (150, -37), (153, -28), (146, -19), (142, -11),
     (136, -12), (130, -11), (125, -14), (120, -20)],
    [(173, -35), (178, -38), (175, -42), (168, -46), (166, -45), (172, -40)],
]

# Inland seas, painted back over the land: without them Hudson Bay, the Black
# Sea and the Caspian vanish and the continents lose their silhouettes.
SEAS = [
    [(-95, 51), (-78, 52), (-77, 62), (-88, 64), (-95, 59)],
    [(28, 41), (41, 42), (41, 46), (31, 46), (28, 44)],
    [(47, 37), (54, 41), (53, 47), (48, 46), (46, 41)],
]

PINS = [
    (1, 30.7, 36.9),    # Antalya
    (2, 30.3, 50.8),    # Dymer, north of Kyiv
    (3, 20.1, 32.1),    # Benghazi
    (4, 114.2, 22.3),   # Hong Kong
    (5, -115.1, 36.2),  # Las Vegas
    (6, -9.1, 38.7),    # Lisbon
    (6, 2.3, 48.9),     # Paris
    (7, 106.3, -6.2),   # Cikande
]

LON0, LON1 = -130.0, 128.0
LAT0, LAT1 = -16.0, 59.4


def draw_map(base, d, x, y, w, h):
    """Equirectangular, identical scale on both axes, clipped to the box."""
    img, md = tile(w, h)
    s = SS
    md.rectangle([0, 0, w * s, h * s], fill=SEA)
    k = (w * s) / (LON1 - LON0)            # px per degree, both axes
    oy = (h * s - k * (LAT1 - LAT0)) / 2   # centre the band vertically

    def px(lon, lat):
        return (lon - LON0) * k, h * s - oy - (lat - LAT0) * k

    for lon in range(-120, 181, 30):
        gx = px(lon, 0)[0]
        md.line([(gx, 0), (gx, h * s)], fill=(214, 210, 200), width=s)
    for lat in range(-30, 90, 30):
        gy = px(0, lat)[1]
        md.line([(0, gy), (w * s, gy)], fill=(214, 210, 200), width=s)
    for poly in COASTS:
        md.polygon([px(a, b) for a, b in poly], fill=(156, 152, 142))
    for poly in SEAS:
        md.polygon([px(a, b) for a, b in poly], fill=SEA)
    base.alpha_composite(shrink(img), (x, y))
    d.rectangle([x, y, x + w, y + h], outline=INK, width=2)

    k2 = w / (LON1 - LON0)
    oy2 = (h - k2 * (LAT1 - LAT0)) / 2
    pf = anton(14)
    for num, lon, lat in PINS:
        cx = x + (lon - LON0) * k2
        cy = y + h - oy2 - (lat - LAT0) * k2
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=RED,
                  outline=CREAM, width=2)
        t = str(num)
        caps(d, cx - caps_w(t, pf) / 2, cy + ink_top(pf, t) / 2, t, pf, CREAM)


# --- content ----------------------------------------------------------------

DATE = "SUNDAY 22 NOVEMBER 2026"
STRAP = "SEVEN STORIES · FOUR CONTINENTS · ONE DAY"

LEAD_KICKER = "1 · LEAD · COP31 UN CLIMATE SUMMIT · ANTALYA, TÜRKIYE"
LEAD_H1 = "COP31 ENDS WITH NO"
LEAD_H2 = "DEAL ON FOSSIL FUELS"
LEAD_DEK = ("The longest COP on record broke up with **no text adopted**: "
            "the EU and island states refused a draft that never named "
            "fossil fuels. Guterres: “deeply disappointing”.")

NUMBERS = [
    ("186", "DRONES AT UKRAINE"),
    ("161", "SHOT DOWN"),
    ("0", "COP31 TEXTS ADOPTED"),
    ("24", "BODY BAGS, CIKANDE"),
    ("98.79%", "HONG KONG TURNOUT"),
]

CARDS = [
    {
        "n": 2,
        "kicker": "UKRAINE · DYMER, NORTH OF KYIV",
        "head": "Russian drone destroys a five-storey block",
        "note": "2 killed · 11 unaccounted for",
        "tag": None,
        "pic": pic_block,
        "accent": RED,
    },
    {
        "n": 3,
        "kicker": "LIBYA · BENGHAZI NAVAL BASE",
        "head": "Blast hits a ship in port",
        "note": "Russian ship, drone suspected",
        "tag": "CLAIM",
        "pic": pic_ship,
        "accent": SLATE,
    },
    {
        "n": 4,
        "kicker": "HONG KONG · ELECTION COMMITTEE",
        "head": "98.79% vote in subsector polls",
        "note": "5,640 of 5,709 electors",
        "tag": "CONFIRMED",
        "pic": pic_ballot,
        "accent": SLATE,
    },
    {
        "n": 5,
        "kicker": "LAS VEGAS · FORMULA ONE",
        "head": "Verstappen wins from pole",
        "note": "+0.639s over Norris",
        "tag": None,
        "pic": pic_car,
        "accent": GREEN,
    },
    {
        "n": 6,
        "kicker": "EUROPE · PORTUGAL TO FRANCE",
        "head": "Cost-of-living marches, day three",
        "note": "France: sixth weekend running",
        "tag": None,
        "pic": pic_march,
        "accent": SLATE,
    },
    {
        "n": 7,
        "kicker": "INDONESIA · CIKANDE, BANTEN",
        "head": "24 body bags from the candy plant",
        "note": "Saturday's fire · toll not final",
        "tag": "UPDATE",
        "pic": pic_factory,
        "accent": RED,
    },
]

UPDATES_TITLE = "SUNDAY UPDATES ON EARLIER EVENTS"
UPDATES = [
    ("SAT 21", "Bahrain denies Iran hit US Patriot radars"),
    ("SAT 21", "Finland: the war is “spilling over” after the Sparta II "
               "strike"),
    ("FRI 20", "Nigeria: the Bayelsa boat toll rises to 29 dead"),
]

CHECK_TITLE = "· THESE BROKE EARLIER IN THE WEEK — NOT SUNDAY'S NEWS"
CHECKS = [
    ("THU 19 NOV", "Shenzhen Trump–Xi–Putin summit · ICJ Myanmar genocide "
                   "ruling · Anthropic's Nasdaq debut"),
    ("FRI 20 NOV", "Russian missiles and a drone came down in Poland · NATO's "
                   "council on it meets Monday 23rd"),
    ("SAT 21 NOV", "Cikande factory fire starts · Sparta II struck in the "
                   "Baltic · Iran–Bahrain strike claims"),
]

STAMP_TEXT = "22 NOV 2026"


# --- composition ------------------------------------------------------------

MAST_H = 104
LEAD_Y = 110
NUM_Y, NUM_H = 326, 62
CARD_Y, CARD_H, CARD_GAP = 396, 174, 6
BAND_Y, BAND_H = 758, 152
CHECK_Y, CHECK_H = 918, 106


def render():
    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ---------------- masthead ----------------
    d.rectangle([0, 0, W, MAST_H], fill=INK)
    d.rectangle([0, MAST_H - 5, W, MAST_H], fill=RED)
    lab = anton(18)
    caps(d, MARGIN, 27, "ONE IMAGE OF THE WORLD'S NEWS", lab, PAPER, track=2.4)
    caps(d, W - MARGIN - caps_w(STRAP, lab, 2.4), 27, STRAP, lab,
         (168, 164, 156), track=2.4)
    df = anton(fit_anton(DATE, COL, 68, 1.5))
    track = (COL - caps_w(DATE, df)) / (len(DATE) - 1)
    caps(d, MARGIN, 96, DATE, df, CREAM, track=track)

    # ---------------- lead ----------------
    d.rectangle([MARGIN, LEAD_Y + 6, MARGIN + 11, LEAD_Y + 21], fill=RED)
    caps(d, MARGIN + 21, LEAD_Y + 21, LEAD_KICKER, anton(21), RED, track=1.4)

    st_w, st_h = 236, 86
    st_x = W - MARGIN - st_w - 8
    place(img, stamp(st_w, st_h, "NO TEXT", "ADOPTED"), st_x - 26,
          LEAD_Y + 18 - 26)

    head_w = st_x - MARGIN - 30
    hs = min(fit_anton(LEAD_H1, head_w, 58, 1.0),
             fit_anton(LEAD_H2, head_w, 58, 1.0))
    hf = anton(hs)
    b1 = LEAD_Y + 29 + ink_top(hf, LEAD_H1)
    b2 = b1 + int(hs * 0.92)
    caps(d, MARGIN, b1, LEAD_H1, hf, INK, track=1.0)
    caps(d, MARGIN, b2, LEAD_H2, hf, INK, track=1.0)

    dek_y = b2 + 20
    d.rectangle([MARGIN, dek_y - 11, W - MARGIN, dek_y - 9], fill=INK)
    end = draw_block(d, MARGIN, dek_y, LEAD_DEK, COL, 23, INK_SOFT,
                     weight=500, leading=27, max_lines=2, tag="lead-dek")
    if end > NUM_Y - 4:
        raise ValueError("lead dek runs into the numbers strip (%d)" % end)

    # ---------------- key numbers ----------------
    d.rectangle([0, NUM_Y, W, NUM_Y + NUM_H], fill=INK)
    # cells sit inside the page column, so the outer figures line up with the
    # margins the rest of the poster keeps
    cell = COL / len(NUMBERS)
    nf, lf = anton(40), anton(19)
    for i, (figure, label) in enumerate(NUMBERS):
        cx = MARGIN + cell * (i + 0.5)
        if i:
            d.rectangle([MARGIN + cell * i, NUM_Y + 11,
                         MARGIN + cell * i + 2, NUM_Y + NUM_H - 11],
                        fill=(70, 72, 76))
        fw = caps_w(figure, nf, 1.0)
        caps(d, cx - fw / 2, NUM_Y + 40, figure, nf, CREAM, track=1.0)
        s = fit_anton(label, cell - 26, 19, 1.3)
        f = anton(s) if s != 19 else lf
        caps(d, cx - caps_w(label, f, 1.3) / 2, NUM_Y + NUM_H - 6, label, f,
             (182, 178, 170), track=1.3)

    # ---------------- story cards ----------------
    gut = 16
    cw = (COL - gut * 2) / 3
    for i, c in enumerate(CARDS):
        cx = MARGIN + (i % 3) * (cw + gut)
        cy = CARD_Y + (i // 3) * (CARD_H + CARD_GAP)
        d.rectangle([cx, cy, cx + cw, cy + CARD_H], fill=CREAM)
        d.rectangle([cx, cy, cx + cw, cy + 4], fill=c["accent"])

        pic_h, pic_w = 48, int(cw) - 40
        d.rectangle([cx, cy + 4, cx + cw, cy + 10 + pic_h], fill=TINT)
        place(img, c["pic"](pic_w, pic_h, c["accent"]),
              cx + (cw - pic_w) / 2, cy + 8)

        # number badge, keyed to the map pin
        bx, by = cx + 8, cy + 11
        d.ellipse([bx, by, bx + 21, by + 21], fill=c["accent"])
        bf = anton(14)
        t = str(c["n"])
        caps(d, bx + 10.5 - caps_w(t, bf) / 2, by + 10.5 + ink_top(bf, t) / 2,
             t, bf, CREAM)

        # sourcing tag, parked in the picture band so it can never crowd the
        # kicker or the headline
        if c["tag"]:
            tf = anton(14)
            tw = caps_w(c["tag"], tf, 1.4)
            d.rectangle([cx + cw - tw - 20, cy + 8, cx + cw - 6, cy + 27],
                        fill=INK)
            caps(d, cx + cw - tw - 13, cy + 23, c["tag"], tf, CREAM, track=1.4)

        ky = cy + 10 + pic_h + 17
        ks = fit_anton(c["kicker"], cw - 18, 19, 1.1)
        caps(d, cx + 9, ky, c["kicker"], anton(ks), c["accent"], track=1.1)

        # a one-line headline drops half a line, so every card's type sits in
        # the same optical slot between the kicker and the note
        nlines = len(layout(c["head"], cw - 18, 26, 700, 700)[0])
        draw_block(d, cx + 9, ky + 6 + max(0, 2 - nlines) * 14, c["head"],
                   cw - 18, 26, INK, weight=700, leading=28, max_lines=2,
                   tag="card-head %d" % i, even=True)
        note_y = cy + CARD_H - 30
        d.rectangle([cx, note_y - 7, cx + cw, note_y - 6], fill=(221, 217, 208))
        draw_block(d, cx + 9, note_y, c["note"], cw - 18, 21, (52, 55, 60),
                   weight=600, leading=22, max_lines=1,
                   tag="card-note %d" % i)

    # ---------------- map + Sunday updates ----------------
    map_w = 520
    draw_map(img, d, MARGIN, BAND_Y, map_w, BAND_H)
    mf = anton(17)
    d.rectangle([MARGIN, BAND_Y, MARGIN + caps_w("WHERE IT HAPPENED", mf, 2.0)
                 + 22, BAND_Y + 26], fill=INK)
    caps(d, MARGIN + 11, BAND_Y + 19, "WHERE IT HAPPENED", mf, CREAM,
         track=2.0)

    ux = MARGIN + map_w + 20
    uw = W - MARGIN - ux
    caps(d, ux, BAND_Y + 15, UPDATES_TITLE,
         anton(fit_anton(UPDATES_TITLE, uw, 18, 1.1)), INK, track=1.1)
    d.rectangle([ux, BAND_Y + 22, W - MARGIN, BAND_Y + 24], fill=INK)
    uy = BAND_Y + 30
    tf = anton(15)
    tw = max(caps_w(day, tf, 1.2) for day, _ in UPDATES) + 12
    for day, text in UPDATES:
        d.rectangle([ux, uy + 2, ux + tw, uy + 20], fill=INK_SOFT)
        caps(d, ux + 6, uy + 16, day, tf, CREAM, track=1.2)
        uy = draw_block(d, ux + tw + 8, uy, text, uw - tw - 8, 19, INK,
                        leading=21, max_lines=2, even=True,
                        tag="update %s" % day) + 5
    if uy > BAND_Y + BAND_H + 2:
        raise ValueError("updates column overflows (%d)" % uy)

    # ---------------- date check ----------------
    d.rectangle([0, CHECK_Y, W, H], fill=INK)
    d.rectangle([0, CHECK_Y, W, CHECK_Y + 4], fill=RED)
    tf2 = anton(19)
    endx = caps(d, MARGIN, CHECK_Y + 26, "DATE CHECK", tf2, RED, track=1.6)
    caps(d, endx + 8, CHECK_Y + 26, CHECK_TITLE, tf2, CREAM, track=1.6)
    sf = anton(22)
    sw = caps_w(STAMP_TEXT, sf, 1.6)
    caps(d, W - MARGIN - sw, CHECK_Y + 27, STAMP_TEXT, sf, RED, track=1.6)
    cy = CHECK_Y + 32
    df2 = anton(17)
    dw = max(caps_w(day, df2, 1.3) for day, _ in CHECKS)
    for day, text in CHECKS:
        d.rectangle([MARGIN, cy + 3, MARGIN + dw + 12, cy + 21],
                    fill=(84, 92, 104))
        caps(d, MARGIN + 6, cy + 17, day, df2, CREAM, track=1.3)
        draw_block(d, MARGIN + dw + 22, cy, text, COL - dw - 22, 20,
                   (223, 220, 213), leading=21, max_lines=1,
                   tag="check %s" % day)
        cy += 22
    if cy > H - 4:
        raise ValueError("date check overflows (%d)" % cy)

    return img.convert("RGB")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img = render()
    out = os.path.join(root, "entry.png")
    img.save(out, format="PNG", optimize=True)
    size = os.path.getsize(out)
    if size > 1048576:
        img.convert("P", palette=Image.ADAPTIVE, colors=192).save(
            out, format="PNG", optimize=True)
        size = os.path.getsize(out)
    img.resize((300, 300), Image.LANCZOS).save(
        os.path.join(root, "preview_300.png"))
    img.resize((512, 512), Image.LANCZOS).save(
        os.path.join(root, "preview_512.png"))
    print("entry.png  %dx%d  %d bytes (%.1f KiB)"
          % (img.width, img.height, size, size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
