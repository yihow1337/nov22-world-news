#!/usr/bin/env python3
"""Render entry.png: a typographic editorial poster of Sunday 22 November 2026
world news.

Local tool only -- it needs Pillow. The program the grader runs (main.py)
never imports this; it only copies the committed entry.png.

    python3 tools/render.py        # writes entry.png + preview_300/512.png

Layout notes
  * Display type (Anton) is positioned by BASELINE, so line spacing is exact.
  * Body copy (Source Sans 3 variable) is drawn one word at a time with an
    explicit, generous word gap: at 300 px the font's own spacing reads as
    mid-word breaks.
  * draw_block()'s max_lines is a layout assertion -- if copy grows past its
    box the render fails loudly instead of quietly overlapping.
"""

import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W = H = 1024
SS = 4  # supersample factor for the drawn glyph tiles

GOOGLE = "/usr/share/fonts/truetype/sand-box/google"
ANTON = os.path.join(GOOGLE, "Anton", "Anton-Regular.ttf")
SANS = os.path.join(GOOGLE, "Source Sans 3", "SourceSans3-VariableFont_wght.ttf")

PAPER = (244, 241, 234)
INK = (22, 24, 27)
INK_SOFT = (72, 76, 82)
RED = (176, 32, 28)
SLATE = (40, 66, 90)
CREAM = (252, 250, 246)

MARGIN = 44
COL = W - 2 * MARGIN  # 936 px of content

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


