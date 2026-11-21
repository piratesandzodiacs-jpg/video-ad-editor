#!/usr/bin/env python3
"""يغطي لوحات أرقام السيارات بلوحة الكراج، ملتصقة بالسيارة (تتبّع مستوي بأربع زوايا).

الطريقة:
  1) زوايا اللوحة بأول فريم: من البقعة الصفراء حول مربع تقريبي تعطيه (x0,y0,x1,y1) بإحداثيات 1080x1920.
  2) التتبّع: نقاط ميزة حول اللوحة (LK optical flow) + homography بـRANSAC كل فريم، فالزوايا الأربع
     تتحرك بمنظور مع الكاميرا والسيارة (مو مربع طافي).
  3) الرسم: لوحتك (garage/assets/plate_cover.png) تتحوّل بالمنظور على الرباعي بدقة 4K،
     وتنزل عليها: إضاءة تتبع سطوع المنطقة حول اللوحة، نعومة، وحبيبات مثل اللقطة.
  حدود: ما يعالج حجب يد أو أداة قدام اللوحة. راجع صور المعاينة بعينك.

  pip install opencv-python-headless numpy
  python3 garage/plates.py --config garage/reels/tour.json --clips <مقاطع> --out <مجلد>
  (يقرأ "plates": {"IMG_x.mov": [x0,y0,x1,y1]} ويطلع plate_<رقم المقطع>.mov و preview_<رقم>.png)
"""
import argparse, json, os, subprocess
import cv2
import numpy as np

W, H = 1080, 1920
K = 2                      # دقة الخرج: 2 = 4K
LO, HI = (8, 90, 100), (36, 255, 255)   # أصفر/برتقالي اللوحة
QPAD = 0.13                # نكبّر الرباعي شوي عشان يغطي حافة اللوحة الأصلية
FEAT_SCALE = 1.35          # نقاط الميزة داخل رباعي أكبر بـ35٪ (تشمل حافة الصدام حول اللوحة)


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


def order_quad(p):
    p = np.array(p, np.float32).reshape(4, 2)
    c = p.mean(0)
    p = p[np.argsort(np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0]))]   # بترتيب عقارب الساعة (y لتحت)
    i = int(np.argmin(p.sum(1)))                                    # نبدأ من الزاوية العليا اليسرى
    return np.roll(p, -i, axis=0)                                   # tl,tr,br,bl بدون تقاطع


def init_quad(bgr, seed):
    """زوايا اللوحة من أكبر بقعة صفراء حول المربع التقريبي."""
    x0, y0, x1, y1 = seed
    e = 60
    X0, Y0, X1, Y1 = max(0, x0 - e), max(0, y0 - e), min(W, x1 + e), min(H, y1 + e)
    m = cv2.inRange(cv2.cvtColor(bgr[Y0:Y1, X0:X1], cv2.COLOR_BGR2HSV), LO, HI)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise SystemExit(f"ما لقيت بقعة صفراء حول {seed}")
    best = max(cnts, key=cv2.contourArea)
    hull = cv2.convexHull(best)
    per = cv2.arcLength(hull, True)
    quad = None
    for eps in (0.02, 0.03, 0.04, 0.06, 0.08, 0.1):
        ap = cv2.approxPolyDP(hull, eps * per, True)
        if len(ap) == 4:
            quad = ap.reshape(4, 2).astype(np.float32); break
    if quad is None or cv2.contourArea(quad.astype(np.float32)) < 0.93 * cv2.contourArea(hull):
        quad = cv2.boxPoints(cv2.minAreaRect(best))   # التقريب بـ4 نقاط قصّ جزء من اللوحة
    q = order_quad(quad + np.array([X0, Y0], np.float32))
    # اللوحة المائلة: نخلّي عرض الخامة على الضلع الأطول، والنص يطلع من تحت لفوق مو مقلوب
    wd = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    ht = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    if wd < ht:
        a, b = np.roll(q, -1, axis=0), np.roll(q, 1, axis=0)
        up = lambda z: ((z[0] - z[3]) + (z[1] - z[2]))[1]       # y سالب = الأعلى يشير لفوق
        q = a if up(a) < up(b) else b
    return q


def scaled(q, s):
    c = q.mean(0)
    return c + (q - c) * s


def poly_mask(shape, q):
    m = np.zeros(shape, np.uint8)
    cv2.fillConvexPoly(m, q.astype(np.int32), 255)
    return m


def feats(gray, quad):
    pts = cv2.goodFeaturesToTrack(gray, maxCorners=150, qualityLevel=0.008, minDistance=3,
                                  mask=poly_mask(gray.shape, scaled(quad, FEAT_SCALE)), blockSize=5)
    return pts if pts is not None else np.zeros((0, 1, 2), np.float32)


