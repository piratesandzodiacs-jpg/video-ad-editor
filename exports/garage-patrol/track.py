"""Track plate corners through the front shot with LK flow + homography."""
import sys, json, subprocess, numpy as np, cv2

V, F0, F1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
corners = np.array(json.loads(sys.argv[4]), np.float32)   # TL TR BR BL at F0
W, H = 1512, 2688
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', V, '-vf', 'format=gray',
                      '-f', 'rawvideo', '-'], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)

def region(c, pad):
    m = np.zeros((H, W), np.uint8)
    x0, y0 = c.min(0) - pad; x1, y1 = c.max(0) + pad
    m[int(max(y0, 0)):int(min(y1, H)), int(max(x0, 0)):int(min(x1, W))] = 255
    return m

out = {F0: corners.tolist()}
cur = corners.copy()
prev = fr[F0]
pts = cv2.goodFeaturesToTrack(prev, 400, 0.01, 8, mask=region(cur, 260))
for f in range(F0 + 1, F1 + 1):
    img = fr[f]
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, img, pts, None, winSize=(31, 31), maxLevel=4)
    back, st2, _ = cv2.calcOpticalFlowPyrLK(img, prev, nxt, None, winSize=(31, 31), maxLevel=4)
    good = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(back - pts, axis=2)[:, 0] < 1.0)
    Hm, inl = cv2.findHomography(pts[good], nxt[good], cv2.RANSAC, 2.0)
    cur = cv2.perspectiveTransform(cur[None], Hm)[0]
    out[f] = cur.tolist()
    prev = img
    if good.sum() < 150 or f % 10 == 0:
        pts = cv2.goodFeaturesToTrack(prev, 400, 0.01, 8, mask=region(cur, 260))
    else:
        pts = nxt[good].reshape(-1, 1, 2)
# light temporal smoothing
keys = sorted(out)
arr = np.array([out[k] for k in keys])
k = np.array([1, 2, 3, 2, 1], np.float32); k /= k.sum()
sm = arr.copy()
for i in range(len(arr)):
    lo, hi = max(i - 2, 0), min(i + 3, len(arr))
    ww = k[2 - (i - lo):2 + (hi - i)]
    sm[i] = (arr[lo:hi] * ww[:, None, None]).sum(0) / ww.sum()
json.dump({str(kk): sm[i].tolist() for i, kk in enumerate(keys)}, open(sys.argv[5], 'w'))
print('tracked', len(keys), 'start', arr[0].round(1).tolist(), 'end', arr[-1].round(1).tolist())
