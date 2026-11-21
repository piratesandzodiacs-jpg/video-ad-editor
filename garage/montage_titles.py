#!/usr/bin/env python3
"""مونتاج 4K بعناوين على ستايل فيديو المستخدم (الديفندر):
سطر صغير أبيض (Poppins Bold) يطلع أول، وبعده بـ0.28 ث الكلمة الكبيرة (Anton) تدخل بفيد وتهدأ من تكبير 10٪.
الكلمة بيضاء أو حمراء مع ظل ناعم، والعنوان يبقى لين نهاية مشهده ثم يروح مع القطع.

الاستخدام:
  bash garage/get_fonts.sh <fonts>            # مرة وحدة
  python3 garage/endcard.py --out <ec> ...     # طبقات كرت النهاية
  python3 garage/montage_titles.py --clips <clips> --ec <ec> --fonts <fonts> --out out.mp4
تعديل المقاطع والعناوين من الثوابت CLIPS / CUTS / TITLES تحت.
"""
import argparse, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

K = 2  # 2 = 4K (2160x3840)
W, H = 1080 * K, 1920 * K
RED = (228, 30, 36)
WHITE = (255, 255, 255)

# (ملف، بداية القص ث، المدة ث) بترتيب المشاهد
CLIPS = [("IMG_6158.mov", 0.0, 2.6), ("IMG_6158.mov", 2.6, 2.95), ("IMG_5812.mov", 2.0, 3.35),
         ("IMG_6150.mov", 1.0, 3.35), ("IMG_6155.mov", 8.0, 3.35), ("IMG_5824.mov", 2.5, 2.85)]
CUTS = [2.4, 5.0, 8.0, 11.0, 14.0]  # حدود المشاهد (دمج ناعم 0.25 ث مركّز على كل حد)
CUT_END = 16.6                       # نهاية الجزء الرئيسي، بعده كرت النهاية
TOTAL = 20.0
# (السطر الصغير، الكلمة الكبيرة، لونها، بداية، نهاية)
TITLES = [("THEY SAID IT COULDN’T BE", "REPAIRED.", RED, 0.2, 2.3),
          ("STEP 1", "INSPECT", WHITE, 2.6, 4.9),
          ("STEP 2", "REPAIR", RED, 5.2, 7.9),
          ("STEP 3", "PAINT", WHITE, 8.2, 10.9),
          ("THE RESULT", "DONE RIGHT.", RED, 11.2, 13.9),
          ("ONE SIGN.", "ONE GARAGE.", RED, 14.3, 16.6)]

LABEL_Y, WORD_TOP = 575 * K, 660 * K   # مكان العنوان (الثلث العلوي، مثل المرجع)
MAX_WORD_W = 940 * K


