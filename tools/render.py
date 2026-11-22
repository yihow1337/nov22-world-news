#!/usr/bin/env python3
"""Render entry.png: Sunday 22 November 2026 as a picture-led news poster.

Local tool only (needs Pillow). The grader never runs this -- it runs main.py,
which copies the committed entry.png. Run:

    python3 tools/render.py

It writes entry.png plus gitignored preview_300.png / preview_512.png so the
composition can be checked at the size the judge actually looks at.

Design rule for this version: every fact is carried by a drawn picture and a
short label. Three big lead panels, four picture tiles, one date-check band.
Nothing that carries a fact is set below ~30px on the 1024 canvas.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

_cos, _sin = math.cos, math.sin

W = H = 1024
GOOGLE = "/usr/share/fonts/truetype/sand-box/google"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- palette ---
PAPER = (243, 240, 233)
INK = (20, 22, 26)
MUTED = (96, 100, 108)
RULE = (203, 199, 189)
WHITE = (255, 255, 255)
ALERT = (198, 36, 28)

GREEN = (15, 104, 80)       # COP31
CRIMSON = (176, 32, 28)     # Ukraine
NAVY = (26, 60, 112)        # Libya
PLUM = (119, 44, 106)       # Hong Kong
EMBER = (178, 92, 22)       # Indonesia
INDIGO = (68, 72, 158)      # Europe
GOLD = (143, 112, 16)       # Las Vegas


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def tint(c, t=0.12):
    return mix(PAPER, c, t)


# ------------------------------------------------------------------ fonts ---
_CACHE = {}


def anton(size):
    return _font(GOOGLE + "/Anton/Anton-Regular.ttf", size)


def disp(size):
    """Headline face: heavy, semi-condensed, open counters when small."""
    return _font(GOOGLE + "/Barlow Semi Condensed/BarlowSemiCondensed-Black.ttf",
                 size)


def kick(size):
    return _font(GOOGLE + "/Barlow Semi Condensed/BarlowSemiCondensed-Bold.ttf",
                 size)


def body(size, weight="SemiBold"):
    key = ("ss3", size, weight)
    if key not in _CACHE:
        f = ImageFont.truetype(
            GOOGLE + "/Source Sans 3/SourceSans3-VariableFont_wght.ttf", size)
        f.set_variation_by_name(weight)
        _CACHE[key] = f
    return _CACHE[key]


def _font(path, size):
    key = (path, size)
    if key not in _CACHE:
        _CACHE[key] = ImageFont.truetype(path, size)
    return _CACHE[key]


# ------------------------------------------------------------------- text ---
def width_of(d, text, font, track=0):
    if not text:
        return 0
    w = d.textlength(text, font=font)
    return w + track * (len(text) - 1)


def draw_tracked(d, xy, text, font, fill, track=0.0):
    """Draw text with extra letter spacing (keeps Source Sans words apart)."""
    x, y = xy
    if not track:
        d.text((x, y), text, font=font, fill=fill)
        return x + d.textlength(text, font=font)
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + track
    return x - track


def wrap(d, text, font, maxw, track=0):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if not cur or width_of(d, trial, font, track) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, loader, maxw, maxlines, hi, lo, track=0):
    """Largest size in [lo, hi] where text wraps into <= maxlines lines."""
    size = hi
    while size > lo:
        f = loader(size)
        lines = wrap(d, text, f, maxw, track)
        if len(lines) <= maxlines and all(
                width_of(d, ln, f, track) <= maxw for ln in lines):
            return f, lines, size
        size -= 1
    f = loader(lo)
    return f, wrap(d, text, f, maxw, track), lo


def block(d, x, y, lines, font, fill, leading, track=0, center=False,
          maxw=0):
    for i, line in enumerate(lines):
        lx = x
        if center:
            lx = x + (maxw - width_of(d, line, font, track)) / 2
        draw_tracked(d, (lx, y + i * leading), line, font, fill, track)


def cap_block(d, x, y, text, loader, maxw, maxlines, hi, lo, fill, leading_k,
              track=0, maxh=0):
    """Set an all-caps headline as large as the box allows."""
    text = text.upper()
    size = hi
    while size > lo:
        f = loader(size)
        lines = wrap(d, text, f, maxw, track)
        lead = int(round(size * leading_k))
        if (len(lines) <= maxlines
                and all(width_of(d, ln, f, track) <= maxw for ln in lines)
                and (not maxh or lead * len(lines) <= maxh)):
            break
        size -= 1
    f = loader(size)
    lines = wrap(d, text, f, maxw, track)
    lead = int(round(size * leading_k))
    block(d, x, y, lines, f, fill, lead, track)
    return len(lines), size


# --------------------------------------------------------------- pictures ---
SS = 4  # supersample factor for the drawn pictograms


class Art:
    """A supersampled drawing surface in local (unscaled) coordinates."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def _s(self, box):
        return [v * SS for v in box]

    def rect(self, box, fill=None, outline=None, width=1, radius=0):
        box = self._s(box)
        if radius:
            self.d.rounded_rectangle(box, radius * SS, fill=fill,
                                     outline=outline, width=width * SS)
        else:
            self.d.rectangle(box, fill=fill, outline=outline,
                             width=width * SS)

    def poly(self, pts, fill=None, outline=None, width=1):
        pts = [(x * SS, y * SS) for x, y in pts]
        self.d.polygon(pts, fill=fill, outline=outline, width=width * SS)

    def line(self, pts, fill, width, joint=None):
        pts = [(x * SS, y * SS) for x, y in pts]
        self.d.line(pts, fill=fill, width=int(width * SS), joint=joint)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._s(box), fill=fill, outline=outline,
                       width=width * SS)

    def pie(self, box, a, b, fill):
        self.d.pieslice(self._s(box), a, b, fill=fill)

    def text(self, xy, s, font_px, fill, loader=disp, track=0.0):
        f = loader(int(font_px * SS))
        x, y = xy[0] * SS, xy[1] * SS
        if track:
            for ch in s:
                self.d.text((x, y), ch, font=f, fill=fill)
                x += self.d.textlength(ch, font=f) + track * SS
        else:
            self.d.text((x, y), s, font=f, fill=fill)

    def text_w(self, s, font_px, loader=disp, track=0.0):
        f = loader(int(font_px * SS))
        w = self.d.textlength(s, font=f)
        if track:
            w += track * SS * (len(s) - 1)
        return w / SS

    def finish(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def chip(a, x, y, text, px, fg, bg, pad=7):
    """A solid high-contrast tab inside a picture."""
    tw = a.text_w(text, px, kick)
    th = px * 1.12
    a.rect([x, y, x + tw + pad * 2, y + th + pad], fill=bg, radius=3)
    a.text((x + pad, y + pad * 0.45), text, px, fg, kick)
    return tw + pad * 2


# --- lead 1: COP31, no text adopted -----------------------------------------
def art_cop31(w, h):
    a = Art(w, h, tint(GREEN, 0.14))
    # a globe for the near-200 countries in the room
    cx, cy, r = 54, h / 2, 40
    a.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(GREEN, INK, 0.22))
    land = mix(GREEN, PAPER, 0.6)
    for box in ([cx - 32, cy - 26, cx + 2, cy - 2],
                [cx - 20, cy - 8, cx + 6, cy + 14],
                [cx - 6, cy + 10, cx + 20, cy + 30],
                [cx + 10, cy - 30, cx + 36, cy - 12]):
        a.ellipse(box, fill=land)
    a.line([(cx - 39, cy), (cx + 39, cy)], mix(GREEN, PAPER, 0.3), 2)
    a.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK, width=3)

    # the cover decision that never got adopted
    px0, py0, px1, py1 = 122, 10, 268, h - 10
    a.rect([px0 + 9, py0 + 9, px1 + 9, py1 + 9], fill=mix(PAPER, INK, 0.2))
    a.rect([px0, py0, px1, py1], fill=WHITE, outline=INK, width=3)
    a.rect([px0 + 15, py0 + 15, px1 - 15, py0 + 28], fill=GREEN)
    for ln in range(4):
        yy = py0 + 44 + ln * 19
        right = px1 - 15 if ln < 3 else px1 - 54
        a.rect([px0 + 15, yy, right, yy + 7], fill=mix(PAPER, INK, 0.42))
    a.line([(px0 - 12, py0 + 2), (px1 + 12, py1 - 2)], ALERT, 16)
    a.line([(px1 + 12, py0 + 2), (px0 - 12, py1 - 2)], ALERT, 16)
    return a.finish()


