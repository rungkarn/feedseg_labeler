# feedseg_labeler: contract between packs, page and Sheet (2026-11-25)

Template: `D:\oneDrive\OneDrive - NSTDA\Projects\worm\worm_labeler` (README, docs/index.html, tools/*). Same flow, per pellet instead of per worm.

## Repos and hosts

| repo | holds | site | Lanta clone (deploy-key ssh alias) |
|---|---|---|---|
| `rungkarn/feedseg_labeler` | code only: `docs/index.html`, `docs/config.json`, `tools/` | https://rungkarn.github.io/feedseg_labeler/ | `/project/lt200264-saiwat/FeedProject/web/feedseg_labeler_repo` (`github-fl`) |
| `rungkarn/feedseg_labeler_packs` | images only: `packs/` | https://rungkarn.github.io/feedseg_labeler_packs/ | `/project/lt200264-saiwat/FeedProject/web/feedseg_labeler_packs_repo` (`github-flp`) |

Images are made and pushed on Lanta only, never stored on the Windows PC.
Lanta python: `/project/lt200264-saiwat/Env/segmentation/bin/python` (numpy, Pillow, opencv, pandas). Run with `-I`.

## Source data (Lanta, read-only)

`/project/lt200264-saiwat/FeedProject/data/processed/Shrimp/cvat_review/v1/`
- `tasks.csv`: `task,image_id,role,kind,stratum,frames,pellets,to_check,core_px,MB,seconds` (55 tasks; role gold|review)
- `tiles.csv`: `image_id,frame,fx0,fy0,fx1,fy1,cx0,cy0,cx1,cy1,n` (frame box and core box in full-scan px)
- `pellets.csv.gz`: `image_id,frame,auto_id,cls,check,points` (`points` = `x,y;x,y;…` in FRAME px, simplified polygon; `check` = all|uncertain|clump|touching|random|none)
- `tasks/<task>/images/<frame>.png`: frame images (each pellet lies fully inside its own frame)
- `config.json`, `labels.json`
- DPI per scan: `/project/lt200264-saiwat/FeedProject/data/processed/Shrimp/manifest.csv` column `dpi` (key `image_id`). mm = px × 25.4 / dpi.
- `uncertain` flag per pellet: from `tasks/<task>/annotations.zip` (CVAT 1.1 XML, attribute `uncertain` per polygon, attribute `auto_id`), or skip if hard; it is shown as a hint only.

## Selection

- gold tasks: every pellet. review tasks: only `check != none`. About 12,767 pellets.
- Refuse any `image_id` whose manifest `reason` starts with `non_feed:document` (internal documents, must never be published).
- One pack per task: pack id = task name (e.g. `gold_asian_2_0019`). Order inside a pack: frame, then top-to-bottom / left-to-right by bbox centre.

## Pack layout (`feedseg_labeler_packs` repo)

- `packs/index.json`: `[{"id": "<task>", "n": <pellets>, "role": "gold|review", "stratum": "asian/2", "image_id": "asian_2_0019"}, …]` (merge, keep other packs)
- `packs/<id>/manifest.json`:
  ```json
  {"id": "gold_asian_2_0019", "image_id": "asian_2_0019", "role": "gold", "stratum": "asian/2", "dpi": 1450,
   "crop": 384, "made": "2026-11-25",
   "items": [{"aid": 10, "auto": "pellet_lying", "check": "all", "unc": 0,
              "len_mm": 2.31, "wid_mm": 1.05, "poly": [[x, y], …]}]}
  ```
  `poly` = pellet outline in CROP px (0…crop), ints. `len_mm`/`wid_mm` = min-area rectangle of the polygon (from frame px), 2 decimals.
- `packs/<id>/<aid>.jpg`: square crop, `crop` × `crop` px (384), JPEG quality 85.
  Crop side in frame px S = max(3 × longest bbox side, 96), centred on the bbox centre; outside the frame = pad with the frame's median colour. Resized to 384 with area interpolation.
  Pack size target ≈ 25 KB per crop → whole set ≈ 0.3 GB.

## Classes and keys (page)

`Class` code sent to the Sheet = key number. Use `e.code` (`Digit1`, `Numpad1`, `KeyC`, …) so a Thai keyboard layout still works.

| Class | key | name (Thai on button) | auto class it maps from |
|---|---|---|---|
| 1 | 1 | เม็ดนอน `pellet_lying` | pellet_lying |
| 2 | 2 | เม็ดตั้ง `pellet_standing` | pellet_standing |
| 3 | 3 | ไม่แน่ใจ `uncertain` | |
| 4 | 4 | หัก (เหลือ < ครึ่ง) `broken` | broken |
| 5 | 5 | กอง/ติดกันหลายเม็ด `clump` | clump |
| 6 | 6 | ไม่ใช่เม็ด (ฝุ่น ริ้ว เงา) `not_pellet` | debris |
| -1 | 0 | clear | |

Picking 1–6 → big green "✅ name" for 600 ms, then next pellet (as worm v2.1).
Flags (toggle, no advance): `c` ร้าว cracked, `x` บิ่น chipped (> half left, broken end), `e` ขอบผิด wrong edge. `flags` = sorted letters, e.g. `"ce"` or `""`.
Navigation: `→`/`Space`/`d` next, `←`/`Backspace`/`a` back, `n` next unanswered, `s` sync now. Changing flags on an answered pellet sends a new row.

Screen per pellet: left = raw crop, right = same crop with `poly` drawn (thin bright outline). Under it: auto class, `len_mm × wid_mm`, `unc` hint, `check`, position `k / n`, pack, user. A toggle (`o` key) hides the outline. Must fit a short notebook screen and a 375 px phone.

## Sheet (one Google Sheet, Apps Script web app, append-only)

Tab `labels`, header: `ts | user | pack | image_id | aid | cls | flags | auto | client_ts`
- POST body (text/plain JSON, like worm): `{"token": "", "user": "...", "pack": "...", "rows": [{"image_id": "...", "aid": 10, "cls": 2, "flags": "c", "auto": "pellet_lying", "t": "<ISO>"}]}` → `{"ok": true, "n": <rows appended>}`. Validate user (`^[\w฀-๿\-]{1,30}$`), pack (`^[\w\-]{1,60}$`), image_id, aid int, cls in −1…6, flags ⊂ `cxe`; max 500 rows per post.
- GET `?action=dump[&pack=..][&user=..]` → `{"ok": true, "rows": [[ts, user, pack, image_id, aid, cls, flags, auto, client_ts], …]}`.
- Latest `ts` per (user, pack, image_id, aid) wins; cls −1 = cleared.
- Page: send every 10 labels / 15 s / on tab close; keep a localStorage queue and retry with backoff; on open, restore the user's state from `dump` and jump to the first unanswered. Download CSV fallback always works (no endpoint needed): `labels_<pack>_<user>.csv` with `image_id,aid,cls,flags,auto`.
- `docs/config.json`: `{"endpoint": "", "token": "", "packsBase": "https://rungkarn.github.io/feedseg_labeler_packs/"}`. Empty endpoint = CSV only.
- URL: `https://rungkarn.github.io/feedseg_labeler/?pack=<id>&u=<name>`; no pack → pick list from `packs/index.json` with the user's progress.

## Collect (Lanta)

`tools/collect_labels.py` (Lanta, reads endpoint from `docs/config.json`, or `--csv` export) →
`/project/lt200264-saiwat/FeedProject/data/processed/Shrimp/web_labels/<YYYYMMDD>/`:
`rows.csv` (all rows as fetched), `latest.csv` (one row per user × pellet: `user,pack,image_id,aid,cls,cls_name,flags,auto,ts`), `summary.txt` (per pack × user: answered / n; auto → label table; for pellets with ≥ 2 users: agreement %, excluding cls 3).
`tools/progress.py`: per pack × user answered / n (reads Sheet + manifests on the site).
