"""تصویر هیولای هالووین (باس‌فایت) برای بازی گروهی — با Pillow ساخته می‌شود.
اگر Pillow نصب نباشد، render() مقدار None برمی‌گرداند و ربات فقط متن می‌فرستد."""
import io
import math
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
    OK = True
except Exception:       # pragma: no cover
    OK = False

W, H = 1024, 576
S = 2                   # ابر-نمونه‌برداری برای لبه‌های نرم
_BASE = {}
_FONT_CANDS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size):
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(here, "static", "monster_font.ttf")] + _FONT_CANDS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


PALETTES = [  # (آسمان بالا، آسمان پایین، کدو روشن، کدو تیره، درخشش چشم، هاله)
    ((12, 6, 34), (58, 18, 70), (255, 140, 25), (150, 50, 8), (255, 235, 90), (255, 60, 20)),
    ((6, 12, 38), (24, 38, 84), (255, 120, 20), (140, 40, 6), (140, 255, 90), (90, 255, 120)),
    ((26, 6, 24), (80, 14, 44), (240, 100, 20), (120, 28, 8), (255, 70, 50), (255, 30, 60)),
    ((8, 8, 30), (40, 20, 90), (255, 160, 40), (160, 70, 10), (120, 220, 255), (120, 120, 255)),
]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _glow(img, xy_draw_fn, blur, strength=1.0):
    """یک لایه‌ی درخشان (بلور) روی تصویر می‌اندازد"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xy_draw_fn(d)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    if strength != 1.0:
        a = layer.getchannel("A").point(lambda v: min(255, int(v * strength)))
        layer.putalpha(a)
    img.alpha_composite(layer)


def _poly_jitter(rng, pts, j):
    return [(x + rng.uniform(-j, j), y + rng.uniform(-j, j)) for x, y in pts]


def _build_base(seed):
    rng = random.Random(seed)
    pal = PALETTES[seed % len(PALETTES)]
    sky_t, sky_b, pk_l, pk_d, eye, aura = pal
    w, h = W * S, H * S
    img = Image.new("RGBA", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):                                          # آسمان شب
        px.line([(0, y), (w, y)], fill=_lerp(sky_t, sky_b, (y / h) ** 1.4) + (255,))
    for _ in range(170):                                        # ستاره‌ها
        x, y = rng.randrange(w), rng.randrange(int(h * 0.55))
        r = rng.choice((1, 1, 2, 3))
        c = rng.randrange(140, 255)
        px.ellipse([x - r, y - r, x + r, y + r], fill=(c, c, 255, rng.randrange(120, 255)))
    # ماه بزرگ
    mx, my, mr = int(w * 0.80), int(h * 0.22), int(h * 0.14)
    _glow(img, lambda d: d.ellipse([mx - mr * 2, my - mr * 2, mx + mr * 2, my + mr * 2], fill=(255, 220, 140, 70)), 70)
    px.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 238, 190, 255))
    for cx, cy, cr in ((-0.35, -0.2, 0.22), (0.25, 0.3, 0.28), (-0.1, 0.45, 0.15), (0.4, -0.3, 0.12)):
        px.ellipse([mx + cx * mr - cr * mr, my + cy * mr - cr * mr, mx + cx * mr + cr * mr, my + cy * mr + cr * mr],
                   fill=(235, 215, 165, 255))
    # ابرهای تیره
    for _ in range(7):
        cx, cy = rng.randrange(w), rng.randrange(int(h * 0.05), int(h * 0.45))
        for k in range(6):
            rr = rng.randrange(50, 120)
            ox = cx + rng.randrange(-180, 180)
            oy = cy + rng.randrange(-20, 20)
            px.ellipse([ox - rr * 1.6, oy - rr * 0.5, ox + rr * 1.6, oy + rr * 0.5], fill=(20, 8, 34, 70))
    # قلعه‌ی شاهنشاهی (چپ)
    cx0 = int(w * 0.06)
    base_y = int(h * 0.78)
    castle = (14, 8, 26, 255)
    px.rectangle([cx0, base_y - 230, cx0 + 330, base_y], fill=castle)
    for tx, th in ((cx0 - 20, 330), (cx0 + 120, 400), (cx0 + 270, 300)):
        px.rectangle([tx, base_y - th, tx + 90, base_y], fill=castle)
        px.polygon([(tx - 14, base_y - th), (tx + 45, base_y - th - 110), (tx + 104, base_y - th)], fill=castle)
    for tx, th in ((cx0 - 20, 330), (cx0 + 120, 400), (cx0 + 270, 300)):
        for wy in (th - 70, th - 150):
            px.rectangle([tx + 34, base_y - wy, tx + 56, base_y - wy + 38], fill=(255, 200, 80, 255))
    # تپه و قبرستان
    px.polygon([(0, h)] + [(x, base_y + 20 + 24 * math.sin(x / 190.0)) for x in range(0, w + 40, 40)] + [(w, h)],
               fill=(10, 6, 18, 255))
    for _ in range(11):
        x = rng.randrange(int(w * 0.40), w)
        y = base_y + 60 + rng.randrange(0, int(h * 0.12))
        tw, th = rng.randrange(34, 56), rng.randrange(52, 86)
        px.rounded_rectangle([x, y - th, x + tw, y], radius=tw // 2, fill=(26, 18, 40, 255))
        px.line([(x + tw // 2, y - th + 14), (x + tw // 2, y - th + 34)], fill=(60, 48, 80, 255), width=3)
    # درخت‌های خشک
    def tree(x, y, ln, ang, dep):
        if dep == 0 or ln < 10:
            return
        ex, ey = x + ln * math.cos(ang), y - ln * math.sin(ang)
        px.line([(x, y), (ex, ey)], fill=(8, 4, 14, 255), width=max(2, dep * 3))
        tree(ex, ey, ln * 0.72, ang + rng.uniform(0.25, 0.6), dep - 1)
        tree(ex, ey, ln * 0.70, ang - rng.uniform(0.25, 0.6), dep - 1)
    tree(int(w * 0.93), base_y + 70, 150, math.pi / 2 + 0.15, 6)
    tree(int(w * 0.42), base_y + 60, 110, math.pi / 2 - 0.1, 5)
    # هاله‌ی پشت هیولا
    bx, by = int(w * 0.52), int(h * 0.56)
    br = int(h * 0.34)
    _glow(img, lambda d: d.ellipse([bx - br * 1.9, by - br * 1.5, bx + br * 1.9, by + br * 1.5], fill=aura + (120,)), 90)
    # پیچک‌ها/بازوهای هیولا با چنگال
    for sgn in (-1, 1):
        pts = []
        for i in range(0, 41):
            t = i / 40
            x = bx + sgn * (br * 0.95 + t * br * 1.35)
            y = by + br * 0.35 - math.sin(t * 2.6) * br * 0.7 + t * br * 0.55
            pts.append((x, y))
        for i in range(len(pts) - 1):
            wd = int((1 - i / 40) * 70 + 18)
            px.line([pts[i], pts[i + 1]], fill=(32, 70, 26, 255), width=wd)
            px.line([pts[i], pts[i + 1]], fill=(60, 120, 40, 255), width=max(2, wd // 3))
        ex, ey = pts[-1]
        for k in (-1, 0, 1):
            ang = math.radians(-70 + k * 35 + (0 if sgn == 1 else 40))
            px.polygon([(ex, ey), (ex + sgn * 70 * math.cos(ang) - 14, ey - 70 * math.sin(ang) - 40),
                        (ex + sgn * 20, ey + 10)], fill=(235, 225, 190, 255))
    # بدنه‌ی کدو
    body = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    lobes = [(-0.62, 0.78), (-0.31, 0.92), (0.0, 1.0), (0.31, 0.92), (0.62, 0.78)]
    for ox, sc in sorted(lobes, key=lambda z: -abs(z[0])):
        rw, rh = br * 0.62, br * 0.98 * sc
        bd.ellipse([bx + ox * br * 1.5 - rw, by - rh * 0.5 - br * 0.05 - rh * 0.5 + rh * 0.5 - rh * 0.5,
                    bx + ox * br * 1.5 + rw, by + rh * 0.5 + br * 0.05 + rh * 0.5 - rh * 0.5], fill=pk_d + (255,))
    # گرادیان شعاعی روی بدنه
    mask = body.getchannel("A")
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for k in range(40, 0, -1):
        t = k / 40
        col = _lerp(pk_l, pk_d, t ** 1.3)
        gd.ellipse([bx - br * 1.55 * t - br * 0.1, by - br * 0.95 * t - br * 0.15, bx + br * 1.55 * t - br * 0.1,
                    by + br * 0.95 * t - br * 0.15], fill=col + (255,))
    clipped = Image.new("RGBA", img.size, (0, 0, 0, 0))
    clipped.paste(grad, (0, 0), mask)
    body = clipped
    groove = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdr = ImageDraw.Draw(groove)
    for ox in (-0.9, -0.45, 0.0, 0.45, 0.9):                     # شیارهای کدو (فقط داخل بدنه)
        cxg = bx + ox * br * 1.45
        gdr.ellipse([cxg - br * 0.30, by - br * 1.05, cxg + br * 0.30, by + br * 0.95], outline=pk_d + (200,), width=14)
    gdr.ellipse([bx - br * 1.62, by - br * 0.88, bx + br * 1.48, by + br * 0.88], outline=(0, 0, 0, 60), width=26)
    ga = ImageChops.multiply(groove.getchannel("A"), body.getchannel("A"))
    groove.putalpha(ga)
    body.alpha_composite(groove)
    img.alpha_composite(body)
    # دمبرگ
    px = ImageDraw.Draw(img)
    stem = [(bx - 30, by - br * 0.92), (bx + 10, by - br * 1.32), (bx + 90, by - br * 1.42), (bx + 70, by - br * 1.24),
            (bx + 40, by - br * 1.2), (bx + 40, by - br * 0.92)]
    px.polygon(stem, fill=(54, 84, 30, 255), outline=(20, 36, 12, 255))
    # چشم‌ها و دهان درخشان
    def facial(d):
        for sgn in (-1, 1):
            ex = bx + sgn * br * 0.52
            ey = by - br * 0.28
            d.polygon([(ex - sgn * br * 0.34, ey + br * 0.10), (ex + sgn * br * 0.30, ey - br * 0.30),
                       (ex + sgn * br * 0.24, ey + br * 0.20)], fill=eye + (255,))
        pts = [(bx - br * 0.95, by + br * 0.18)]
        n = 11
        for i in range(n):
            x0 = bx - br * 0.95 + i * (br * 1.9 / n)
            x1 = bx - br * 0.95 + (i + 0.5) * (br * 1.9 / n)
            pts.append((x0, by + br * (0.18 if i % 2 == 0 else 0.34) + 0))
            pts.append((x1, by + br * 0.52 + (br * 0.10 if i % 2 else 0)))
        pts.append((bx + br * 0.95, by + br * 0.18))
        pts.append((bx + br * 0.5, by + br * 0.78))
        pts.append((bx - br * 0.5, by + br * 0.78))
        d.polygon(pts, fill=eye + (255,))
    _glow(img, lambda d: facial(d), 30, 1.6)
    facial(px)
    dark = (30, 8, 6, 255)                                       # دندان‌ها
    for i in range(10):
        x = bx - br * 0.85 + i * (br * 1.7 / 9)
        up = i % 2 == 0
        y0 = by + br * (0.20 if up else 0.74)
        y1 = y0 + br * (0.22 if up else -0.22)
        px.polygon([(x - br * 0.07, y0), (x + br * 0.07, y0), (x, y1)], fill=dark)
    for sgn in (-1, 1):                                          # مردمک‌های تیره‌ی چشم
        ex = bx + sgn * br * 0.50
        ey = by - br * 0.20
        px.ellipse([ex - 18, ey - 26, ex + 18, ey + 26], fill=dark)
    # خفاش‌ها
    for _ in range(6):
        x, y, sz = rng.randrange(w), rng.randrange(int(h * 0.06), int(h * 0.4)), rng.randrange(26, 60)
        px.polygon([(x, y), (x - sz, y - sz * 0.5), (x - sz * 0.5, y + sz * 0.1), (x, y + sz * 0.35),
                    (x + sz * 0.5, y + sz * 0.1), (x + sz, y - sz * 0.5)], fill=(6, 2, 12, 255))
    # مه پایین
    fog = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for _ in range(22):
        x, y = rng.randrange(-100, w), int(h * rng.uniform(0.80, 0.98))
        rr = rng.randrange(120, 260)
        fd.ellipse([x - rr, y - rr * 0.25, x + rr, y + rr * 0.25], fill=(190, 180, 220, 26))
    img.alpha_composite(fog.filter(ImageFilter.GaussianBlur(22)))
    vig = Image.new("L", img.size, 0)                            # تاریکی گوشه‌ها
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark_l = Image.new("RGBA", img.size, (0, 0, 0, 170))
    dark_l.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.67)))
    img.alpha_composite(dark_l)
    out = img.resize((W, H), Image.LANCZOS)
    geo = {"bx": bx / S, "by": by / S, "br": br / S}
    return out, geo


def _base(seed):
    k = seed % len(PALETTES)
    if k not in _BASE:
        _BASE[k] = _build_base(k)
    img, geo = _BASE[k]
    return img.copy(), geo


def _text_c(d, xy, text, font, fill, stroke=4, stroke_fill=(0, 0, 0, 255), anchor="mm"):
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def render(hp, maxhp, seed=0, hits=(), state="live"):
    """PNG بایت‌ها. hits: فهرست دمیج‌ها (عدد) یا None برای خطا. state: live | dead | safe(هیچ‌کس نجنگید)"""
    if not OK:
        return None
    try:
        img, geo = _base(int(seed))
        d = ImageDraw.Draw(img)
        bx, by, br = geo["bx"], geo["by"], geo["br"]
        if state == "dead":
            gray = img.convert("L").convert("RGBA")
            img = Image.blend(img, gray, 0.78)
            img = Image.blend(img, Image.new("RGBA", img.size, (0, 0, 0, 255)), 0.28)
            d = ImageDraw.Draw(img)
            for _ in range(3):                                   # ترک
                x = bx + random.Random(seed).uniform(-br, br)
                d.line([(x, by - br * 0.6), (x + 40, by), (x - 30, by + br * 0.5)], fill=(255, 255, 255, 200), width=5)
        # نوار جان بالای هیولا
        bw, bh = 520, 38
        x0, y0 = bx - bw / 2, 34
        d.rounded_rectangle([x0 - 6, y0 - 6, x0 + bw + 6, y0 + bh + 6], radius=14, fill=(0, 0, 0, 190))
        frac = max(0.0, min(1.0, hp / float(maxhp or 1)))
        col = (80, 220, 90) if frac > 0.55 else ((250, 190, 40) if frac > 0.25 else (235, 50, 40))
        if frac > 0:
            d.rounded_rectangle([x0, y0, x0 + bw * frac, y0 + bh], radius=10, fill=col + (255,))
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=10, outline=(255, 255, 255, 220), width=2)
        f1 = _font(34)
        label = f"HP  {int(max(hp, 0))} / {int(maxhp)}"
        _text_c(d, (bx, y0 + bh / 2 + 1), label, f1, (255, 255, 255, 255), stroke=3)
        # آیکون کدوی کوچک کنار نوار
        ix, iy = x0 - 44, y0 + bh / 2
        d.ellipse([ix - 22, iy - 20, ix + 22, iy + 20], fill=(255, 130, 20, 255), outline=(120, 40, 5, 255), width=3)
        d.polygon([(ix - 10, iy - 8), (ix - 3, iy + 2), (ix - 14, iy + 2)], fill=(30, 10, 0, 255))
        d.polygon([(ix + 10, iy - 8), (ix + 3, iy + 2), (ix + 14, iy + 2)], fill=(30, 10, 0, 255))
        d.rectangle([ix - 3, iy - 30, ix + 5, iy - 18], fill=(60, 100, 30, 255))
        # دمیج‌های پرنده روی هیولا
        f2 = _font(70)
        for i, h_ in enumerate(hits[:3]):
            px_ = bx + (i - 1) * br * 1.0
            py_ = by - br * (0.78 if i % 2 == 0 else 0.55)
            if h_:
                _text_c(d, (px_, py_), f"-{int(h_)}", f2, (255, 60, 50, 255), stroke=8, stroke_fill=(255, 255, 255, 255))
            else:
                _text_c(d, (px_, py_), "MISS", _font(54), (215, 220, 230, 255), stroke=7, stroke_fill=(25, 25, 40, 255))
        if state == "dead":
            _text_c(d, (bx, H * 0.55), "DEFEATED", _font(96), (255, 235, 150, 255), stroke=9, stroke_fill=(70, 20, 0, 255))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
        return buf.getvalue()
    except Exception:
        import logging
        logging.exception("monster_art.render")
        return None
