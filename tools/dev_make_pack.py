"""Make a synthetic dev pack (no real images) under docs/packs_dev/packs/ for local testing."""
import json, math, os, random
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "packs_dev", "packs")
CROP = 384
AUTOS = ["pellet_lying", "pellet_standing", "broken", "clump", "debris"]

def make(pid, role, stratum, image_id, n, seed):
    rnd = random.Random(seed)
    d = os.path.join(ROOT, pid)
    os.makedirs(d, exist_ok=True)
    items = []
    for aid in range(10, 10 + n):
        img = Image.new("RGB", (CROP, CROP), (40 + rnd.randint(-8, 8), 70, 150))
        dr = ImageDraw.Draw(img)
        for _ in range(6):  # distractor neighbours
            x, y = rnd.randint(0, CROP), rnd.randint(0, CROP)
            dr.ellipse([x - 30, y - 10, x + 30, y + 10], fill=(150, 100, 50))
        L, W = rnd.randint(40, 70), rnd.randint(18, 28)
        ang = rnd.random() * math.pi
        cx = cy = CROP / 2
        poly = []
        for t in range(24):
            a = 2 * math.pi * t / 24
            x, y = L * math.cos(a), W * math.sin(a)
            poly.append([int(cx + x * math.cos(ang) - y * math.sin(ang)),
                         int(cy + x * math.sin(ang) + y * math.cos(ang))])
        dr.polygon([tuple(p) for p in poly], fill=(190, 130, 60))
        img.save(os.path.join(d, f"{aid}.jpg"), quality=85)
        items.append({"aid": aid, "auto": AUTOS[aid % 5], "check": "all", "unc": aid % 4 == 0 and 1 or 0,
                      "len_mm": round(L / 20, 2), "wid_mm": round(W / 20, 2), "poly": poly})
    json.dump({"id": pid, "image_id": image_id, "role": role, "stratum": stratum, "dpi": 800,
               "crop": CROP, "made": "dev", "items": items}, open(os.path.join(d, "manifest.json"), "w"))
    return {"id": pid, "n": n, "role": role, "stratum": stratum, "image_id": image_id}

idx = [make("gold_dev_a", "gold", "dev/a", "dev_a_0001", 12, 1),
       make("review_dev_b", "review", "dev/b", "dev_b_0002", 12, 2)]
json.dump(idx, open(os.path.join(ROOT, "index.json"), "w"))
print("ok", ROOT)
