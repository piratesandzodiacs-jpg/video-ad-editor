#!/usr/bin/env python3
"""يرسم طبقات كرت النهاية (على طريقة فيديو المستخدم) كملفات PNG شفافة 1080x1920.
كل طبقة لحالها عشان ffmpeg يدخلها بالتتابع.

الاستخدام:
  python3 garage/endcard.py --out DIR --logo garage/assets/logo_t.png \
      --phone <الرقم> --address "<العنوان>" --handle repair_painting_cars
الرقم والعنوان ما ينحفظون بالمستودع، يتمرّرون وقت التشغيل.
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
YEL = (242, 190, 34, 255)
WHITE = (255, 255, 255, 255)


def font(size, raqm=False):
    eng = ImageFont.Layout.RAQM if raqm else ImageFont.Layout.BASIC
    return ImageFont.truetype(BOLD, size, layout_engine=eng)


def text_tile(text, size, fill, target_w=None, stroke=0, spacing=0, raqm=False):
    f = font(size, raqm)
    pad = 12 + stroke
    if spacing:
        widths = [f.getlength(c) for c in text]
        tw = int(sum(widths) + spacing * (len(text) - 1))
    else:
        tw = int(f.getlength(text))
    th = int(size * 1.35)
    t = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    if spacing:
        x = pad
        for c, w in zip(text, widths):
            d.text((x, pad), c, font=f, fill=fill, stroke_width=stroke, stroke_fill=fill)
            x += w + spacing
    else:
        kw = dict(direction="rtl", language="ar") if raqm else {}
        d.text((pad, pad), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=fill, **kw)
    t = t.crop(t.getbbox())
    if target_w:
        t = t.resize((target_w, t.height), Image.LANCZOS)
    return t


def shadow(tile, blur=8, alpha=170, off=(0, 5)):
    pad = blur * 3
    out = Image.new("RGBA", (tile.width + 2 * pad, tile.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", tile.size, (0, 0, 0, alpha))
    sh.putalpha(tile.getchannel("A").point(lambda v: v * alpha // 255))
    out.alpha_composite(sh, (pad + off[0], pad + off[1]))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(tile, (pad, pad))
    return out, pad


def place(layer, tile, cx, y, with_shadow=True):
    if with_shadow:
        tile, pad = shadow(tile)
        cx_, y_ = int(cx - tile.width / 2), int(y - pad)
    else:
        cx_, y_ = int(cx - tile.width / 2), int(y)
    layer.alpha_composite(tile, (cx_, y_))


def blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def phone_icon(h=86):
    w = int(h * 0.55)
    ic = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=10, fill=YEL)
    d.rounded_rectangle((8, 10, w - 9, h - 22), radius=4, fill=(0, 0, 0, 0))
    d.ellipse((w // 2 - 4, h - 16, w // 2 + 4, h - 8), fill=(0, 0, 0, 0))
    return ic


def pin_icon(h=44):
    w = int(h * 0.7)
    ic = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ic)
    d.ellipse((0, 0, w - 1, w - 1), fill=YEL)
    d.polygon([(2, w * 0.7), (w - 3, w * 0.7), (w // 2, h - 1)], fill=YEL)
    d.ellipse((w // 2 - 6, w // 2 - 6, w // 2 + 6, w // 2 + 6), fill=(0, 0, 0, 0))
    return ic


def insta_icon(s=40):
    ic = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=11, outline=YEL, width=4)
    d.ellipse((s * 0.28, s * 0.28, s * 0.72, s * 0.72), outline=YEL, width=4)
    d.ellipse((s * 0.70, s * 0.18, s * 0.82, s * 0.30), fill=YEL)
    return ic


def row(layer, icon, tile, gap, cx, y, icon_dy=0):
    total = icon.width + gap + tile.width
    x0 = int(cx - total / 2)
    layer.alpha_composite(icon, (x0, int(y + icon_dy)))
    place(layer, tile, x0 + icon.width + gap + tile.width / 2, y)


def sticker_logo(path, width):
    lg = Image.open(path).convert("RGBA")
    # يشيل بقايا الخط الرفيع أسفل الشعار: تحت مستوى ذيل الـV نمسح كل شي بعيد عن محوره
    import numpy as np
    arr = np.array(lg)
    op = arr[:, :, 3] > 128
    h = arr.shape[0]
    rows = op.any(axis=1)
    y = h - 1
    while y >= 0 and not rows[y]:
        y -= 1
    while y >= 0 and rows[y]:
        y -= 1
    start = y + 1  # بداية آخر كتلة صفوف من تحت
    if start > 0 and rows[:start].any():  # بينها وبين الشعار فراغ = بقايا خط
        arr[start:, :, 3] = 0
    lg = Image.fromarray(arr)
    lg = lg.crop(lg.getbbox())
    lg = lg.resize((width, int(lg.height * width / lg.width)), Image.LANCZOS)
    pad = 28
    base = Image.new("RGBA", (lg.width + 2 * pad, lg.height + 2 * pad), (0, 0, 0, 0))
    base.alpha_composite(lg, (pad, pad))
    a = base.getchannel("A").filter(ImageFilter.MaxFilter(25))
    white = Image.new("RGBA", base.size, (255, 255, 255, 255))
    white.putalpha(a)
    white.alpha_composite(base)
    return white


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--address", required=True)
    ap.add_argument("--handle", default="repair_painting_cars")
    ap.add_argument("--headline", default="BOOK YOUR REPAIR TODAY")
    ap.add_argument("--sub", default="USA IMPORTS  ·  BODY REPAIR  ·  PAINT")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cx = W / 2

    L = blank(); place(L, sticker_logo(a.logo, 700), cx, 290); L.save(f"{a.out}/ec_logo.png")
    L = blank(); place(L, text_tile(a.headline, 100, WHITE, target_w=830, stroke=4), cx, 830); L.save(f"{a.out}/ec_head.png")
    L = blank(); place(L, text_tile(a.sub, 40, YEL, target_w=836, spacing=7), cx, 965); L.save(f"{a.out}/ec_sub.png")
    L = blank(); d = ImageDraw.Draw(L); d.rectangle((122, 1030, 958, 1034), fill=YEL); L.save(f"{a.out}/ec_line.png")
    L = blank(); row(L, phone_icon(), text_tile(a.phone, 150, YEL, target_w=470, stroke=5), 38, cx, 1075, icon_dy=8); L.save(f"{a.out}/ec_phone.png")
    addr = text_tile(a.address, 36, WHITE, raqm=True)
    if addr.width > 760:
        addr = addr.resize((760, addr.height), Image.LANCZOS)
    L = blank(); row(L, pin_icon(), addr, 22, cx, 1235); L.save(f"{a.out}/ec_addr.png")
    L = blank(); row(L, insta_icon(), text_tile("@" + a.handle, 40, WHITE), 20, cx, 1335); L.save(f"{a.out}/ec_handle.png")
    print("layers:", sorted(os.listdir(a.out)))


if __name__ == "__main__":
    main()
