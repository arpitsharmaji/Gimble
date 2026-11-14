"""Illustrated placeholder portraits for the DEMO seed data (no real people, no stock photos).

Real partners upload their own photos; these only make a fresh dev/demo install look alive.
"""
import colorsys, random
from PIL import Image, ImageDraw, ImageFilter

W, H = 800, 1000
S = 2  # supersampling factor for smooth edges

SKIN = [(246, 214, 189), (232, 190, 160), (198, 149, 114), (160, 112, 82), (120, 82, 58)]
HAIR = [(38, 27, 24), (70, 44, 30), (125, 78, 42), (28, 22, 38), (168, 120, 64)]


def _hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def _gradient(c1, c2, size):
    mask = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, c2), Image.new("RGB", size, c1), mask)


def portrait(hue: int, variant: int, style: str = "long", skin: int = 1, hair: int = 0, seed: int = 0) -> Image.Image:
    rnd = random.Random(seed * 100 + variant)
    w, h = W * S, H * S
    pal = [(hue, 0.55, 0.30), (hue + 40, 0.65, 0.18)] if variant == 0 else \
          [(hue + 20, 0.60, 0.42), (hue - 30, 0.55, 0.20)] if variant == 1 else \
          [(hue - 25, 0.70, 0.55), (hue + 70, 0.55, 0.22)]
    img = _gradient(_hsl(*pal[0]), _hsl(*pal[1]), (w, h)).convert("RGBA")

    # soft background shapes: bokeh lights (cafe / city feel)
    bokeh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bokeh)
    for _ in range(16 if variant else 9):
        r = rnd.randint(40, 150) * S
        x, y = rnd.randint(0, w), rnd.randint(0, int(h * 0.65))
        col = _hsl(hue + rnd.randint(-40, 80), 0.8, rnd.uniform(0.6, 0.8))
        bd.ellipse([x - r, y - r, x + r, y + r], fill=col + (rnd.randint(28, 70),))
    img = Image.alpha_composite(img, bokeh.filter(ImageFilter.GaussianBlur(14 * S)))

    d = ImageDraw.Draw(img)
    cx = w // 2 + (rnd.randint(-40, 40) * S if variant else 0)
    skin_c, hair_c = SKIN[skin % 5], HAIR[hair % 5]
    cloth = _hsl(hue + (180 if variant == 1 else 30 + variant * 60), 0.45, 0.55 if variant != 2 else 0.4)

    # hair behind the head (long / bun)
    top = int(h * 0.14)
    if style == "long":
        d.rounded_rectangle([cx - 215 * S, top + 40 * S, cx + 215 * S, top + 700 * S], radius=150 * S, fill=hair_c)
    # shoulders & torso
    d.ellipse([cx - 400 * S, int(h * 0.55), cx + 400 * S, int(h * 1.25)], fill=cloth)
    d.rectangle([cx - 66 * S, int(h * 0.43), cx + 66 * S, int(h * 0.62)], fill=tuple(int(c * .92) for c in skin_c))  # neck
    d.pieslice([cx - 105 * S, int(h * 0.54), cx + 105 * S, int(h * 0.66)], 0, 180, fill=tuple(int(c * .88) for c in skin_c))  # collar shadow
    # head
    hx0, hy0, hx1, hy1 = cx - 150 * S, top + 60 * S, cx + 150 * S, top + 540 * S
    d.ellipse([hx0, hy0, hx1, hy1], fill=skin_c)
    # ears
    for sx in (-1, 1):
        ex = cx + sx * 148 * S
        d.ellipse([ex - 26 * S, top + 290 * S, ex + 26 * S, top + 380 * S], fill=tuple(int(c * .96) for c in skin_c))
    # hair on top / fringe
    if style == "short":
        d.pieslice([hx0 - 14 * S, hy0 - 40 * S, hx1 + 14 * S, hy0 + 330 * S], 180, 360, fill=hair_c)
        d.rectangle([hx0 - 6 * S, hy0 + 110 * S, hx0 + 38 * S, hy0 + 220 * S], fill=hair_c)
        d.rectangle([hx1 - 38 * S, hy0 + 110 * S, hx1 + 6 * S, hy0 + 220 * S], fill=hair_c)
    elif style == "bun":
        d.ellipse([cx - 95 * S, top - 80 * S, cx + 95 * S, top + 90 * S], fill=hair_c)
        d.pieslice([hx0 - 10 * S, hy0 - 25 * S, hx1 + 10 * S, hy0 + 330 * S], 180, 360, fill=hair_c)
    else:
        d.pieslice([hx0 - 24 * S, hy0 - 50 * S, hx1 + 24 * S, hy0 + 360 * S], 180, 360, fill=hair_c)
        d.polygon([(cx - 165 * S, hy0 + 120 * S), (cx + 30 * S, hy0 + 20 * S), (cx + 165 * S, hy0 + 150 * S), (cx + 165 * S, hy0 + 40 * S), (cx - 165 * S, hy0 + 40 * S)], fill=hair_c)
    # simple, friendly face: eyes, brows, smile, blush
    eye_y = top + 270 * S
    for sx in (-1, 1):
        ex = cx + sx * 58 * S
        d.ellipse([ex - 15 * S, eye_y - 11 * S, ex + 15 * S, eye_y + 11 * S], fill=(40, 30, 34))
        d.arc([ex - 30 * S, eye_y - 50 * S, ex + 30 * S, eye_y - 18 * S], 200, 340, fill=hair_c, width=7 * S)
        d.ellipse([ex - 34 * S, eye_y + 42 * S, ex + 34 * S, eye_y + 80 * S], fill=(255, 130, 140, 28))
    d.arc([cx - 48 * S, top + 350 * S, cx + 48 * S, top + 430 * S], 25, 155, fill=(150, 60, 70), width=8 * S)

    # light: soft glow from the top-left + vignette, then film grain
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-w // 2, -h // 3, w, h // 2], fill=(255, 235, 215, 70))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(120 * S)))
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse([-w // 6, -h // 10, w + w // 6, h + h // 10], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160 * S))
    img = Image.composite(img, Image.new("RGBA", (w, h), (10, 8, 16, 255)), vig)
    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    grain = Image.effect_noise((W, H), 22).convert("RGB")
    return Image.blend(img, grain, 0.045)


def save_portraits(dir_path, user_id: int, hue: int, style: str, skin: int, hair: int, count: int = 3) -> list[str]:
    """Writes `count` JPEGs named like real uploads and returns their /uploads/... URLs."""
    import secrets
    dir_path.mkdir(parents=True, exist_ok=True)
    urls = []
    for v in range(count):
        name = f"u{user_id}_{secrets.token_hex(8)}.jpg"
        portrait(hue, v, style, skin, hair, seed=user_id).save(dir_path / name, "JPEG", quality=84, optimize=True)
        urls.append(f"/uploads/{name}")
    return urls