# --- lead 2: Ukraine drone night / Dymer ------------------------------------
def art_dymer(w, h):
    a = Art(w, h, tint(CRIMSON, 0.11))
    bg = tint(CRIMSON, 0.11)
    ground = h - 12
    a.rect([0, ground, w, h], fill=mix(PAPER, INK, 0.55))

    bx0, bx1, by0 = 70, 186, 30
    a.rect([bx0, by0, bx1, ground], fill=(44, 47, 53))
    for row in range(5):
        for col in range(4):
            x = bx0 + 11 + col * 26
            y = by0 + 11 + row * 18
            a.rect([x, y, x + 16, y + 11], fill=(232, 227, 214))
    # floors one to five on the right-hand side have come down
    a.poly([(144, by0 - 4), (bx1 + 6, by0 - 4), (bx1 + 6, ground + 2),
            (126, ground + 2), (152, 78)], fill=bg)
    for rub in ([126, ground - 13, 158, ground], [150, ground - 22, 178, ground],
                [170, ground - 10, 194, ground]):
        a.rect(rub, fill=(44, 47, 53))
    a.poly([(146, 84), (158, 52), (164, 74), (174, 60), (178, 104),
            (142, 110)], fill=(226, 92, 24))
    a.poly([(150, 88), (159, 68), (165, 88), (161, 104), (148, 104)],
           fill=(246, 184, 48))

    # strike drone, nose down on its run
    a.poly([(8, 18), (60, 34), (38, 46), (14, 40)], fill=INK)
    a.poly([(38, 36), (58, 32), (47, 50)], fill=INK)
    for i in range(4):
        x = 64 + i * 13
        a.line([(x, 40 + i * 5), (x + 7, 43 + i * 5)], INK, 3)

    # the night's two numbers, set big enough to survive 300px
    a.text((206, 2), "186", 44, CRIMSON)
    a.text((208, 46), "DRONES", 20, INK, kick, 1.0)
    a.text((206, 66), "161", 44, mix(INK, CRIMSON, 0.3))
    a.text((208, 110), "SHOT DOWN", 20, INK, kick, 1.0)
    return a.finish()


