#!/usr/bin/env python
"""Labelling progress per pack x user: answered / n. Stdlib only.

    python tools/progress.py                  # endpoint + packsBase from docs/config.json
    python tools/progress.py --pack gold_asian_2_0019
    python tools/progress.py --url https://script.google.com/macros/s/.../exec --packs-base https://rungkarn.github.io/feedseg_labeler_packs/

n per pack = `n` in packs/index.json on the packs site. Answered = latest row per (user, pack, image_id, aid) with cls >= 1.
"""
import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_CFG = Path(__file__).resolve().parent.parent / "docs" / "config.json"
COLS = ["ts", "user", "pack", "image_id", "aid", "cls", "flags", "auto", "client_ts"]


def get_json(url, timeout=120):
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


def fmt_ts(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M") if ms else "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CFG))
    ap.add_argument("--url")
    ap.add_argument("--token")
    ap.add_argument("--packs-base")
    ap.add_argument("--pack")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8")) if Path(a.config).exists() else {}
    endpoint = a.url or cfg.get("endpoint")
    token = a.token if a.token is not None else cfg.get("token", "")
    base = (a.packs_base or cfg.get("packsBase") or "").rstrip("/")
    if not endpoint:
        raise SystemExit("no endpoint (set docs/config.json or pass --url)")
    if not base:
        raise SystemExit("no packsBase (set docs/config.json or pass --packs-base)")

    index = get_json(f"{base}/packs/index.json")
    totals = {p["id"]: p["n"] for p in index if not a.pack or p["id"] == a.pack}
    if a.pack and a.pack not in totals:
        raise SystemExit(f"pack '{a.pack}' not on the packs site")

    q = {"action": "dump"}
    if a.pack:
        q["pack"] = a.pack
    if token:
        q["token"] = token
    j = get_json(endpoint + "?" + urllib.parse.urlencode(q))
    if not j.get("ok"):
        raise SystemExit(f"server error: {j}")

    best = {}
    for row in j["rows"]:
        r = dict(zip(COLS, row))
        k = (r["user"], r["pack"], str(r["image_id"]), int(r["aid"]))
        t = ts_ms(r["ts"])
        if k not in best or t >= best[k][0]:
            best[k] = (t, int(r["cls"]))

    done, last, stale = {}, {}, set()
    for (who, pack, _img, _aid), (t, c) in best.items():
        key = (pack, who)
        last[key] = max(last.get(key, 0), t)
        if pack not in totals:
            stale.add(pack)
        elif c >= 1:
            done[key] = done.get(key, 0) + 1

    rows, seen = [], set()
    for (pack, who) in sorted(set(done) | set(last)):
        if pack not in totals:
            continue
        seen.add(pack)
        d, n = done.get((pack, who), 0), totals[pack]
        rows.append((pack, who, f"{d}/{n}", f"{100 * d / n:5.1f}%", "DONE" if d >= n else f"{n - d} left",
                     fmt_ts(last.get((pack, who), 0))))
    for pack in sorted(set(totals) - seen):
        rows.append((pack, "-", f"0/{totals[pack]}", "  0.0%", "not started", "-"))
    head = ("pack", "user", "done/n", "pct", "status", "last activity")
    rows.sort(key=lambda r: (r[0], r[1]))
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    for r in [head] + rows:
        print("  ".join(str(x).ljust(w[i]) for i, x in enumerate(r)))
    if stale:
        print(f"\nnote: labels for packs not on the site: {sorted(stale)}")


if __name__ == "__main__":
    main()