def tile(img_font, text, fill, stretch=1.0, shadow=False):
    f = img_font
    l, t, r, b = f.getbbox(text)
    pad = 40 * K
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), text, font=f, fill=fill + (255,))
    im = im.crop(im.getbbox())
    if stretch != 1.0:
        im = im.resize((int(im.width * stretch), im.height), Image.LANCZOS)
    if shadow:
        sp = 30 * K
        out = Image.new("RGBA", (im.width + 2 * sp, im.height + 2 * sp), (0, 0, 0, 0))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 150))
        sh.putalpha(im.getchannel("A").point(lambda v: v * 150 // 255))
        out.alpha_composite(sh, (sp + 6 * K, sp + 9 * K))
        out = out.filter(ImageFilter.GaussianBlur(9 * K))
        out.alpha_composite(im, (sp, sp))
        return out
    return im


def make_titles(fonts, tmp):
    items = []
    for i, (label, word, color, s, e) in enumerate(TITLES):
        fl = ImageFont.truetype(f"{fonts}/Poppins-Bold.ttf", 62 * K)
        lt = tile(fl, label, WHITE, shadow=True)
        size = 310 * K
        while True:
            fw = ImageFont.truetype(f"{fonts}/Anton.ttf", size)
            wt = tile(fw, word, color, stretch=1.12, shadow=True)
            if wt.width <= MAX_WORD_W + 60 * K or size < 120 * K:
                break
            size -= 8 * K
        lp, wp = f"{tmp}/t{i}_label.png", f"{tmp}/t{i}_word.png"
        lt.save(lp); wt.save(wp)
        wcy = WORD_TOP + (wt.height - 60 * K) // 2
        items.append((lp, wp, s, e, wcy))
    return items


def run(cmd):
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True); ap.add_argument("--ec", required=True)
    ap.add_argument("--fonts", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    items = make_titles(a.fonts, tmp)

    # أطوال المشاهد: كل دمج 0.25 ث مركّز على الحد
    d = 0.25
    offs = [c - d / 2 for c in CUTS]
    lens = [offs[0] + d] + [offs[i] - offs[i - 1] + d for i in range(1, len(offs))] + [CUT_END - offs[-1]]

    inputs, g = [], []
    for i, (f, ss, dur) in enumerate(CLIPS):
        inputs += ["-ss", str(ss), "-t", f"{dur}", "-i", f"{a.clips}/{f}"]
        g.append(f"[{i}:v]fps=30,scale={1166*K}:-2,crop={1080*K}:{1920*K}:'(iw-ow)*t/{dur}':'(ih-oh)/2',"
                 f"eq=contrast=1.08:saturation=1.12,vignette=PI/5,setsar=1,format=yuv420p[c{i}]")
    prev = "c0"
    for i in range(1, len(CLIPS)):
        g.append(f"[{prev}][c{i}]xfade=transition=fade:duration={d}:offset={offs[i-1]:.3f}[x{i}]")
        prev = f"x{i}"
    n = len(CLIPS)
    for j, (lp, wp, s, e, wcy) in enumerate(items):
        ln, wn = n + 2 * j, n + 2 * j + 1
        hold = e - s + 0.6
        inputs += ["-itsoffset", f"{s}", "-loop", "1", "-framerate", "30", "-t", f"{hold}", "-i", lp,
                   "-itsoffset", f"{s + 0.28}", "-loop", "1", "-framerate", "30", "-t", f"{hold}", "-i", wp]
        s2 = s + 0.28
        g.append(f"[{ln}:v]format=rgba,fade=t=in:st={s}:d=0.18:alpha=1[ln{j}]")
        g.append(f"[{wn}:v]format=rgba,scale=w='trunc(iw*(1+0.10*max(0,1-(t-{s2})/0.25))/2)*2':h=-2:eval=frame,"
                 f"fade=t=in:st={s2}:d=0.2:alpha=1[wn{j}]")
        g.append(f"[{prev}][ln{j}]overlay=x='(W-w)/2':y='{LABEL_Y}-h/2':enable='between(t,{s},{e})'[a{j}]")
        g.append(f"[a{j}][wn{j}]overlay=x='(W-w)/2':y='{wcy}-h/2':enable='between(t,{s2},{e})'[b{j}]")
        prev = f"b{j}"
    g[-1] = g[-1].rsplit("[", 1)[0] + "[v]"
    main_mp4 = f"{tmp}/main.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inputs +
        ["-filter_complex", ";".join(g), "-map", "[v]", "-t", str(CUT_END), "-an", "-c:v", "libx264",
         "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", main_mp4])

    # كرت النهاية: خلفية متغبشة من لقطة النتيجة + طبقات endcard.py بالتتابع
    le = round(TOTAL - CUT_END + 0.3, 3); off = round(CUT_END - 0.3, 3)
    layers = [("logo", 0.35), ("head", 0.8), ("sub", 1.0), ("line", 1.15), ("phone", 1.35), ("addr", 1.6), ("handle", 1.85)]
    inp = ["-i", main_mp4, "-ss", "8", "-t", str(le), "-i", f"{a.clips}/{CLIPS[4][0]}"]
    for name, _ in layers:
        inp += ["-loop", "1", "-framerate", "30", "-t", str(le), "-i", f"{a.ec}/ec_{name}.png"]
    g = [f"[0:v]trim=duration={CUT_END},setpts=PTS-STARTPTS,fps=30,format=yuv420p,setsar=1[m]",
         f"[1:v]fps=30,scale={W}:{H},gblur=sigma={30*K},eq=brightness=-0.15:saturation=0.85,vignette=PI/4,"
         f"trim=duration={le},setpts=PTS-STARTPTS,format=yuv420p[bg]"]
    for i, (name, st) in enumerate(layers):
        g.append(f"[{i+2}:v]scale={W}:{H}:flags=lanczos,format=rgba,fade=t=in:st={st}:d=0.35:alpha=1[l{i}]")
    cur = "bg"
    for i, (name, st) in enumerate(layers):
        if name == "logo":
            y = f"if(lt(t,{st+0.45}),-{90*K}*(1-(t-{st})/0.45),0)"
        else:
            y = f"if(lt(t,{st+0.35}),{50*K}*(1-(t-{st})/0.35),0)"
        g.append(f"[{cur}][l{i}]overlay=y='{y}'[e{i}]")
        cur = f"e{i}"
    g.append(f"[m][{cur}]xfade=transition=fade:duration=0.3:offset={off},format=yuv420p[v]")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inp +
        ["-filter_complex", ";".join(g), "-map", "[v]", "-t", str(TOTAL), "-an", "-c:v", "libx264",
         "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out])
    print("تم:", a.out)


if __name__ == "__main__":
    main()
