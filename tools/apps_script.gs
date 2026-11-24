/**
 * feedseg_labeler: receiver (Google Apps Script bound to a Google Sheet).
 *
 * Setup (README.md section "ตั้ง Google Sheet"):
 *  1. Create a Google Sheet. Extensions > Apps Script. Paste this file. Save.
 *  2. Deploy > New deployment > type Web app > Execute as: Me, Who has access: Anyone.
 *  3. Put the /exec URL (and TOKEN, if you set one) into docs/config.json.
 *  4. Test in a browser: <exec url>?action=dump  -> {"ok":true,"rows":[...]}
 *
 * After editing this script: Deploy > Manage deployments > pencil (edit) the EXISTING deployment >
 * Version: New version > Deploy. That keeps the /exec URL; "New deployment" makes a new URL.
 *
 * Sheet tab "labels" (created on first use), header:
 *   ts | user | pack | image_id | aid | cls | flags | auto | client_ts
 * Rows are only APPENDED. Latest ts per (user, pack, image_id, aid) wins; cls -1 = cleared.
 *
 * POST (text/plain JSON): {token, user, pack, rows:[{image_id, aid, cls, flags, auto, t}]} -> {ok, n}
 * GET  ?action=dump[&pack=P][&user=U][&token=T] -> {ok, rows:[[ts,user,pack,image_id,aid,cls,flags,auto,client_ts],...]}
 *      (all rows in append order; the client/collector takes the latest per key)
 */
const SHEET_NAME = "labels";
const TOKEN = "";          // optional shared secret; if set, must equal "token" in docs/config.json
const MAX_ROWS_PER_POST = 500;
const HEADER = ["ts", "user", "pack", "image_id", "aid", "cls", "flags", "auto", "client_ts"];

const USER_RE = /^[\w฀-๿\-]{1,30}$/;
const PACK_RE = /^[\w\-]{1,60}$/;
const IMAGE_RE = /^[\w.\-]{1,120}$/;
const AUTO_RE = /^[\w]{0,30}$/;

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(HEADER);
    sh.setFrozenRows(1);
  }
  return sh;
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

/** Validate a POST body, return the rows to append (arrays, 9 columns). Pure function: testable. */
function buildRows_(body, nowIso) {
  const user = String(body.user), pack = String(body.pack);
  if (!USER_RE.test(user) || !PACK_RE.test(pack)) return [];
  const out = [];
  const rows = Array.isArray(body.rows) ? body.rows.slice(0, MAX_ROWS_PER_POST) : [];
  for (const r of rows) {
    const cls = Number(r.cls);
    const aid = Number(r.aid);
    const flags = String(r.flags == null ? "" : r.flags);
    if (!Number.isInteger(cls) || cls < -1 || cls > 6) continue;
    if (!Number.isInteger(aid) || aid < 0) continue;
    if (!IMAGE_RE.test(String(r.image_id))) continue;
    if (!/^[cxe]{0,3}$/.test(flags)) continue;
    const auto = String(r.auto == null ? "" : r.auto);
    if (!AUTO_RE.test(auto)) continue;
    out.push([nowIso, user, pack, String(r.image_id), aid, cls, flags, auto, String(r.t || "").slice(0, 40)]);
  }
  return out;
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (TOKEN && body.token !== TOKEN) return json_({ ok: false, error: "bad token" });
    const out = buildRows_(body, new Date().toISOString());
    if (out.length) {
      const lock = LockService.getScriptLock();
      lock.waitLock(20000);
      try {
        const sh = sheet_();
        sh.getRange(sh.getLastRow() + 1, 1, out.length, HEADER.length).setValues(out);
      } finally {
        lock.releaseLock();
      }
    }
    return json_({ ok: true, n: out.length });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  try {
    const p = (e && e.parameter) || {};
    if (TOKEN && p.token !== TOKEN) return json_({ ok: false, error: "bad token" });
    if (p.action !== "dump") return json_({ ok: true, service: "feedseg-labeler" });
    const sh = sheet_();
    const n = sh.getLastRow();
    const vals = n > 1 ? sh.getRange(2, 1, n - 1, HEADER.length).getValues() : [];
    const rows = [];
    for (const v of vals) {
      if (p.pack && String(v[2]) !== p.pack) continue;
      if (p.user && String(v[1]) !== p.user) continue;
      rows.push(v.map(x => (x instanceof Date ? x.toISOString() : x)));
    }
    return json_({ ok: true, rows: rows });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}
