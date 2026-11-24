# feedseg_labeler

เว็บลาเบลเม็ดอาหารกุ้ง ทีละเม็ด (static, GitHub Pages + Google Sheet) ต้นแบบคือ `worm_labeler` สัญญาระหว่าง pack / หน้าเว็บ / Sheet อยู่ใน [CONTRACT.md](CONTRACT.md)

## ภาพรวม

```
Lanta                               GitHub Pages                       คนลาเบล                 Google Sheet
cvat_review/v1 ──export_pellet_pack──> feedseg_labeler_packs (ภาพ crop)
                  (บน Lanta เท่านั้น)   feedseg_labeler (หน้าเว็บ)  ──>  เปิดลิงก์ ?pack=..&u=ชื่อ
                                                                          │ กด 1–6 (+ c x e)
                                                                          └── POST ทุก 10 เม็ด / 15 วิ ──> แท็บ labels
Lanta: collect_labels.py <────────────── ดึงจาก Sheet (?action=dump) <───────────────────────────────┘
        → web_labels/<วันที่>/{rows,latest}.csv + summary.txt
```

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `docs/index.html` | หน้าลาเบล ไฟล์เดียว ไม่พึ่ง CDN |
| `docs/config.json` | `endpoint` (URL /exec ของ Apps Script), `token`, `packsBase` (เว็บที่เก็บภาพ) |
| `tools/apps_script.gs` | ตัวรับข้อมูล วางใน Google Sheet (append-only) |
| `tools/export_pellet_pack.py` | ทำ pack จาก CVAT review (รันบน Lanta) |
| `tools/lanta_publish_pack.sh` | export + commit + push repo ภาพ (บน Lanta) |
| `tools/collect_labels.py` | ดึงผลจาก Sheet ลงไฟล์บน Lanta |
| `tools/progress.py` | ดูความคืบหน้า per pack × user |
| `tools/dev_make_pack.py`, `tools/dev_mock_endpoint.py` | ทดสอบในเครื่อง (pack สังเคราะห์ + endpoint ปลอม) |

ภาพไม่อยู่ใน repo นี้ อยู่ repo แยก `rungkarn/feedseg_labeler_packs` ภาพสร้างและ push จาก Lanta เท่านั้น ห้ามเก็บบนเครื่อง Windows

## ตั้ง Google Sheet (ผู้ดูแลทำครั้งเดียว)

1. สร้าง Google Sheet ใหม่
2. เมนู Extensions → Apps Script ลบโค้ดเดิม วางเนื้อหา `tools/apps_script.gs` กด Save (ถ้าจะใช้ token ให้ใส่ใน `TOKEN` และใส่ค่าเดียวกันใน `docs/config.json`)
3. Deploy → New deployment → ประเภท Web app → Execute as: **Me**, Who has access: **Anyone** → Deploy → อนุญาตสิทธิ์
4. คัดลอก URL ที่ลงท้าย `/exec` ใส่ใน `docs/config.json` ช่อง `endpoint` แล้ว commit/push
5. ทดสอบ: เปิด `<URL>/exec?action=dump` ในเบราว์เซอร์ ต้องได้ `{"ok":true,"rows":[]}` แท็บ `labels` ถูกสร้างตอนมีข้อมูลแรก
6. แก้สคริปต์ภายหลัง: Deploy → Manage deployments → ดินสอบน deployment เดิม → Version: New version → Deploy (URL เดิมไม่เปลี่ยน ห้ามกด New deployment)

คอลัมน์ในแท็บ `labels`: `ts | user | pack | image_id | aid | cls | flags | auto | client_ts` เพิ่มแถวอย่างเดียว ไม่แก้ทับ ค่าล่าสุดต่อ (user, pack, image_id, aid) ชนะ, `cls = -1` = ล้างคำตอบ

## ลิงก์ที่ส่งให้คนลาเบล

```
https://rungkarn.github.io/feedseg_labeler/?pack=gold_asian_2_0019&u=somchai
```