# --- lead 3: Benghazi naval base --------------------------------------------
def art_benghazi(w, h):
    a = Art(w, h, tint(NAVY, 0.12))
    water = h - 30
    a.rect([0, water, w, h], fill=mix(NAVY, PAPER, 0.4))
    for i in range(3):
        y = water + 8 + i * 8
        a.line([(14 + i * 16, y), (w - 12, y)], mix(NAVY, PAPER, 0.6), 3)
    a.rect([0, water - 16, 52, water + 5], fill=mix(PAPER, INK, 0.5))

    cx0 = 150
    a.poly([(52, water - 20), (258, water - 20), (240, water + 7),
            (70, water + 7)], fill=mix(NAVY, INK, 0.3))
    a.rect([186, water - 48, 234, water - 20], fill=mix(NAVY, PAPER, 0.2))
    a.rect([200, water - 64, 216, water - 48], fill=mix(NAVY, INK, 0.1))
    a.line([(90, water - 20), (90, water - 58)], mix(NAVY, INK, 0.3), 5)
    a.line([(76, water - 48), (106, water - 48)], mix(NAVY, INK, 0.3), 5)

    # black smoke first, so the fireball sits in front of it
    for sm in ([cx0 - 34, 2, cx0 + 14, 40], [cx0 + 2, 0, cx0 + 54, 36],
               [cx0 + 40, 10, cx0 + 82, 44], [cx0 - 8, 18, cx0 + 44, 58]):
        a.ellipse(sm, fill=mix(INK, PAPER, 0.22))

    cx, cy = cx0, water - 48
    for radii, col in (((54, 24), (164, 26, 20)),
                       ((40, 18), (232, 104, 20)),
                       ((24, 11), (250, 206, 70))):
        burst = []
        for i in range(18):
            ang = 6.283185 * i / 18 + 0.17
            r = radii[0] if i % 2 == 0 else radii[1]
            burst.append((cx + _cos(ang) * r, cy + _sin(ang) * r * 0.86))
        a.poly(burst, fill=col)

    a.poly([(306, 10), (254, 26), (274, 38), (302, 32)], fill=INK)
    a.poly([(274, 28), (296, 32), (282, 46)], fill=INK)
    chip(a, 10, h - 38, "DRONE SUSPECTED", 26, WHITE, ALERT)
    return a.finish()


