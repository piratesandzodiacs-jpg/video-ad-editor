#!/usr/bin/env python3
"""يغطي لوحات أرقام السيارات بلوحة الكراج (garage/assets/plate_cover.png): تتبّع باللون من مربع بداية تعطيه، ويطلع فيديو RGBA 4K يتركّب فوق المقطع.

الكشف التلقائي الكامل ما نجح (يخلط بين اللوحة والقميص والشريط)، فالطريقة:
  1) تعطي مربع تقريبي للوحة بأول المقطع بإحداثيات 1080x1920 (x0,y0,x1,y1)
  2) السكربت يلحقها بالفريمات بالنطاق الأصفر حولها
  3) يطلع plate_<رقم>.mov لكل مقطع + صورة معاينة بمربعات خضراء، وانت تراجعها بعينك

  pip install opencv-python-headless numpy
  python3 garage/plates.py --config garage/reels/tour.json --clips <مقاطع> --out <مجلد>
  (يقرأ "plates": {"IMG_x.mov": [x0,y0,x1,y1]} من ملف الإعدادات، ويطلع plate_<رقم المقطع>.mov)
"""
import argparse, json, os, subprocess
import cv2
import numpy as np

W, H = 1080, 1920
EXPAND = 150      # نطاق البحث حول المربع السابق
PAD = 0.3         # حشوة حول المربع المتتبَّع (تغطي لو التتبّع تأخر شوي)
LO, HI = (8, 90, 100), (36, 255, 255)


def frames(src, ss, dur, fps=30):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(dur), "-i", src,
           "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = W * H * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
    p.wait()


def blob(bgr, box):
    """أكبر بقعة صفراء داخل نطاق حول box. يرجع (x0,y0,x1,y1) أو None."""
    x0, y0, x1, y1 = box
    X0, Y0 = max(0, int(x0 - EXPAND)), max(0, int(y0 - EXPAND))
    X1, Y1 = min(W, int(x1 + EXPAND)), min(H, int(y1 + EXPAND))
    roi = bgr[Y0:Y1, X0:X1]
    m = cv2.inRange(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), LO, HI)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = max(cnts, key=cv2.contourArea, default=None)
    if best is None or cv2.contourArea(best) < 60:
        return None
    x, y, w, h = cv2.boundingRect(best)
    return X0 + x, Y0 + y, X0 + x + w, Y0 + y + h


def track(src, ss, dur, seed):
    box = np.array(seed, float)
    area0 = (seed[2] - seed[0]) * (seed[3] - seed[1])
    out = []
    for f in frames(src, ss, dur):
        d = blob(f, box)
        if d is not None:
            a = (d[2] - d[0]) * (d[3] - d[1])
            if area0 / 8 < a < area0 * 4:   # يتجاهل بقعة ضخمة (جدار أصفر) أو صغيرة جداً
                box = 0.5 * box + 0.5 * np.array(d, float)
        out.append(tuple(box))
    return out


def padded(b):
    x0, y0, x1, y1 = b
    px, py = (x1 - x0) * PAD, (y1 - y0) * PAD
    return int(max(0, x0 - px)), int(max(0, y0 - py)), int(min(W, x1 + px)), int(min(H, y1 + py))


def write_cover(boxes, banner_path, path, k=2):
    """فيديو RGBA بدقة 4K (k=2): لوحة الكراج تتركّب على كل مربع متتبَّع.
    خلفية سوداء تملأ المربع كله، وصورة اللوحة بالنسبة الأصلية بنص العرض."""
    ban = cv2.imread(banner_path, cv2.IMREAD_COLOR)
    bh0, bw0 = ban.shape[:2]
    OW, OH = W * k, H * k
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{OW}x{OH}", "-r", "30",
                          "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", path], stdin=subprocess.PIPE)
    for b in boxes:
        x0, y0, x1, y1 = [v * k for v in padded(b)]
        fr = np.zeros((OH, OW, 4), np.uint8)
        bw, bh = x1 - x0, y1 - y0
        if bw > 4 and bh > 4:
            fr[y0:y1, x0:x1] = (0, 0, 0, 255)
            s = min(bw * 0.94 / bw0, bh * 0.94 / bh0)
            w, h = max(2, int(bw0 * s)), max(2, int(bh0 * s))
            small = cv2.resize(ban, (w, h), interpolation=cv2.INTER_AREA)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            px, py = cx - w // 2, cy - h // 2
            fr[py:py + h, px:px + w, :3] = small
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()


def preview(src, ss, dur, boxes, path):
    fr = list(frames(src, ss, dur)); idx = np.linspace(0, len(fr) - 1, 5).astype(int)
    tiles = []
    for i in idx:
        f = fr[i].copy(); x0, y0, x1, y1 = padded(boxes[i])
        cv2.rectangle(f, (x0, y0), (x1, y1), (0, 255, 0), 4)
        tiles.append(cv2.resize(f, (270, 480), interpolation=cv2.INTER_AREA))
    cv2.imwrite(path, np.hstack(tiles))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--clips", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--banner", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plate_cover.png"))
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8")); os.makedirs(a.out, exist_ok=True)
    for i, (f, ss, dur) in enumerate(cfg["clips"]):
        seed = cfg.get("plates", {}).get(f)
        if not seed:
            continue
        boxes = track(f"{a.clips}/{f}", ss, dur, seed)
        write_cover(boxes, a.banner, f"{a.out}/plate_{i}.mov")
        preview(f"{a.clips}/{f}", ss, dur, boxes, f"{a.out}/preview_{i}.png")
        print(f"مقطع {i} ({f}): {len(boxes)} فريم")


if __name__ == "__main__":
    main()
