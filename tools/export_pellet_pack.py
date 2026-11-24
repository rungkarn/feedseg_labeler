#!/usr/bin/env python
"""Export CVAT-review tasks to static per-pellet web packs (run ON LANTA).

    python -I tools/export_pellet_pack.py --site <packs repo clone> [--task gold_asian_2_0019,review_x] [--replace]

Per task writes <site>/packs/<task>/manifest.json + <aid>.jpg and merges <site>/packs/index.json.
Selection: gold = every pellet, review = check != none. Image_ids whose manifest reason starts with
non_feed:document are refused. Crop = square, side S = max(3 * longest bbox side, 96) frame px, centred on
the bbox centre, padded with the frame's median colour, resized to --crop px (INTER_AREA).
Contract: feedseg_labeler/CONTRACT.md.
"""
import argparse
import csv
import gzip
import json
import shutil
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
DATA = "/project/lt200264-saiwat/FeedProject/data/processed/Shrimp"
SRC_DEFAULT = f"{DATA}/cvat_review/v1"
MANIFEST_DEFAULT = f"{DATA}/manifest.csv"


def parse_points(s):
    return np.array([[float(v) for v in p.split(",")] for p in s.split(";")], dtype=np.float32)


def read_unc(zpath):
    """(frame name, auto_id) -> uncertain 0/1 from the CVAT 1.1 XML."""
    out = {}
    with zipfile.ZipFile(zpath) as z:
        root = ET.fromstring(z.read("annotations.xml"))
    for im in root.iter("image"):
        for pg in im.iter("polygon"):
            at = {a.get("name"): (a.text or "") for a in pg.iter("attribute")}
            if "auto_id" in at:
                out[(im.get("name"), int(at["auto_id"]))] = 1 if at.get("uncertain", "").lower() == "true" else 0
    return out


def make_crop(img, pts, med, side_px):
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    s = int(round(max(3 * max(x1 - x0, y1 - y0), 96)))
    ox, oy = int(round(cx - s / 2)), int(round(cy - s / 2))
    buf = np.empty((s, s, 3), np.uint8)
    buf[:] = med
    h, w = img.shape[:2]
    ax0, ay0, ax1, ay1 = max(ox, 0), max(oy, 0), min(ox + s, w), min(oy + s, h)
    if ax1 > ax0 and ay1 > ay0:
        buf[ay0 - oy:ay1 - oy, ax0 - ox:ax1 - ox] = img[ay0:ay1, ax0:ax1]
    k = side_px / s
    crop = cv2.resize(buf, (side_px, side_px), interpolation=cv2.INTER_AREA)
    poly = np.clip(np.rint((pts - [ox, oy]) * k), 0, side_px).astype(int).tolist()
    return crop, poly


def export_task(t, args, pel_by_img, tiles_by_img, dpi_reason):
    task, image_id, role = t["task"], t["image_id"], t["role"]
    dpi, reason = dpi_reason[image_id]
    if reason.startswith("non_feed:document"):
        sys.exit(f"REFUSED {task}: image {image_id} is a document scan")
    out = Path(args.site) / "packs" / task
    if out.exists():
        if not args.replace:
            sys.exit(f"{out} exists; use --replace")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    unc = read_unc(Path(args.src) / "tasks" / task / "annotations.zip")
    rows = pel_by_img[image_id]
    if role != "gold":
        rows = [r for r in rows if r["check"] != "none"]
    order = {f: i for i, f in enumerate(tiles_by_img[image_id])}
    items_raw = []
    for r in rows:
        pts = parse_points(r["points"])
        c = (pts.min(0) + pts.max(0)) / 2
        items_raw.append((order[r["frame"]], c[1], c[0], r, pts))
    items_raw.sort(key=lambda x: x[:3])
    seen = set()
    items, nbytes = [], 0
    cur, img, med = None, None, None
    for _, _, _, r, pts in items_raw:
        aid = int(r["auto_id"])
        if aid in seen:
            sys.exit(f"{task}: duplicate auto_id {aid}")
        seen.add(aid)
        if r["frame"] != cur:
            cur = r["frame"]
            img = np.array(Image.open(Path(args.src) / "tasks" / task / "images" / cur).convert("RGB"))
            med = np.median(img[::8, ::8].reshape(-1, 3), axis=0).astype(np.uint8)
        crop, poly = make_crop(img, pts, med, args.crop)
        p = out / f"{aid}.jpg"
        Image.fromarray(crop).save(p, quality=args.quality, optimize=True)
        nbytes += p.stat().st_size
        (_, (lw, sw), _) = cv2.minAreaRect(pts)
        mm = 25.4 / dpi
        items.append({"aid": aid, "auto": r["cls"], "check": r["check"],
                      "unc": unc.get((cur, aid), 0),
                      "len_mm": round(max(lw, sw) * mm, 2), "wid_mm": round(min(lw, sw) * mm, 2),
                      "poly": poly})
    man = {"id": task, "image_id": image_id, "role": role, "stratum": t["stratum"], "dpi": dpi,
           "crop": args.crop, "made": date.today().isoformat(), "items": items}
    (out / "manifest.json").write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
    return len(items), nbytes + (out / "manifest.json").stat().st_size


def merge_index(site, entries):
    p = Path(site) / "packs" / "index.json"
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    by = {e["id"]: e for e in cur}
    for e in entries:
        by[e["id"]] = e
    new = [by[k] for k in sorted(by)]
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(new, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--site", required=True, help="packs repo clone (holds packs/)")
    ap.add_argument("--task", action="append", help="task name(s), repeatable or comma list; default all")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--crop", type=int, default=384)
    ap.add_argument("--quality", type=int, default=85)
    args = ap.parse_args()

    src = Path(args.src)
    with open(src / "tasks.csv", newline="", encoding="utf-8") as f:
        tasks = list(csv.DictReader(f))
    if args.task:
        want = [x for a in args.task for x in a.split(",") if x]
        known = {t["task"] for t in tasks}
        bad = [w for w in want if w not in known]
        if bad:
            sys.exit(f"unknown task(s): {bad}")
        tasks = [t for t in tasks if t["task"] in want]
    imgs = {t["image_id"] for t in tasks}

    tiles = {}
    with open(src / "tiles.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["image_id"] in imgs:
                tiles.setdefault(r["image_id"], []).append(r["frame"])
    pel = {}
    with gzip.open(src / "pellets.csv.gz", "rt", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["image_id"] in imgs:
                pel.setdefault(r["image_id"], []).append(r)
    dpi_reason = {}
    with open(args.manifest, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["image_id"] in imgs:
                dpi_reason[r["image_id"]] = (int(float(r["dpi"])), r.get("reason") or "")
    missing = imgs - set(dpi_reason)
    if missing:
        sys.exit(f"not in manifest: {sorted(missing)}")

    tot_n, tot_b = 0, 0
    for t in tasks:
        t0 = time.time()
        n, b = export_task(t, args, pel, tiles, dpi_reason)
        merge_index(args.site, [{"id": t["task"], "n": n, "role": t["role"], "stratum": t["stratum"],
                                 "image_id": t["image_id"]}])
        tot_n += n
        tot_b += b
        print(f"{t['task']}: n={n} {b / 1e6:.1f} MB {time.time() - t0:.1f} s ({b / max(n, 1) / 1024:.1f} KB/crop)",
              flush=True)
    print(f"total: {len(tasks)} packs, {tot_n} pellets, {tot_b / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