# --- tiles -------------------------------------------------------------------
def art_hongkong(w, h):
    a = Art(w, h, tint(PLUM, 0.12))
    # ballot slip going into the box: the Election Committee subsector polls
    a.poly([(64, 34), (158, 34), (172, h - 4), (50, h - 4)],
           fill=mix(PLUM, INK, 0.18))
    a.rect([78, 40, 144, 49], fill=mix(PLUM, INK, 0.55))
    a.poly([(92, 2), (152, 11), (146, 41), (86, 32)], fill=WHITE,
           outline=INK, width=2)
    a.line([(100, 20), (110, 30), (136, 9)], PLUM, 7, "curve")
    return a.finish()


def art_cikande(w, h):
    a = Art(w, h, tint(EMBER, 0.13))
    base = h - 4
    a.rect([34, 44, 200, base], fill=(48, 46, 44))
    for i in range(4):
        x = 34 + i * 41.5
        a.poly([(x, 45), (x + 20, 24), (x + 41.5, 45)], fill=(48, 46, 44))
    a.rect([168, 4, 186, 26], fill=(48, 46, 44))
    for i in range(4):
        a.rect([46 + i * 40, 56, 72 + i * 40, 74], fill=(230, 120, 26))
    a.poly([(34, base), (200, base), (200, base - 8), (34, base - 8)],
           fill=(214, 86, 20))
    for sm in ([86, 0, 132, 30], [114, 6, 160, 36], [48, 4, 92, 34],
               [150, 0, 196, 26]):
        a.ellipse(sm, fill=mix(PAPER, INK, 0.3))
    return a.finish()


def art_protest(w, h):
    a = Art(w, h, tint(INDIGO, 0.12))
    a.rect([18, 6, 86, 44], fill=WHITE, outline=INK, width=2)
    for i in range(3):
        a.rect([26, 13 + i * 11, 78 - i * 16, 19 + i * 11],
               fill=mix(PAPER, INK, 0.45))
    a.rect([48, 44, 54, 70], fill=mix(INDIGO, INK, 0.3))
    a.rect([128, 0, 196, 36], fill=INDIGO)
    a.rect([158, 36, 164, 66], fill=mix(INDIGO, INK, 0.3))
    for i in range(8):
        x = 1 + i * 29
        top = 44 + (i % 3) * 5
        shade = mix(INDIGO, INK, 0.3 if i % 2 else 0.12)
        a.ellipse([x, top, x + 24, top + 24], fill=shade)
        a.poly([(x - 9, h), (x - 4, top + 24), (x + 28, top + 24),
                (x + 33, h)], fill=shade)
    return a.finish()


def art_vegas(w, h):
    a = Art(w, h, tint(GOLD, 0.14))
    road = h - 8
    a.rect([0, road, w, h], fill=mix(PAPER, INK, 0.5))
    a.poly([(24, road - 14), (58, road - 14), (72, road - 30),
            (114, road - 30), (122, road - 14), (176, road - 14),
            (176, road - 3), (24, road - 3)], fill=(34, 36, 40))
    a.rect([74, road - 42, 112, road - 30], fill=(34, 36, 40))
    a.rect([12, road - 23, 32, road - 12], fill=(34, 36, 40))
    a.rect([168, road - 26, 190, road - 14], fill=(34, 36, 40))
    for cx in (56, 142):
        a.ellipse([cx - 16, road - 31, cx + 16, road], fill=(18, 19, 22))
        a.ellipse([cx - 6, road - 21, cx + 6, road - 9],
                  fill=mix(PAPER, INK, 0.25))
    fx, fy = 198, 4
    a.rect([fx - 4, fy, fx + 2, road - 2], fill=(34, 36, 40))
    for r in range(3):
        for c in range(3):
            col = WHITE if (r + c) % 2 == 0 else (24, 25, 28)
            a.rect([fx + 2 + c * 11, fy + r * 11,
                    fx + 13 + c * 11, fy + 11 + r * 11], fill=col)
    return a.finish()


