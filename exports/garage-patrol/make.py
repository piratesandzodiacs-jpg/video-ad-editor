"""Garage reel: 3D sticker intro + top-right banner + short English text + plate cover.

Edit the CONFIG block to change text, timing, or the plate image.
"""
import os, sys, json, math, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
# ------------------------------- CONFIG -------------------------------------
SRC = '/root/.claude/uploads/46322b08-ba23-5045-b031-91dfb8e7d2b5/1da78717-1795368304943158.mp4'
STICKER = os.path.join(HERE, 'nissan_sticker.png')   # car logo: spins in, then sits top-right
BANNER = os.path.join(HERE, 'garage-banner.jpg')     # garage logo: goes on the number plate
PLATE_IMG = os.path.join(HERE, 'plate_cover.png')   # replace this file to change the plate cover
PLATE_TRACK = os.path.join(HERE, 'plate.json')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out.mp4')
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf'
FONT2 = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
GOLD = (242, 184, 32)
WHITE = (255, 255, 255)
TEXTS = [  # start, end, text, size, color, y (center, on 1080x1920)
    (2.25, 4.55, 'PREMIUM AUTO GARAGE', 76, WHITE, 1560),
    (2.45, 4.55, 'TRD GARAGE', 48, GOLD, 1640),
]
INTRO_END = 2.05      # car logo lands top-right by this time
CORNER_W = 230        # car logo width in the top-right corner (px)
# ----------------------------------------------------------------------------

W, H, FPS = 1080, 1920, 30
SW, SH, SFPS = 1512, 2688, 50
N_SRC = 343
DUR = N_SRC / SFPS
N = int(round(DUR * FPS))

# ---------- plate cover ----------
if not os.path.exists(PLATE_IMG):  # build from the garage banner (letterboxed on black)
    pw, ph = 960, 410
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 255))
    bn0 = Image.open(BANNER).convert('RGBA')
    bw = pw - 12; bn0 = bn0.resize((bw, round(bn0.height * bw / bn0.width)), Image.LANCZOS)
    im.alpha_composite(bn0, ((pw - bw) // 2, (ph - bn0.height) // 2))
    im.save(PLATE_IMG)
plate = cv2.cvtColor(np.array(Image.open(PLATE_IMG).convert('RGBA')), cv2.COLOR_RGBA2BGRA)
ptrack = {int(k): np.array(v, np.float32) for k, v in json.load(open(PLATE_TRACK)).items()}

def cover_plate(frame, f):
    if f not in ptrack:
        return frame
    c = ptrack[f].copy()
    # grow 4% so the yellow edge never peeks out
    ctr = c.mean(0); c = ctr + (c - ctr) * 1.04
    ph_, pw_ = plate.shape[:2]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [pw_, 0], [pw_, ph_], [0, ph_]]), c)
    wp = cv2.warpPerspective(plate, M, (SW, SH), flags=cv2.INTER_LINEAR)
    a = wp[:, :, 3:4].astype(np.float32) / 255
    return (wp[:, :, :3] * a + frame * (1 - a)).astype(np.uint8)