- ไม่ใส่ `pack` = หน้าเลือกชุด (แสดงจำนวนที่ตอบแล้ว / ทั้งหมดของคนนั้น)
- ไม่ใส่ `u` = ถามชื่อ (จำไว้ในเครื่อง)
- เปิดซ้ำ/เปลี่ยนเครื่อง: หน้าเว็บดึงคำตอบเดิมจาก Sheet แล้วไปเม็ดที่ยังไม่ตอบ
- ทดสอบในเครื่อง: `?base=/packs_dev/` (ที่เก็บภาพ) และ `?endpoint=http://localhost:8788/`

## ปุ่ม

| ปุ่ม | หน้าที่ |
|---|---|
| 1 | เม็ดนอน `pellet_lying` |
| 2 | เม็ดตั้ง `pellet_standing` |
| 3 | ไม่แน่ใจ `uncertain` (ใช้เมื่อดูไม่ออกจริง ๆ อย่าเดา) |
| 4 | หัก เหลือน้อยกว่าครึ่ง `broken` |
| 5 | กอง/ติดกันหลายเม็ด `clump` |
| 6 | ไม่ใช่เม็ด (ฝุ่น ริ้ว เงา) `not_pellet` |
| 0 | ล้างคำตอบ |
| c / x / e | ติด flag: ร้าว / บิ่น (เหลือมากกว่าครึ่ง) / ขอบผิด (กดซ้ำ = เอาออก ไม่เลื่อนเม็ด) |
| o | เปิด/ปิดเส้นขอบ |
| Space, →, d | ถัดไป |
| Backspace, ←, a | ย้อน |
| n | ไปเม็ดที่ยังไม่ตอบ |
| s | ส่งทันที |

กด 1–6 แล้วขึ้น ✅ ชื่อคำตอบ 0.6 วินาที จากนั้นไปเม็ดถัดไปเอง คีย์ใช้ตำแหน่งปุ่มจริง (`e.code`) จึงใช้ได้แม้คีย์บอร์ดเป็นภาษาไทย

ถ้าไม่ตั้ง `endpoint` หรือส่งไม่ได้ ผลยังเก็บในเครื่อง กด **Download CSV** ได้เสมอ ไฟล์ `labels_<pack>_<user>.csv` คอลัมน์ `image_id,aid,cls,flags,auto`

## ทำ pack และเก็บผล (บน Lanta)

รายละเอียดอาร์กิวเมนต์ดูหัวไฟล์แต่ละตัว (`python tools/<ชื่อ>.py -h`)

```bash
# ทำ pack + push repo ภาพ (ไม่ใส่ --task = ทั้ง 55 task ราว 0.3 GB)
bash tools/lanta_publish_pack.sh --task gold_asian_2_0019,gold_asian_2S_0030 --replace

# ความคืบหน้า
python tools/progress.py [--pack <id>]

# เก็บผล -> data/processed/Shrimp/web_labels/<YYYYMMDD>/{rows.csv,latest.csv,summary.txt}
python tools/collect_labels.py            # endpoint จาก docs/config.json
python tools/collect_labels.py --csv labels.csv   # หรือจาก Sheet ที่ export เป็น CSV
```

`latest.csv` = หนึ่งแถวต่อ user × เม็ด, `summary.txt` มีตารางตอบแล้ว/ทั้งหมด, ระบบเดา → คำตอบคน, และ % ตรงกันของเม็ดที่ ≥ 2 คนตอบ (ไม่นับ 3 ไม่แน่ใจ)

## เมื่อลาเบลจบ

ลบ repo `rungkarn/feedseg_labeler_packs` ทิ้งแล้วสร้างใหม่ (ประวัติภาพหายหมด ไม่ให้ repo โตค้าง) ผลอยู่ใน Sheet และไฟล์ `web_labels/` บน Lanta แล้ว

## ทดสอบในเครื่อง (ไม่ต้องใช้ภาพจริง)

```
python tools/dev_make_pack.py                     # pack สังเคราะห์ที่ docs/packs_dev/ (ไม่ถูก commit)
python tools/dev_mock_endpoint.py 8788            # endpoint ปลอม เก็บในหน่วยความจำ
python -m http.server 8787 --directory docs
# เปิด http://localhost:8787/?base=/packs_dev/&endpoint=http://localhost:8788/&u=test&pack=gold_dev_a
```