# ------------------------------------------------------------------ layout ---
MARGIN = 20
CONTENT = W - MARGIN * 2            # 984
MAST_H = 132
LEAD_Y, LEAD_H = 140, 458
LEAD_W, LEAD_GAP = 318, 15
LEAD_HEAD_H, LEAD_ART_H, LEAD_FACT_H = 54, 140, 96
TILE_Y, TILE_H = 606, 320
TILE_W, TILE_GAP = 237, 12
TILE_ART_H, TILE_FACT_H = 86, 84
BAND_Y = 934

LEADS = [
    dict(accent=GREEN, art=art_cop31, tag=None,
         kicker="COP31 · ANTALYA, TÜRKIYE",
         head="COP31 ends with no text adopted",
         fact="EU refused a text with no fossil fuels"),
    dict(accent=CRIMSON, art=art_dymer, tag=None,
         kicker="UKRAINE · DYMER, NEAR KYIV",
         head="Drone destroys a five-storey block",
         fact="2 killed · 11 unaccounted for"),
    dict(accent=NAVY, art=art_benghazi, tag="CLAIM",
         kicker="LIBYA · BENGHAZI PORT",
         head="Blast and fire at the naval base",
         fact="Eastern govt: a Russian ship was hit"),
]

TILES = [
    dict(accent=PLUM, art=art_hongkong, place="HONG KONG",
         head="98.79% turnout", fact="5,640 of 5,709 electors"),
    dict(accent=EMBER, art=art_cikande, place="INDONESIA · CIKANDE",
         head="24 body bags", fact="Saturday's fire · toll not final"),
    dict(accent=INDIGO, art=art_protest, place="EUROPE",
         head="Day 3 of marches", fact="Living costs · 6th French weekend"),
    dict(accent=GOLD, art=art_vegas, place="LAS VEGAS GP",
         head="Verstappen wins", fact="From pole · Norris +0.639s"),
]

DATE_CHECK = [
    ("THU 19", "Shenzhen summit · ICJ Myanmar · Anthropic IPO"),
    ("FRI 20", "Missiles in Poland · SAT 21 Cikande fire starts"),
]


def masthead(img, d):
    d.rectangle([0, 0, W, MAST_H], fill=INK)
    d.rectangle([0, MAST_H - 7, W, MAST_H], fill=ALERT)

    f = kick(27)
    draw_tracked(d, (MARGIN, 12), "THE WORLD ON ONE DAY", f,
                 mix(INK, PAPER, 0.62), 1.6)
    right = "SEVEN STORIES · FOUR CONTINENTS"
    rw = width_of(d, right, f, 1.6)
    draw_tracked(d, (W - MARGIN - rw, 12), right, f, mix(INK, PAPER, 0.62), 1.6)

    date = "SUNDAY 22 NOVEMBER 2026"
    size, track = 88, 3.0
    while width_of(d, date, anton(size), track) > CONTENT:
        size -= 1
    f = anton(size)
    dw = width_of(d, date, f, track)
    # optically centre the caps in the strip below the standfirst
    bb = d.textbbox((0, 0), date, font=f)
    top = 46 + (MAST_H - 13 - 46 - (bb[3] - bb[1])) / 2 - bb[1]
    draw_tracked(d, ((W - dw) / 2, top), date, f, PAPER, track)


def lead_panel(img, d, x, spec):
    y = LEAD_Y
    acc = spec["accent"]
    d.rectangle([x, y, x + LEAD_W, y + LEAD_H], fill=WHITE)

    # header bar
    hb = LEAD_HEAD_H
    d.rectangle([x, y, x + LEAD_W, y + hb], fill=acc)
    pad = 13
    avail = LEAD_W - pad * 2
    kf, klines, ks = fit(d, spec["kicker"], kick, avail, 1, 32, 22, 1.2)
    draw_tracked(d, (x + pad, y + (hb - ks * 1.28) / 2), klines[0], kf, WHITE,
                 1.2)

    # picture
    img.paste(spec["art"](LEAD_W, LEAD_ART_H), (x, y + hb))
    ay = y + hb + LEAD_ART_H
    d.rectangle([x, ay, x + LEAD_W, ay + 2], fill=acc)

    # headline, sized to the gap between the picture and the fact line
    hy = ay + 14
    room = (y + LEAD_H - LEAD_FACT_H) - hy
    nlines, hsize = cap_block(d, x + pad, hy, spec["head"], disp, avail, 3,
                              46, 34, INK, 1.1, 0.3, maxh=room)

    # one short fact, anchored to the foot of the panel
    fy = y + LEAD_H - LEAD_FACT_H + 4
    d.rectangle([x + pad, fy, x + LEAD_W - pad, fy + 2], fill=RULE)
    ff, flines, fs = fit(d, spec["fact"], lambda s: body(s, "SemiBold"),
                         avail, 2, 30, 24, 0.4)
    block(d, x + pad, fy + 12, flines, ff, mix(INK, PAPER, 0.18),
          int(round(fs * 1.2)), 0.4)

    d.rectangle([x, y, x + LEAD_W, y + LEAD_H], outline=RULE, width=2)