# ---------- 3D sticker renderer ----------
s = cv2.imread(STICKER, cv2.IMREAD_UNCHANGED)[:, :, [2, 1, 0, 3]].astype(np.float32) / 255
k = 640 / s.shape[1]
s = cv2.resize(s, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
sh, sw = s.shape[:2]
A = s[:, :, 3:4]
face = np.concatenate([s[:, :, :3] * A, A], 2)
BCX = W - 36 - CORNER_W / 2
BCY = 70 + CORNER_W * sh / sw / 2
yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
diag = (xx + 0.55 * yy) / (sw + 0.55 * sh)
FOC, THICK, LAYERS = 1500.0, 18.0, 14

def ease(u):
    u = min(max(u, 0.0), 1.0); return u * u * u * (u * (u * 6 - 15) + 10)

def back_out(u):
    u = min(max(u, 0.0), 1.0); c = 1.70158; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2

def sticker_pose(t):
    th = 2 * math.pi * ease((t - 0.15) / 1.30)
    tilt = math.radians(8) * math.sin(2 * math.pi * t / 2.0)
    sc = back_out(t / 0.38)
    cx, cy = W / 2, 820.0
    u = ease((t - 1.75) / (INTRO_END - 1.75))
    sc *= 1 - u * (1 - CORNER_W / sw)      # shrink to corner size
    cx += (BCX - cx) * u; cy += (BCY - cy) * u
    fade = 1.0
    shine = (t - 1.45) / 0.35 if 1.45 <= t <= 1.80 else -1
    return th, tilt, sc, cx, cy, fade, shine

def project(pts, th, tilt, sc, cx, cy):
    c_, s_ = math.cos(th), math.sin(th); ct, st = math.cos(tilt), math.sin(tilt)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    x1 = c_ * x + s_ * z; z1 = -s_ * x + c_ * z
    y2 = ct * y - st * z1; z2 = st * y + ct * z1
    zc = FOC + z2
    return np.stack([cx + sc * FOC * x1 / zc, cy + sc * FOC * y2 / zc], 1).astype(np.float32), zc

def warp(tex, pose, z, flip=False):
    th, tilt, sc, cx, cy = pose
    hw, hh = sw / 2, sh / 2
    obj = np.array([[-hw, -hh, z], [hw, -hh, z], [hw, hh, z], [-hw, hh, z]], np.float32)
    dst, zc = project(obj, th, tilt, sc, cx, cy)
    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    if flip: src = src[[1, 0, 3, 2]]
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(tex, M, (W, H), flags=cv2.INTER_LINEAR), zc.mean()

def render_sticker(t):
    th, tilt, sc, cx, cy, fade, shine = sticker_pose(t)
    if sc <= 0.01 or fade <= 0: return None
    pose = (th, tilt, sc, cx, cy)
    c = math.cos(th); side = abs(math.sin(th))
    rim = np.array([0.62, 0.63, 0.66]) * (0.55 + 0.45 * side)
    layers = []
    for i in range(LAYERS):
        z = -THICK / 2 + THICK * i / (LAYERS - 1)
        shade = (rim * (0.85 + 0.15 * i / (LAYERS - 1))).astype(np.float32)
        layers.append((z, np.concatenate([A * shade, A], 2), False))
    ft = face.copy(); ft[:, :, :3] *= 0.80 + 0.20 * abs(c)
    if shine >= 0:
        band = np.exp(-((diag - (-0.25 + 1.5 * shine)) / 0.06) ** 2) * 0.55 * A[:, :, 0]
        ft[:, :, :3] += band[..., None] * (1 - ft[:, :, :3])
    layers.append((-THICK / 2 - 0.01, ft, False) if c > 0 else (THICK / 2 + 0.01, ft, True))
    rs = sorted((warp(tex, pose, z, fl) for z, tex, fl in layers), key=lambda r: -r[1])
    acc = np.zeros((H, W, 4), np.float32)
    for img, _ in rs:
        acc = img + acc * (1 - img[:, :, 3:4])
    return acc * fade

def sticker_layer(t, sub=5):
    accs = [render_sticker(t + (i - (sub - 1) / 2) / sub * 0.5 / FPS) for i in range(sub)]
    accs = [a for a in accs if a is not None]
    if not accs: return None
    return sum(accs) / sub

# ---------- text ----------
fonts = {}
def text_layer(t):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); any_ = False
    for (a, b, txt, size, col, y) in TEXTS:
        if not (a <= t <= b): continue
        any_ = True
        u = ease((t - a) / 0.35); o = min(u, ease((b - t) / 0.2) if b < DUR - 0.05 else 1)
        f = fonts.setdefault((size, col == WHITE), ImageFont.truetype(FONT if col == WHITE else FONT2, size))
        yy_ = y + (1 - u) * 30
        sh_ = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh_).text((W / 2, yy_ + 3), txt, font=f, fill=(0, 0, 0, int(200 * o)), anchor='mm')
        img.alpha_composite(sh_.filter(ImageFilter.GaussianBlur(6)))
        ImageDraw.Draw(img).text((W / 2, yy_), txt, font=f, fill=col + (int(255 * o),), anchor='mm')
    return np.array(img).astype(np.float32) / 255 if any_ else None

grad = np.clip((np.arange(H) - 1300) / 620, 0, 1)[:, None, None] ** 1.3 * 0.62

# ---------- main loop ----------
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
_cache = {'i': -1, 'f': None}
def get_src(f):
    while _cache['i'] < f:
        buf = dec.stdout.read(SW * SH * 3)
        if len(buf) < SW * SH * 3: break
        _cache['f'] = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3); _cache['i'] += 1
    return _cache['f']
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                        '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
for i in range(N):
    t = i / FPS
    f = min(int(round(t * SFPS)), N_SRC - 1)
    fr = cover_plate(get_src(f).astype(np.float32), f).astype(np.uint8)
    fr = cv2.resize(fr, (W, H), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32) / 255
    dim = 0.38 * (1 - ease((t - 1.7) / 0.4))          # darken behind the intro sticker
    fr *= 1 - dim
    fr *= 1 - grad * (1 if 2.0 < t < 4.6 else 0)    # bottom shade behind text
    if t < INTRO_END:
        st = sticker_layer(t)
    else:
        if 'corner' not in globals(): corner = render_sticker(INTRO_END)
        st = corner
    if st is not None:
        fr = st[:, :, :3] + fr * (1 - st[:, :, 3:4])
    tl = text_layer(t)
    if tl is not None:
        fr = tl[:, :, :3] * tl[:, :, 3:4] + fr * (1 - tl[:, :, 3:4])
    enc.stdin.write((np.clip(fr, 0, 1) * 255).astype(np.uint8).tobytes())
    if i % 30 == 0: print(i, flush=True)
enc.stdin.close(); enc.wait()
print('done', OUT)
