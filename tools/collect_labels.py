#!/usr/bin/env python
"""Collect web labels (Google Sheet) into Lanta files. Stdlib only.

Run ON LANTA (so the files land in the data folder):
    python tools/collect_labels.py                  # endpoint from docs/config.json
    python tools/collect_labels.py --csv labels.csv # a Sheet tab exported as CSV instead
    python tools/collect_labels.py --pack gold_asian_2_0019 --dry-run

Output dir (default <Shrimp>/web_labels/<YYYYMMDD>/):
    rows.csv     all rows as fetched
    latest.csv   one row per user x pellet: user,pack,image_id,aid,cls,cls_name,flags,auto,ts   (cleared, cls -1, dropped)
    summary.txt  per pack x user answered / n; auto -> label table; agreement (>= 2 users, cls 3 excluded)
Latest ts per (user, pack, image_id, aid) wins. n per pack comes from packs/index.json at packsBase
(or --site <packs clone>); without it n is shown as "?".
"""
import argparse
import csv
import json
import os
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_CFG = Path(__file__).resolve().parent.parent / "docs" / "config.json"
LANTA_OUT = "/project/lt200264-saiwat/FeedProject/data/processed/Shrimp/web_labels"
COLS = ["ts", "user", "pack", "image_id", "aid", "cls", "flags", "auto", "client_ts"]
CLS_NAME = {1: "pellet_lying", 2: "pellet_standing", 3: "uncertain", 4: "broken", 5: "clump", 6: "not_pellet"}


def get_json(url, timeout=180):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ts_ms(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return 0.0


def rows_from_url(endpoint, token, pack):
    q = {"action": "dump"}
    if pack:
        q["pack"] = pack
    if token:
        q["token"] = token
    j = get_json(endpoint + "?" + urllib.parse.urlencode(q))
    if not j.get("ok"):
        raise SystemExit(f"server error: {j}")
    return [dict(zip(COLS, r)) for r in j["rows"]]


def rows_from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def latest(rows):
    best = {}
    for r in rows:
        k = (r["user"], r["pack"], str(r["image_id"]), int(r["aid"]))
        t = ts_ms(r.get("ts", 0))
        if k not in best or t >= best[k][0]:
            best[k] = (t, r)
    return [r for _, r in best.values()]


def pack_sizes(base, site):
    try:
        if site:
            idx = json.loads((Path(site) / "packs" / "index.json").read_text(encoding="utf-8"))
        elif base:
            idx = get_json(f"{base}/packs/index.json")
        else:
            return {}
        return {p["id"]: p["n"] for p in idx}
    except Exception as e:
        print(f"note: no pack sizes ({e})")
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CFG))
    ap.add_argument("--url", help="Apps Script /exec URL (default: docs/config.json endpoint)")
    ap.add_argument("--csv", help="exported Sheet CSV instead of the endpoint")
    ap.add_argument("--token")
    ap.add_argument("--packs-base", help="default: docs/config.json packsBase")
    ap.add_argument("--site", help="packs repo clone (reads packs/index.json locally for n)")
    ap.add_argument("--pack", help="only this pack")
    ap.add_argument("--out", help="output dir (default web_labels/<YYYYMMDD> on Lanta, else ./labels_web/<YYYYMMDD>)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8")) if Path(a.config).exists() else {}
    endpoint = a.url or cfg.get("endpoint")
    token = a.token if a.token is not None else cfg.get("token", "")
    base = (a.packs_base or cfg.get("packsBase") or "").rstrip("/")
    day = datetime.now().strftime("%Y%m%d")
    out = Path(a.out) if a.out else Path(LANTA_OUT if os.path.isdir(LANTA_OUT) else "labels_web") / day

    if a.csv:
        rows = rows_from_csv(a.csv)
    elif endpoint:
        rows = rows_from_url(endpoint, token, a.pack)
    else:
        raise SystemExit("no endpoint (docs/config.json) and no --csv")
    if a.pack:
        rows = [r for r in rows if r["pack"] == a.pack]
    sizes = pack_sizes(base, a.site)

    lat = [r for r in latest(rows) if int(r["cls"]) >= 1]
    lat.sort(key=lambda r: (r["pack"], r["user"], str(r["image_id"]), int(r["aid"])))

    lines = []
    per = Counter((r["pack"], r["user"]) for r in lat)
    lines.append("pack x user: answered / n")
    for (pack, user), c in sorted(per.items()):
        n = sizes.get(pack)
        lines.append(f"  {pack}  {user}  {c}/{n if n else '?'}" + (f"  {100 * c / n:.1f}%" if n else ""))
    tab = defaultdict(Counter)
    for r in lat:
        tab[r["auto"]][CLS_NAME.get(int(r["cls"]), str(r["cls"]))] += 1
    lines.append("")
    lines.append("auto class -> human label (counts, all users)")
    for auto in sorted(tab):
        tot = sum(tab[auto].values())
        parts = ", ".join(f"{k} {v} ({100 * v / tot:.0f}%)" for k, v in tab[auto].most_common())
        lines.append(f"  {auto or '(none)'} [{tot}]: {parts}")
    by_pellet = defaultdict(dict)
    for r in lat:
        if int(r["cls"]) != 3:
            by_pellet[(r["pack"], str(r["image_id"]), int(r["aid"]))][r["user"]] = int(r["cls"])
    multi = [v for v in by_pellet.values() if len(v) >= 2]
    agree = sum(1 for v in multi if len(set(v.values())) == 1)
    lines.append("")
    lines.append(f"agreement (pellets with >= 2 users, cls 3 excluded): "
                 + (f"{agree}/{len(multi)} = {100 * agree / len(multi):.1f}%" if multi else "none yet"))
    summary = "\n".join(lines) + "\n"

    print(f"rows fetched {len(rows)}, latest answered {len(lat)} -> {out}{' (dry-run)' if a.dry_run else ''}")
    print(summary)
    if a.dry_run:
        return
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "rows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in rows:
            w.writerow([r.get(c, "") for c in COLS])
    with open(out / "latest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user", "pack", "image_id", "aid", "cls", "cls_name", "flags", "auto", "ts"])
        for r in lat:
            w.writerow([r["user"], r["pack"], r["image_id"], r["aid"], int(r["cls"]),
                        CLS_NAME.get(int(r["cls"]), ""), r.get("flags", ""), r.get("auto", ""), r.get("ts", "")])
    (out / "summary.txt").write_text(summary, encoding="utf-8")
    print(f"written: {out}/rows.csv latest.csv summary.txt")


if __name__ == "__main__":
    main()