def tile(img, d, x, spec):
    y = TILE_Y
    acc = spec["accent"]
    d.rectangle([x, y, x + TILE_W, y + TILE_H], fill=WHITE)
    d.rectangle([x, y, x + TILE_W, y + 9], fill=acc)

    img.paste(spec["art"](TILE_W, TILE_ART_H), (x, y + 9))
    ty = y + 9 + TILE_ART_H
    pad = 13
    avail = TILE_W - pad * 2

    pf, plines, ps = fit(d, spec["place"], kick, avail, 1, 30, 21, 1.2)
    draw_tracked(d, (x + pad, ty + 7), plines[0], pf, acc, 1.2)
    ty += 7 + int(round(ps * 1.28))

    room = (y + TILE_H - TILE_FACT_H) - ty
    cap_block(d, x + pad, ty, spec["head"], disp, avail, 2, 46, 32, INK, 1.08,
              0.3, maxh=room)

    fy = y + TILE_H - TILE_FACT_H + 2
    d.rectangle([x + pad, fy, x + TILE_W - pad, fy + 2], fill=RULE)
    ff, flines, fs = fit(d, spec["fact"], lambda s: body(s, "SemiBold"),
                         avail, 2, 28, 23, 0.4)
    block(d, x + pad, fy + 10, flines, ff, mix(INK, PAPER, 0.2),
          int(round(fs * 1.2)), 0.4)

    d.rectangle([x, y, x + TILE_W, y + TILE_H], outline=RULE, width=2)


def date_band(d):
    d.rectangle([0, BAND_Y, W, H], fill=INK)
    d.rectangle([0, BAND_Y, W, BAND_Y + 6], fill=ALERT)

    draw_tracked(d, (MARGIN, BAND_Y + 11), "DATE CHECK", disp(36), ALERT, 0.8)
    draw_tracked(d, (MARGIN + 2, BAND_Y + 53), "NOT SUNDAY'S NEWS", kick(24),
                 mix(INK, PAPER, 0.62), 1.1)

    cx = MARGIN + 252
    avail = W - MARGIN - cx
    size = 31
    while size > 22:
        tf, bf = kick(size), body(size, "SemiBold")
        if all(width_of(d, day, tf, 1.2) + 14 +
               width_of(d, txt, bf, 0.4) <= avail
               for day, txt in DATE_CHECK):
            break
        size -= 1
    tf, bf = kick(size), body(size, "SemiBold")
    lead = int(round(size * 1.26))
    top = BAND_Y + (H - BAND_Y - lead * len(DATE_CHECK)) / 2 - 3
    for i, (day, txt) in enumerate(DATE_CHECK):
        yy = top + i * lead
        ex = draw_tracked(d, (cx, yy), day, tf, ALERT, 1.2)
        draw_tracked(d, (ex + 14, yy), txt, bf, PAPER, 0.4)


def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    masthead(img, d)
    for i, spec in enumerate(LEADS):
        lead_panel(img, d, MARGIN + i * (LEAD_W + LEAD_GAP), spec)
    for i, spec in enumerate(TILES):
        tile(img, d, MARGIN + i * (TILE_W + TILE_GAP), spec)
    date_band(d)
    return img


def main():
    img = render()
    out = os.path.join(ROOT, "entry.png")
    img.save(out, "PNG", optimize=True)
    for px in (512, 300):
        img.resize((px, px), Image.LANCZOS).save(
            os.path.join(ROOT, "preview_%d.png" % px), "PNG")
    print("entry.png %dx%d %d bytes" % (img.width, img.height,
                                        os.path.getsize(out)))


if __name__ == "__main__":
    main()
