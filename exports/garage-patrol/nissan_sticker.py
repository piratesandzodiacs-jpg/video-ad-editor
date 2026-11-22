import sys, numpy as np, cv2
from scipy import ndimage as ndi

img = cv2.imread(sys.argv[1])[:, :, ::-1].astype(np.float32)
lum = img.mean(2)
bright = lum > 40
lab, n = ndi.label(bright)
sizes = ndi.sum(bright, lab, range(1, n + 1))
bright = np.isin(lab, np.where(sizes > 200)[0] + 1)
# fill only small holes (letters inside the bar), keep the big ring openings
holes = ndi.binary_fill_holes(bright) & ~bright
hl, hn = ndi.label(holes)
hs = ndi.sum(holes, hl, range(1, hn + 1))
small = np.isin(hl, np.where(hs < 6000)[0] + 1)
logo = bright | small
# soft logo alpha from luminance at edges
a = np.clip((lum - 20) / 40, 0, 1)
a = np.where(logo & ~ndi.binary_erosion(logo, iterations=2), np.maximum(a, 0), 1.0) * ndi.binary_dilation(logo, iterations=1)
a = np.where(small, 1.0, a)
# die-cut white sticker around it
d = ndi.distance_transform_edt(~logo)
sil = ndi.binary_fill_holes(d < 22)
sil = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 5) > 0.5
sa = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 0.8)
white = np.full_like(img, 255)
col = img * a[..., None] + white * (1 - a[..., None])
ys, xs = np.where(sa > 0.01)
y0, y1, x0, x1 = ys.min() - 6, ys.max() + 7, xs.min() - 6, xs.max() + 7
rgba = np.dstack([col, sa * 255]).clip(0, 255).astype(np.uint8)[y0:y1, x0:x1]
cv2.imwrite(sys.argv[2], cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
print(rgba.shape)
