import sys, numpy as np, cv2
from scipy import ndimage as ndi
img = cv2.imread(sys.argv[1])[:, :, ::-1].astype(np.float32)
lum = img.mean(2)
bright = lum > 40
lab, n = ndi.label(bright)
sizes = ndi.sum(bright, lab, range(1, n + 1))
bright = np.isin(lab, np.where(sizes > 200)[0] + 1)
inner = ndi.binary_fill_holes(ndi.distance_transform_edt(~bright) < 8)
inner = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 3) > 0.5
sil = ndi.binary_fill_holes(ndi.distance_transform_edt(~inner) < 20)
sil = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 4) > 0.5
ia = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 1.0)[..., None]
sa = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 0.8)
col = img * ia + 255 * (1 - ia)
ys, xs = np.where(sa > 0.01)
y0, y1, x0, x1 = ys.min() - 6, ys.max() + 7, xs.min() - 6, xs.max() + 7
rgba = np.dstack([col, sa * 255]).clip(0, 255).astype(np.uint8)[y0:y1, x0:x1]
cv2.imwrite(sys.argv[2], cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)); print(rgba.shape)
