"""Lock onto a yellow number plate by finding its edges every frame (no drift).
usage: yellow_lock.py video W H F0 F1 rough.json out.json
"""
import sys, json, subprocess, numpy as np, cv2

V, W, H, F0, F1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
rough = {int(k): np.array(v, np.float32) for k, v in json.load(open(sys.argv[6])).items()}
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', V, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                     capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def order(p):
    s = p.sum(1); d = p[:, 0] - p[:, 1]
    return np.float32([p[np.argmin(s)], p[np.argmax(d)], p[np.argmax(s)], p[np.argmin(d)]])  # TL TR BR BL


def quad_from_mask(m):
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts: return None
    c = max(cnts, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    per = cv2.arcLength(hull, True)
    for eps in np.linspace(0.005, 0.08, 40):
        ap = cv2.approxPolyDP(hull, eps * per, True)
        if len(ap) == 4: break
    else:
        return None
    q = order(ap[:, 0, :].astype(np.float32))
    # refine each side with a least-squares line through the hull points near it
    pts = c[:, 0, :].astype(np.float32)
    lines = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        ab = b - a; L = np.linalg.norm(ab); n = np.array([-ab[1], ab[0]]) / L
        t = ((pts - a) @ ab) / L ** 2
        dist = np.abs((pts - a) @ n)
        sel = pts[(t > 0.12) & (t < 0.88) & (dist < 6)]
        if len(sel) < 10: lines.append((a, ab / L)); continue
        vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))
    out = []
    for i in range(4):  # corner i = intersection of side i-1 and side i
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        A = np.array([d1, -d2]).T
        try:
            s_ = np.linalg.solve(A.astype(np.float64), (p2 - p1).astype(np.float64)); out.append(p1 + s_[0] * d1)
        except np.linalg.LinAlgError:
            out.append(q[i])
    return np.float32(out)


res, bad = {}, 0
for f in range(F0, F1 + 1):
    r = rough[f]
    x0, y0 = np.maximum(np.floor(r.min(0) - 60), 0).astype(int)
    x1, y1 = np.minimum(np.ceil(r.max(0) + 60), [W, H]).astype(int)
    roi = fr[f][y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (12, 90, 90), (40, 255, 255))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    q = quad_from_mask(m)
    ok = q is not None
    if ok:
        q = (q + [x0, y0]).astype(np.float32)
        area = cv2.contourArea(q); ra = cv2.contourArea(r)
        if not (0.7 < area / ra < 1.4) or np.abs(q - r).max() > 40: ok = False
    if not ok:
        bad += 1; q = None
    res[f] = q
# fill gaps by carrying the last good offset from the rough track
keys = list(range(F0, F1 + 1)); last = np.zeros((4, 2), np.float32)
arr = []
for f in keys:
    if res[f] is not None: last = res[f] - rough[f]; arr.append(res[f])
    else: arr.append(rough[f] + last)
arr = np.array(arr)
# temporal smoothing: 5-tap, keeps it glued but removes edge-detection flicker
k = np.array([1, 4, 6, 4, 1], np.float32)
sm = arr.copy()
for i in range(len(arr)):
    lo, hi = max(i - 2, 0), min(i + 3, len(arr)); w = k[2 - (i - lo):2 + (hi - i)]
    sm[i] = (arr[lo:hi] * w[:, None, None]).sum(0) / w.sum()
json.dump({str(f): sm[i].tolist() for i, f in enumerate(keys)}, open(sys.argv[7], 'w'))
jit = np.abs(np.diff(arr - sm, axis=0)).max()
print(f'frames {len(keys)} missed {bad}  max raw-vs-smoothed wiggle {jit:.1f}px')