def ring_luma(gray, quad):
    outer = poly_mask(gray.shape, scaled(quad, 1.9)); inner = poly_mask(gray.shape, scaled(quad, 1.05))
    ring = (outer > 0) & (inner == 0)
    return float(gray[ring].mean()) if ring.any() else 128.0


def track(src, ss, dur, seed):
    """يرجع (رباعيات N×4×2 بإحداثيات 1080x1920، معاملات إضاءة N)."""
    quads, gains = [], []
    prev, quad, pts, l0 = None, None, None, 1.0
    lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    for f in frames(src, ss, dur):
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if prev is None:
            quad = init_quad(f, seed); pts = feats(gray, quad); l0 = ring_luma(gray, quad)
        else:
            if len(pts) >= 6:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **lk)
                ok = st.ravel() == 1
                if ok.sum() >= 6:
                    Hm, inl = cv2.findHomography(pts[ok], nxt[ok], cv2.RANSAC, 2.0)
                    if Hm is not None and inl is not None and inl.sum() >= 5:
                        q2 = cv2.perspectiveTransform(quad.reshape(1, 4, 2), Hm).reshape(4, 2)
                        a0, a1 = cv2.contourArea(quad), cv2.contourArea(q2.astype(np.float32))
                        if a0 > 0 and 0.7 < a1 / a0 < 1.4:     # يتجاهل قفزة غير منطقية
                            quad = q2.astype(np.float32)
                            pts = nxt[ok][inl.ravel() == 1].reshape(-1, 1, 2)
                        else:
                            pts = nxt[ok].reshape(-1, 1, 2)
            if len(pts) < 20:                                   # نجدد النقاط
                extra = feats(gray, quad)
                pts = np.vstack([pts, extra]) if len(pts) else extra
        gains.append(np.clip(ring_luma(gray, quad) / max(l0, 1.0), 0.8, 1.2))
        quads.append(quad.copy()); prev = gray
    quads = np.array(quads)
    # تنعيم خفيف للزوايا (متوسط 3 فريمات) يمنع الرجفة
    sm = quads.copy()
    for i in range(1, len(quads) - 1):
        sm[i] = (quads[i - 1] + 2 * quads[i] + quads[i + 1]) / 4
    return sm, np.array(gains)