# --- word-level typesetting -------------------------------------------------

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def tokens(text):
    """-> [(word, is_bold)] honouring **emphasis**.

    A chunk that does not start on whitespace is glued to the previous word,
    so "**Murat Kurum**," keeps its comma instead of spacing it off.
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
        gap = round(size * 0.33)
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
    """Re-wrap the same number of lines into the narrowest column that still
    holds them, so a two-line headline does not end on one orphan word."""
    n = len(lines)
    if n < 2:
        return lines
    lo, hi, best = int(max_w * 0.45), int(max_w), lines
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
    """Draw wrapped body copy from a top-left corner. Returns the y below it."""
    lines, gap = layout(text, max_w, size, weight, bold_weight, gap)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError("%s: %d lines (max %d) for %r"
                         % (tag or "block", len(lines), max_lines, text[:46]))
    if even:
        lines = balance(text, lines, gap, max_w, size, weight, bold_weight)
    if leading is None:
        leading = round(size * 1.30)
    cy = y
    for line in lines:
        cx = x
        for word, font, ww in line:
            d.text((cx, cy), word, font=font, fill=fill)
            cx += ww + gap
        cy += leading
    return cy


def caps(d, x, baseline, text, font, fill, track=0.0):
    """Letter-spaced caps on a baseline, glyph by glyph. Returns end x."""
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
    """Height of the inked caps above the baseline, measured not guessed."""
    x0, y0, x1, y1 = font.getbbox(text, anchor="ls")
    return -y0


def fit_anton(text, target_w, max_size, track=0.0):
    """Largest Anton size (<= max_size) whose tracked text fits target_w."""
    size = max_size
    while size > 10 and caps_w(text, anton(size), track) > target_w:
        size -= 1
    return size


# --- drawn glyphs -----------------------------------------------------------
# Painted on supersampled tiles so diagonals and curves come down antialiased.

def tile(w, h):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def place(base, t, x, y):
    base.alpha_composite(t.resize((t.width // SS, t.height // SS),
                                  Image.LANCZOS), (x, y))


def glyph_building(w, h):
    """Five-storey block with its right end collapsed -- Dymer."""
    img, d = tile(w, h)
    s = SS
    base = (h - 6) * s
    left, right = 3 * s, int(w * 0.62) * s
    d.rectangle([left, 6 * s, right, base], fill=INK)
    rows, cols = 5, 3
    fh = (base - 6 * s) / rows
    cw = (right - left) / cols
    for r in range(rows):
        for c in range(cols):
            wx = left + c * cw + cw * 0.22
            wy = 6 * s + r * fh + fh * 0.26
            d.rectangle([wx, wy, wx + cw * 0.52, wy + fh * 0.44], fill=CREAM)
    # the collapsed end: a slumped wedge of floors and rubble
    d.polygon([(right, 6 * s), (right, base), ((w - 4) * s, base),
               ((w - 4) * s, int(h * 0.55) * s)], fill=INK_SOFT)
    for rx, rw, rh in ((1, 12, 5), (15, 9, 3), (26, 10, 4)):
        d.rectangle([right + rx * s, base - rh * s,
                     right + (rx + rw) * s, base], fill=INK)
    d.rectangle([0, base, w * s, base + 3 * s], fill=INK)
    return img


def glyph_ship(w, h):
    """Ship at a quay with a blast above the deck -- Benghazi."""
    img, d = tile(w, h)
    s = SS
    water = (h - 12) * s
    d.polygon([(8 * s, water - 13 * s), ((w - 8) * s, water - 13 * s),
               ((w - 18) * s, water), (18 * s, water)], fill=INK)
    d.rectangle([int(w * 0.30) * s, water - 26 * s,
                 int(w * 0.52) * s, water - 13 * s], fill=INK)
    d.rectangle([int(w * 0.36) * s, water - 34 * s,
                 int(w * 0.43) * s, water - 26 * s], fill=INK)
    cx, cy = int(w * 0.70) * s, water - 30 * s
    pts = []
    for i in range(16):
        ang = math.pi * 2 * i / 16 - math.pi / 2
        r = (20 if i % 2 == 0 else 9) * s
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.86))
    d.polygon(pts, fill=RED)
    for i in range(3):
        yy = water + (3 + i * 4) * s
        d.line([(2 * s, yy), ((w - 2) * s, yy)], fill=INK_SOFT, width=2 * s)
    return img


def glyph_crowd(w, h):
    """Marchers with placards -- Europe's cost-of-living protests."""
    img, d = tile(w, h)
    s = SS
    ground = (h - 5) * s
    for hx in (10, 29, 48, 67, 86):
        r = 4.5 * s
        d.ellipse([hx * s - r, ground - 23 * s - r,
                   hx * s + r, ground - 23 * s + r], fill=INK)
        d.rectangle([hx * s - 6 * s, ground - 17 * s,
                     hx * s + 6 * s, ground], fill=INK)
    for px, col, pw in ((16, RED, 30), (56, INK, 32)):
        d.rectangle([(px + pw // 2 - 1) * s, 22 * s,
                     (px + pw // 2 + 2) * s, ground - 16 * s], fill=INK_SOFT)
        d.rectangle([px * s, 3 * s, (px + pw) * s, 23 * s], fill=col)
        for ln in range(2):
            d.rectangle([(px + 5) * s, (9 + ln * 6) * s,
                         (px + pw - 5) * s, (12 + ln * 6) * s], fill=CREAM)
    d.rectangle([0, ground, w * s, ground + 3 * s], fill=INK)
    return img


def glyph_factory(w, h):
    """Gutted factory shed still smoking -- Cikande."""
    img, d = tile(w, h)
    s = SS
    base = (h - 6) * s
    top = 30 * s
    body_r = (w - 22) * s
    d.rectangle([3 * s, top, body_r, base], fill=INK)
    step = (body_r - 3 * s) / 3
    for i in range(3):
        x0 = 3 * s + i * step
        d.polygon([(x0, top), (x0 + step, top), (x0 + step, top - 11 * s)],
                  fill=INK)
    d.rectangle([(w - 18) * s, 16 * s, (w - 7) * s, base], fill=INK)
    for i, (ox, r) in enumerate(((-1, 6.5), (5, 8.5), (14, 5.5))):
        cx = (w - 13 + ox) * s
        cy = (11 - i * 2) * s
        d.ellipse([cx - r * s, cy - r * s, cx + r * s, cy + r * s],
                  fill=INK_SOFT)
    d.rectangle([int(w * 0.24) * s, base - 17 * s,
                 int(w * 0.42) * s, base], fill=CREAM)
    d.rectangle([int(w * 0.52) * s, base - 11 * s,
                 int(w * 0.64) * s, base], fill=CREAM)
    d.rectangle([0, base, w * s, base + 3 * s], fill=INK)
    return img


# --- content ----------------------------------------------------------------

DATE = "SUNDAY 22 NOVEMBER 2026"

LEAD_KICKER = ("LEAD · COP31 UN CLIMATE SUMMIT · ANTALYA, TÜRKIYE · "
               "TWO DAYS INTO OVERTIME")
LEAD_H1 = "COP31 ENDS WITHOUT"
LEAD_H2 = "A CLIMATE PACT"
LEAD_SUB = ("Nearly 200 countries broke up in Antalya with no deal adopted, "
            "the longest COP on record.")
LEAD_BODY = (
    "President **Murat Kurum** told the closing plenary there was no "
    "agreement on the text, so the decisions were not adopted, and no new "
    "draft would come: “we did all that we could.” The **European "
    "Union** would not take a text that left out fossil fuels or a "
    "transition away from them; Panama and the Marshall Islands also "
    "withheld support. **António Guterres**: “deeply disappointing.”")
STRIKE_CAP = ("The words the talks broke over — dropped from the late "
              "drafts.")

PANELS = [
    {
        "kicker": "UKRAINE · DYMER, NORTH OF KYIV",
        "head": "Russian drone destroys a five-storey block",
        "body": ("Flats collapsed from the first floor to the fifth, 45 km "
                 "north of Kyiv: **two killed**, one aged 18, four hurt, "
                 "**11 unaccounted for**, two of them children. Zelenskyy "
                 "pressed the US to release Patriots Ukraine has paid for."),
        "glyph": glyph_building,
        "accent": RED,
    },
    {
        "kicker": "LIBYA · BENGHAZI NAVAL BASE",
        "head": "Blast and fire hit a ship in port",
        "body": ("The eastern Libyan government said a first inquiry put the "
                 "dawn explosion **aboard a Russian ship** refuelling on its "
                 "way home, and that a **drone attack was suspected**. "
                 "Injuries, no confirmed deaths, no claim of responsibility."),
        "glyph": glyph_ship,
        "accent": SLATE,
    },
    {
        "kicker": "EUROPE · PORTUGAL TO FRANCE",
        "head": "Cost-of-living protests, third day",
        "body": ("Marches over living costs and affordable housing ran for a "
                 "**third day running**, after a big Friday and smaller "
                 "Saturday rallies. In France it is the sixth weekend of "
                 "protests in a row."),
        "glyph": glyph_crowd,
        "accent": SLATE,
    },
    {
        "kicker": "INDONESIA · CIKANDE, BANTEN",
        "head": "24 body bags from a gutted factory",
        "body": ("Rescuers searched all Sunday at the PT Fonusa Agung Mulia "
                 "candy plant west of Jakarta, burnt out by **Saturday "
                 "evening's fire**: **24 body bags** reached hospital, the "
                 "official toll not yet final, dozens unaccounted for."),
        "glyph": glyph_factory,
        "accent": RED,
    },
]

FOOT_1 = ("COP31 breaks up with no pact · a drone levels a Dymer apartment "
          "block · blast at Benghazi")
FOOT_2 = ("Europe's cost-of-living protests, day three · 24 body bags at the "
          "Cikande candy factory")


# --- composition ------------------------------------------------------------

def render():
    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ---------------- masthead ----------------
    mast_h = 124
    d.rectangle([0, 0, W, mast_h], fill=INK)
    d.rectangle([0, mast_h - 6, W, mast_h], fill=RED)

    lab = anton(19)
    caps(d, MARGIN, 30, "ONE DAY OF WORLD NEWS", lab, PAPER, track=2.6)
    right = "FIVE STORIES · FIVE REGIONS"
    caps(d, W - MARGIN - caps_w(right, lab, 2.6), 30, right, lab,
         (170, 166, 158), track=2.6)

    ds = fit_anton(DATE, COL, 88, 1.5)
    df = anton(ds)
    # spread the date edge to edge of the column
    date_track = (COL - caps_w(DATE, df)) / (len(DATE) - 1)
    caps(d, MARGIN, 108, DATE, df, CREAM, track=date_track)

    # ---------------- lead ----------------
    kf = anton(22)
    d.rectangle([MARGIN, 140, MARGIN + 12, 156], fill=RED)
    caps(d, MARGIN + 23, 156, LEAD_KICKER, kf, RED, track=1.5)

    hs = min(fit_anton(LEAD_H1, COL, 92, 1.0), fit_anton(LEAD_H2, COL, 92, 1.0))
    hf = anton(hs)
    b1 = 232
    b2 = b1 + int(hs * 0.93)
    caps(d, MARGIN, b1, LEAD_H1, hf, INK, track=1.0)
    caps(d, MARGIN, b2, LEAD_H2, hf, INK, track=1.0)
    rule_x = MARGIN + caps_w(LEAD_H2, hf, 1.0) + 24
    d.rectangle([rule_x, b2 - 30, W - MARGIN, b2 - 18], fill=RED)

    y = b2 + 24
    d.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=INK)
    y += 15

    box_w = 286
    box_x = W - MARGIN - box_w
    left_w = box_x - MARGIN - 32

    ty = draw_block(d, MARGIN, y, LEAD_SUB, left_w, 25, INK, weight=600,
                    leading=30, max_lines=2, tag="lead-sub", even=True)
    ty += 10
    ty = draw_block(d, MARGIN, ty, LEAD_BODY, left_w, 17, INK_SOFT,
                    leading=21, max_lines=5, tag="lead-body")

    # the device: FOSSIL FUELS, struck out. Box height follows the type.
    fs = fit_anton("FOSSIL", box_w - 52, 53, 1.0)
    ff = anton(fs)
    cap_h = ink_top(ff, "FOSSIL")
    line_gap = cap_h + 9
    pad = 14
    bt = y - 2
    bb = bt + pad + cap_h + line_gap + pad
    d.rectangle([box_x, bt, W - MARGIN, bb], fill=INK)
    fb1 = bt + pad + cap_h
    fb2 = fb1 + line_gap
    tx0 = box_x + 24
    for base, word in ((fb1, "FOSSIL"), (fb2, "FUELS")):
        caps(d, tx0, base, word, ff, CREAM, track=1.0)
        # the strike runs the length of the word it cancels, no further
        mid = base - int(cap_h * 0.54)
        d.rectangle([tx0 - 11, mid - 4, tx0 + caps_w(word, ff, 1.0) + 11,
                     mid + 4], fill=RED)
    cy = draw_block(d, box_x, bb + 12, STRIKE_CAP, box_w, 17,
                    INK_SOFT, leading=22, max_lines=2, tag="strike-cap",
                    even=True)

    y = max(ty, cy) + 18

    # ---------------- section rule with inset label ----------------
    d.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=INK)
    sec = "THE SAME SUNDAY, ELSEWHERE"
    sf = anton(19)
    sw = caps_w(sec, sf, 2.2)
    d.rectangle([MARGIN, y - 10, MARGIN + sw + 20, y + 12], fill=PAPER)
    caps(d, MARGIN, y + 8, sec, sf, INK, track=2.2)
    y += 22

    # ---------------- four panels ----------------
    foot_y = 958
    gutter = 30
    pw = (COL - gutter) // 2
    gap_v = 14
    row_h = (foot_y - 12 - y - gap_v) // 2

    for i, p in enumerate(PANELS):
        px = MARGIN + (i % 2) * (pw + gutter)
        py = y + (i // 2) * (row_h + gap_v)
        d.rectangle([px, py, px + pw, py + 3], fill=p["accent"])
        gw, gh = 96, 62
        place(img, p["glyph"](gw, gh), px + pw - gw, py + 12)
        caps(d, px, py + 30, p["kicker"], anton(21), p["accent"], track=1.4)
        hy = draw_block(d, px, py + 36, p["head"], pw - gw - 16, 24, INK,
                        weight=700, leading=27, max_lines=2,
                        tag="panel-head %d" % i, even=True)
        by = max(hy + 8, py + 12 + gh + 8)
        end = draw_block(d, px, by, p["body"], pw, 16.5, INK_SOFT, leading=20,
                         max_lines=4, tag="panel-body %d" % i)
        if end > py + row_h + 4:
            raise ValueError("panel %d overflows its row (%d > %d)"
                             % (i, end, py + row_h + 4))

    # ---------------- footer ----------------
    d.rectangle([0, foot_y, W, H], fill=INK)
    d.rectangle([0, foot_y, W, foot_y + 5], fill=RED)
    stamp = anton(32)
    sw = caps_w("22 NOV 2026", stamp, 1.2)
    caps(d, MARGIN, foot_y + 45, "22 NOV 2026", stamp, CREAM, track=1.2)
    tx = MARGIN + sw + 28
    d.rectangle([tx - 15, foot_y + 20, tx - 13, H - 18], fill=(92, 94, 98))
    fw = W - MARGIN - tx
    draw_block(d, tx, foot_y + 19, FOOT_1, fw, 17, (228, 224, 216),
               leading=23, max_lines=1, tag="foot1")
    draw_block(d, tx, foot_y + 42, FOOT_2, fw, 17, (228, 224, 216),
               leading=23, max_lines=1, tag="foot2")

    return img.convert("RGB")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img = render()
    out = os.path.join(root, "entry.png")
    img.save(out, format="PNG", optimize=True)
    size = os.path.getsize(out)
    if size > 1048576:
        img.convert("P", palette=Image.ADAPTIVE, colors=128).save(
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
