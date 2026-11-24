# feedseg_labeler

เว็บลาเบลเม็ดอาหารกุ้งทีละเม็ด (static, github.io) ต้นแบบ `worm/worm_labeler` อ่าน `README.md` และ `CONTRACT.md` ก่อน
- `docs/` = รากของ GitHub Pages: `index.html` (ไฟล์เดียว), `config.json`; `docs/packs_dev/` = pack สังเคราะห์สำหรับทดสอบ (gitignored)
- `tools/` = export_pellet_pack.py, lanta_publish_pack.sh, collect_labels.py, progress.py (รันบน Lanta), apps_script.gs, dev_*.py
- คลาส/คีย์/คอลัมน์ Sheet ต้องตรง CONTRACT.md (แก้ที่เดียวแล้วแก้ index.html + apps_script.gs + collect_labels.py ให้ตรงกัน)
- **ภาพ pack ห้ามเก็บบนเครื่อง Windows** — export + push จาก Lanta เท่านั้น (`bash tools/lanta_publish_pack.sh`) ภาพอยู่ repo แยก `rungkarn/feedseg_labeler_packs`
- แก้ `apps_script.gs` แล้วต้อง deploy เวอร์ชันใหม่ใน Apps Script เอง (URL เดิม)
- localStorage ใช้ prefix `fsl:` เสมอ; ใช้ `e.code` ไม่ใช้ `e.key` (คีย์บอร์ดไทย)
- ตอบผู้ใช้เป็นภาษาไทย; แก้ไฟล์ไทยด้วย Edit/Write ไม่ใช้ PowerShell Get/Set-Content