def build_texture(quad0, banner, k=K):
    """لوحة الكراج بنسبة اللوحة الأصلية: خلفية داكنة + إطار + صورتك (عريضة أو مكدّسة)."""
    q = scaled(quad0, 1 + QPAD) * k
    wd = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    ht = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    asp = max(0.25, wd / max(ht, 1))
    Wt = int(np.clip(wd * 1.3, 240, 1800)); Ht = max(40, int(Wt / asp))
    tex = np.full((Ht, Wt, 3), 14, np.uint8)
    bh0, bw0 = banner.shape[:2]
    mx, my = int(Wt * 0.05), int(Ht * 0.07)
    iw, ih = Wt - 2 * mx, Ht - 2 * my
    left, logo, right = banner[:, :int(bw0 * 0.308)], banner[:, int(bw0 * 0.308):int(bw0 * 0.69)], banner[:, int(bw0 * 0.69):]

    def put(img, x, y, w):
        h = max(2, int(w * img.shape[0] / img.shape[1])); w = max(2, int(w))
        tex[y:y + h, x:x + w] = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        return h

    if asp >= 3.0:                                   # لوحة طويلة: الصورة كلها
        s_ = min(iw / bw0, ih / bh0)
        w, h = int(bw0 * s_), int(bh0 * s_)
        put(banner, (Wt - w) // 2, (Ht - h) // 2, w)
    elif asp >= 1.1:                                 # لوحة متوسطة: الشعار فوق، واللوحتين النصيتين جنب بعض تحته
        txt = np.hstack([cv2.resize(left, (int(left.shape[1] * bh0 / left.shape[0]), bh0)),
                         cv2.resize(right, (int(right.shape[1] * bh0 / right.shape[0]), bh0))])
        ia = logo.shape[0] / logo.shape[1] + txt.shape[0] / txt.shape[1]      # مجموع (ارتفاع/عرض)
        w = int(min(iw, ih / ia))
        y = (Ht - int(w * ia)) // 2
        y += put(logo, (Wt - w) // 2, y, w)
        put(txt, (Wt - w) // 2, y, w)
    else:                                            # لوحة مربعة أو طويلة بالعمودي: ثلاثة أجزاء مكدّسة
        parts = [logo, left, right]
        inv = sum(p.shape[0] / p.shape[1] for p in parts)
        w = int(min(iw, ih / inv))
        y = (Ht - int(w * inv)) // 2
        for part in parts:
            y += put(part, (Wt - w) // 2, y, w)
    bt = max(2, int(Ht * 0.035))
    cv2.rectangle(tex, (0, 0), (Wt - 1, Ht - 1), (88, 88, 88), bt)          # إطار اللوحة
    alpha = np.zeros((Ht, Wt), np.uint8)
    cv2.rectangle(alpha, (0, 0), (Wt - 1, Ht - 1), 255, -1)
    r = max(3, int(Ht * 0.08))
    for (cx, cy) in ((0, 0), (Wt - 1, 0), (0, Ht - 1), (Wt - 1, Ht - 1)):  # زوايا مدوّرة
        pass
    mask = np.zeros((Ht, Wt), np.uint8)
    cv2.rectangle(mask, (r, 0), (Wt - 1 - r, Ht - 1), 255, -1); cv2.rectangle(mask, (0, r), (Wt - 1, Ht - 1 - r), 255, -1)
    for (cx, cy) in ((r, r), (Wt - 1 - r, r), (r, Ht - 1 - r), (Wt - 1 - r, Ht - 1 - r)):
        cv2.circle(mask, (cx, cy), r, 255, -1)
    return np.dstack([tex, mask])


def render(quads, gains, banner, path, k=K):
    OW, OH = W * k, H * k
    tex = build_texture(quads[0], banner, k)
    Ht, Wt = tex.shape[:2]
    src = np.array([[0, 0], [Wt, 0], [Wt, Ht], [0, Ht]], np.float32)
    rng = np.random.default_rng(7)
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{OW}x{OH}", "-r", "30",
                          "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", path], stdin=subprocess.PIPE)
    for q, g in zip(quads, gains):
        qq = (scaled(q, 1 + QPAD) * k).astype(np.float32)
        x0, y0 = int(max(0, np.floor(qq[:, 0].min()) - 8)), int(max(0, np.floor(qq[:, 1].min()) - 8))
        x1, y1 = int(min(OW, np.ceil(qq[:, 0].max()) + 8)), int(min(OH, np.ceil(qq[:, 1].max()) + 8))
        fr = np.zeros((OH, OW, 4), np.uint8)
        if x1 - x0 > 6 and y1 - y0 > 6:
            M = cv2.getPerspectiveTransform(src, qq - np.array([x0, y0], np.float32))
            w = cv2.warpPerspective(tex, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            rgb = w[:, :, :3].astype(np.float32) * float(g) * 0.93          # إضاءة المشهد، وبياض مو ناصع
            rgb += rng.normal(0, 2.0, rgb.shape).astype(np.float32)          # حبيبات تشبه اللقطة
            w[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
            w = cv2.GaussianBlur(w, (0, 0), 0.8)                             # نعومة مثل عدسة الآيفون
            fr[y0:y1, x0:x1] = w
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()


def preview(src, ss, dur, quads, path):
    fr = list(frames(src, ss, dur)); idx = np.linspace(0, len(fr) - 1, 5).astype(int)
    c = quads[0].mean(0); r = 230
    tiles = []
    for i in idx:
        f = fr[i].copy(); q = quads[i]
        cv2.polylines(f, [q.astype(np.int32)], True, (0, 255, 0), 3)
        cx, cy = q.mean(0)
        x0, y0 = int(np.clip(cx - r, 0, W - 2 * r)), int(np.clip(cy - r, 0, H - 2 * r))
        tiles.append(cv2.resize(f[y0:y0 + 2 * r, x0:x0 + 2 * r], (240, 240), interpolation=cv2.INTER_AREA))
    cv2.imwrite(path, np.hstack(tiles))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--clips", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--banner", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plate_cover.png"))
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8")); os.makedirs(a.out, exist_ok=True)
    banner = cv2.imread(a.banner, cv2.IMREAD_COLOR)
    for i, (f, ss, dur) in enumerate(cfg["clips"]):
        seed = cfg.get("plates", {}).get(f)
        if not seed:
            continue
        quads, gains = track(f"{a.clips}/{f}", ss, dur, seed)
        render(quads, gains, banner, f"{a.out}/plate_{i}.mov")
        preview(f"{a.clips}/{f}", ss, dur, quads, f"{a.out}/preview_{i}.png")
        print(f"مقطع {i} ({f}): {len(quads)} فريم، إضاءة {gains.min():.2f}-{gains.max():.2f}")


if __name__ == "__main__":
    main()
