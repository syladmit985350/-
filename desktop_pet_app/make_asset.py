from collections import deque
from pathlib import Path
from PIL import Image
import numpy as np

src = Path('/mnt/data/image(2).png')
out = Path('/mnt/data/desktop_pet_app/assets/pet.png')
orig_out = Path('/mnt/data/desktop_pet_app/assets/pet_original.png')
img = Image.open(src).convert('RGBA')
img.save(orig_out)
arr = np.array(img)
rgb = arr[:, :, :3]
h, w = rgb.shape[:2]
# Only remove near-white pixels connected to image edges, so white clothes/highlights stay intact.
near_white = (rgb[:, :, 0] > 238) & (rgb[:, :, 1] > 238) & (rgb[:, :, 2] > 238)
visited = np.zeros((h, w), dtype=bool)
q = deque()
for x in range(w):
    if near_white[0, x]:
        visited[0, x] = True; q.append((0, x))
    if near_white[h-1, x]:
        visited[h-1, x] = True; q.append((h-1, x))
for y in range(h):
    if near_white[y, 0] and not visited[y, 0]:
        visited[y, 0] = True; q.append((y, 0))
    if near_white[y, w-1] and not visited[y, w-1]:
        visited[y, w-1] = True; q.append((y, w-1))

while q:
    y, x = q.popleft()
    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < h and 0 <= nx < w and (not visited[ny, nx]) and near_white[ny, nx]:
            visited[ny, nx] = True
            q.append((ny, nx))

arr2 = arr.copy()
# Transparent background
arr2[visited, 3] = 0
# Reduce bright edge fringe only where it is connected to the background.
# Use a small crop around the non-transparent part to reduce window texture size.
ys, xs = np.where(arr2[:, :, 3] > 0)
if len(xs) and len(ys):
    pad = 14
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, w)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, h)
    arr2 = arr2[y0:y1, x0:x1]

# Save reasonably sized pet asset while keeping detail.
out_img = Image.fromarray(arr2, 'RGBA')
# Resize longest side to 720 px for lighter runtime drawing.
longest = max(out_img.size)
if longest > 720:
    scale = 720 / longest
    out_img = out_img.resize((int(out_img.width * scale), int(out_img.height * scale)), Image.LANCZOS)
out_img.save(out)
print(out, out_img.size)
