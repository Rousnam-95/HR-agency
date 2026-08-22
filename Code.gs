/*************************************************************************
 * HR-STAFFING LEAD SHEET  —  bootstrap Apps Script
 * Author: built for Mansour Traboulsi (mansour.traboulsi@telus.com)
 *
 * WHAT THIS IS
 *   The Sheet-delivery half of the leadgen-hr-staffing pipeline (see the repo README).
 *   The Python CLI (`python -m leadgen ingest ...`) filters/geo-buckets/dedupes leads
 *   locally, then POSTs new ones here as JSON. This script owns the actual Google Sheet:
 *     1) A "Leads" tab that's the persistent database (never rebuilt/duplicated on rerun)
 *     2) "Grand Montreal" / "Other" tabs that are live FILTER() views over Leads
 *     3) An "Excluded" tab (audit trail: why a posting got filtered out)
 *     4) A "Dashboard" tab with COUNTIF/AVERAGEIFS summary metrics
 *     5) A LeadScore column, recomputed daily so recency decays like request-tracker's priority
 *
 * HOW TO INSTALL  (one time, ~3 minutes)
 *   1. Go to https://script.google.com  ->  New project
 *   2. Paste THIS file into Code.gs (replace everything). No other files needed (no Form.html
 *      -- this project has no intake form, only the doPost ingestion endpoint).
 *   3. Run the function  setup  (top toolbar). Approve the permissions prompt.
 *      -> The Execution log prints your Spreadsheet URL. Open & bookmark it.
 *   4. Deploy the web app:  Deploy -> New deployment
 *        - Type: Web app
 *        - Execute as: Me
 *        - Who has access: Anyone within TELUS  (or "Anyone" if you want it reachable from a
 *          personal Google account / off the TELUS network -- see HOW-TO-Deploy-Sheet.md)
 *      Copy the Web app URL -> put it in .env as SHEET_WEBAPP_URL.
 *
 * To re-deploy after editing later: Deploy -> Manage deployments -> edit (pencil)
 *************************************************************************/

/******************** CONFIG ********************/
var CONFIG = {
  SPREADSHEET_NAME: 'HR Staffing Leads',
  SHEET: 'Leads',
  EXCLUDED_SHEET: 'Excluded',
  DASH: 'Dashboard',
  GRAND_MTL_SHEET: 'Grand Montreal',
  OTHER_SHEET: 'Other',
  GRAND_MTL_VALUE: 'Grand Montreal',   // must match leadgen/data/qc_geo_lookup.csv's region_bucket values exactly
  OTHER_VALUE: 'Other',
};

/* Column layout (1-indexed) for the Leads tab. Change order here only if you also update
   buildLeadsSheet()/ingestLeads(). */
var COL = {
  ID: 1, DEDUPE_KEY: 2, DATE_FIRST_SEEN: 3, DATE_LAST_SEEN: 4, TIMES_SEEN: 5,
  SOURCE: 6, POSTING_ID: 7, POSTING_URL: 8, COMPANY_NAME: 9, NAICS_CODE: 10,
  JOB_TITLE: 11, MUNICIPALITY: 12, REGION_BUCKET: 13, DISTANCE_KM: 14,
  HEADCOUNT_BUCKET: 15, HEADCOUNT_RAW: 16, CONTACT_NAME: 17, CONTACT_TITLE: 18,
  CONTACT_EMAIL: 19, CONTACT_PHONE: 20, CONTACT_SOURCE_TIER: 21, CONTACT_CONFIDENCE: 22,
  LEAD_SCORE: 23, NOTES: 24
};
var HEADERS = [
  'ID', 'Dedupe Key', 'Date First Seen', 'Date Last Seen', 'Times Seen',
  'Source', 'Posting ID', 'Posting URL', 'Company Name', 'NAICS',
  'Job Title', 'Municipality', 'Region', 'Distance (km)',
  'Headcount Bucket', 'Headcount (raw)', 'Contact Name', 'Contact Title',
  'Contact Email', 'Contact Phone', 'Contact Source', 'Contact Confidence',
  'Lead Score', 'Notes'
];

var EXCL_COL = { COMPANY_NAME: 1, JOB_TITLE: 2, MUNICIPALITY: 3, TYPE: 4, METHOD: 5, REASON: 6, DATE_LOGGED: 7 };
var EXCL_HEADERS = ['Company Name', 'Job Title', 'Municipality', 'Type', 'Method', 'Reason', 'Date Logged'];

/******************** WEB APP — JSON ingestion endpoint ********************/
/* No doGet -- this project has no human-facing intake page, only doPost from the CLI. */
function doPost(e) {
  var result;
  try {
    var body = JSON.parse(e.postData.contents);
    result = ingestBatch(body.leads || [], body.excluded || [], body.dropped || []);
  } catch (err) {
    result = { error: String(err) };
  }
  return ContentService.createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

function ingestBatch(leads, excluded, dropped) {
  var ss = getSpreadsheet();
  ensureAllSheetsExist(ss);
  var sheet = ss.getSheetByName(CONFIG.SHEET);
  var now = new Date();

  var existingRowByKey = getExistingDedupeKeys(sheet);
  var appended = 0, updated = 0;

  leads.forEach(function (lead) {
    var key = lead.dedupe_key || '';
    var existingRow = key ? existingRowByKey[key] : undefined;
    if (existingRow) {
      sheet.getRange(existingRow, COL.DATE_LAST_SEEN).setValue(now);
      var timesCell = sheet.getRange(existingRow, COL.TIMES_SEEN);
      timesCell.setValue((timesCell.getValue() || 0) + 1);
      recomputeRowScore(sheet, existingRow, now);
      updated++;
      return;
    }

    var id = nextId(sheet);
    var row = new Array(HEADERS.length);
    row[COL.ID - 1] = id;
    row[COL.DEDUPE_KEY - 1] = key;
    row[COL.DATE_FIRST_SEEN - 1] = now;
    row[COL.DATE_LAST_SEEN - 1] = now;
    row[COL.TIMES_SEEN - 1] = lead.times_seen || 1;
    row[COL.SOURCE - 1] = lead.source || '';
    row[COL.POSTING_ID - 1] = lead.posting_id || '';
    row[COL.POSTING_URL - 1] = lead.posting_url || '';
    row[COL.COMPANY_NAME - 1] = lead.company_name || '';
    row[COL.NAICS_CODE - 1] = lead.naics_code || '';
    row[COL.JOB_TITLE - 1] = lead.job_title || '';
    row[COL.MUNICIPALITY - 1] = lead.municipality || '';
    row[COL.REGION_BUCKET - 1] = lead.region_bucket || '';
    row[COL.DISTANCE_KM - 1] = lead.distance_km || '';
    row[COL.HEADCOUNT_BUCKET - 1] = lead.headcount_bucket || '';
    row[COL.HEADCOUNT_RAW - 1] = lead.vacancy_count_raw || '';
    row[COL.CONTACT_NAME - 1] = lead.contact_name || '';
    row[COL.CONTACT_TITLE - 1] = lead.contact_title || '';
    row[COL.CONTACT_EMAIL - 1] = lead.contact_email || '';
    row[COL.CONTACT_PHONE - 1] = lead.contact_phone || '';
    row[COL.CONTACT_SOURCE_TIER - 1] = lead.contact_source_tier || '';
    row[COL.CONTACT_CONFIDENCE - 1] = lead.contact_confidence || '';
    row[COL.LEAD_SCORE - 1] = computeLeadScore(lead, 0);
    row[COL.NOTES - 1] = lead.notes || '';

    sheet.appendRow(row);
    if (key) existingRowByKey[key] = sheet.getLastRow();
    appended++;
  });

  logExcluded(ss, excluded, dropped, now);

  return { appended: appended, updated: updated, receivedLeads: leads.length,
           receivedExcluded: excluded.length, receivedDropped: dropped.length };
}

function logExcluded(ss, excluded, dropped, now) {
  if (!excluded.length && !dropped.length) return;
  var sheet = ss.getSheetByName(CONFIG.EXCLUDED_SHEET);
  var rows = [];
  excluded.forEach(function (x) {
    rows.push([x.company_name || '', x.job_title || '', x.municipality || '',
               'Sector', x.exclusion_method || '', x.exclusion_reason || '', now]);
  });
  dropped.forEach(function (x) {
    rows.push([x.company_name || '', x.job_title || '', x.municipality || '',
               'Geo', '', x.drop_reason || '', now]);
  });
  if (rows.length) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, EXCL_HEADERS.length).setValues(rows);
  }
}

function getExistingDedupeKeys(sheet) {
  var last = sheet.getLastRow();
  var map = {};
  if (last < 2) return map;
  var keys = sheet.getRange(2, COL.DEDUPE_KEY, last - 1, 1).getValues();
  for (var i = 0; i < keys.length; i++) {
    if (keys[i][0]) map[keys[i][0]] = i + 2;
  }
  return map;
}

/******************** LEAD SCORING ********************/
/* HeadcountWeight x ContactCompletenessWeight + RecencyBonus, mirroring request-tracker's
   impact x urgency + age-bonus pattern. Recomputed daily by refreshLeadScores() so recency
   decays over time instead of freezing at ingestion-time freshness forever. */
function headcountWeight(bucket) {
  return ({ '1-4': 1, '5-9': 2, '10-24': 3, '25+': 4 })[bucket] || 0;
}
function contactWeight(lead) {
  var hasName = !!lead.contact_name;
  var hasEmail = !!lead.contact_email, hasPhone = !!lead.contact_phone;
  if (hasName && hasEmail && hasPhone) return 3;
  if (hasName && (hasEmail || hasPhone)) return 2;
  if (hasEmail || hasPhone) return 1;
  return 0;
}
function recencyBonus(daysOld) {
  if (daysOld <= 7) return 2;
  if (daysOld <= 30) return 1;
  return 0;
}
function computeLeadScore(lead, daysOld) {
  return headcountWeight(lead.headcount_bucket) * contactWeight(lead) + recencyBonus(daysOld);
}

/* Recompute one row's score in place (used on a re-seen update, mid-batch). */
function recomputeRowScore(sheet, row, now) {
  var vals = sheet.getRange(row, 1, 1, HEADERS.length).getValues()[0];
  var firstSeen = vals[COL.DATE_FIRST_SEEN - 1];
  var daysOld = firstSeen instanceof Date ? Math.floor((now - firstSeen) / 86400000) : 0;
  var lead = {
    headcount_bucket: vals[COL.HEADCOUNT_BUCKET - 1],
    contact_name: vals[COL.CONTACT_NAME - 1],
    contact_email: vals[COL.CONTACT_EMAIL - 1],
    contact_phone: vals[COL.CONTACT_PHONE - 1],
  };
  sheet.getRange(row, COL.LEAD_SCORE).setValue(computeLeadScore(lead, daysOld));
}

/* Daily trigger: recompute every row's score for recency decay + re-sort by score desc. */
function refreshLeadScores() {
  var sheet = getSpreadsheet().getSheetByName(CONFIG.SHEET);
  var last = sheet.getLastRow();
  if (last < 2) return;
  var now = new Date();
  var n = last - 1;
  var data = sheet.getRange(2, 1, n, HEADERS.length).getValues();
  data.forEach(function (row) {
    var firstSeen = row[COL.DATE_FIRST_SEEN - 1];
    var daysOld = firstSeen instanceof Date ? Math.floor((now - firstSeen) / 86400000) : 0;
    var lead = {
      headcount_bucket: row[COL.HEADCOUNT_BUCKET - 1], contact_name: row[COL.CONTACT_NAME - 1],
      contact_email: row[COL.CONTACT_EMAIL - 1], contact_phone: row[COL.CONTACT_PHONE - 1],
    };
    row[COL.LEAD_SCORE - 1] = computeLeadScore(lead, daysOld);
  });
  sheet.getRange(2, 1, n, HEADERS.length).setValues(data);
  sortByScore(sheet);
}

function sortByScore(sheet) {
  var last = sheet.getLastRow();
  if (last < 3) return;
  var range = sheet.getRange(2, 1, last - 1, HEADERS.length);
  var data = range.getValues();
  data.sort(function (a, b) { return (b[COL.LEAD_SCORE - 1] || 0) - (a[COL.LEAD_SCORE - 1] || 0); });
  range.setValues(data);
}

/******************** SETUP — run this ONCE ********************/
function setup() {
  var ss = getSpreadsheet();
  ensureAllSheetsExist(ss);
  installTriggers(ss);
  var url = ss.getUrl();
  console.log('Setup complete.');
  console.log('Spreadsheet (bookmark this): ' + url);
  console.log('Next: Deploy -> New deployment -> Web app, then put that URL in .env as SHEET_WEBAPP_URL.');
  return url;
}

function ensureAllSheetsExist(ss) {
  if (!ss.getSheetByName(CONFIG.SHEET)) buildLeadsSheet(ss);
  if (!ss.getSheetByName(CONFIG.EXCLUDED_SHEET)) buildExcludedSheet(ss);
  if (!ss.getSheetByName(CONFIG.GRAND_MTL_SHEET)) buildRegionView(ss, CONFIG.GRAND_MTL_SHEET, CONFIG.GRAND_MTL_VALUE);
  if (!ss.getSheetByName(CONFIG.OTHER_SHEET)) buildRegionView(ss, CONFIG.OTHER_SHEET, CONFIG.OTHER_VALUE);
  if (!ss.getSheetByName(CONFIG.DASH)) buildDashboard(ss);
}

function buildLeadsSheet(ss) {
  var sheet = ss.insertSheet(CONFIG.SHEET);
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setFontWeight('bold').setFontColor('#ffffff').setBackground('#4B286D');
  sheet.setFrozenRows(1);
  sheet.hideColumns(COL.DEDUPE_KEY);   // internal dedupe key, not for human eyes

  var scoreRange = sheet.getRange(2, COL.LEAD_SCORE, sheet.getMaxRows() - 1, 1);
  sheet.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThanOrEqualTo(8).setBackground('#D9EAD3').setRanges([scoreRange]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(4, 7.99).setBackground('#FCE5CD').setRanges([scoreRange]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(4).setBackground('#F4CCCC').setRanges([scoreRange]).build(),
  ]);

  var confRange = sheet.getRange(2, COL.CONTACT_CONFIDENCE, sheet.getMaxRows() - 1, 1);
  sheet.setConditionalFormatRules(sheet.getConditionalFormatRules().concat([
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Low').setBackground('#F4CCCC').setRanges([confRange]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('High').setBackground('#D9EAD3').setRanges([confRange]).build(),
  ]));

  sheet.setColumnWidth(COL.COMPANY_NAME, 220);
  sheet.setColumnWidth(COL.JOB_TITLE, 180);
  sheet.setColumnWidth(COL.CONTACT_NAME, 160);
  sheet.setColumnWidth(COL.NOTES, 240);
}

function buildExcludedSheet(ss) {
  var sheet = ss.insertSheet(CONFIG.EXCLUDED_SHEET);
  sheet.getRange(1, 1, 1, EXCL_HEADERS.length).setValues([EXCL_HEADERS])
    .setFontWeight('bold').setFontColor('#ffffff').setBackground('#7a7a7a');
  sheet.setFrozenRows(1);
}

/* A live-formula view, not a second copy of the data -- stays in sync automatically as
   Leads grows. Region string must match CONFIG.GRAND_MTL_VALUE/OTHER_VALUE exactly. */
function buildRegionView(ss, sheetName, regionValue) {
  var sheet = ss.insertSheet(sheetName);
  var lastColLetter = columnToLetter(HEADERS.length);
  var formula = '=IFERROR(FILTER(' + CONFIG.SHEET + '!A2:' + lastColLetter + ', ' +
    CONFIG.SHEET + '!' + columnToLetter(COL.REGION_BUCKET) + '2:' + columnToLetter(COL.REGION_BUCKET) +
    '="' + regionValue + '"), "(no leads yet)")';
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setFontWeight('bold').setFontColor('#ffffff').setBackground('#4B286D');
  sheet.getRange(2, 1).setFormula(formula);
  sheet.setFrozenRows(1);
}

function columnToLetter(col) {
  var letter = '';
  while (col > 0) {
    var rem = (col - 1) % 26;
    letter = String.fromCharCode(65 + rem) + letter;
    col = Math.floor((col - 1) / 26);
  }
  return letter;
}

function buildDashboard(ss) {
  var d = ss.insertSheet(CONFIG.DASH);
  var L = "'" + CONFIG.SHEET + "'!";
  var X = "'" + CONFIG.EXCLUDED_SHEET + "'!";
  var rows = [
    ['HR STAFFING LEADS DASHBOARD', ''],
    ['', ''],
    ['Total leads',                '=COUNTA(' + L + 'A2:A)'],
    ['  • Grand Montreal',         '=COUNTIF(' + L + 'M2:M,"' + CONFIG.GRAND_MTL_VALUE + '")'],
    ['  • Other (within 100km)',   '=COUNTIF(' + L + 'M2:M,"' + CONFIG.OTHER_VALUE + '")'],
    ['', ''],
    ['  • Named contact (High)',   '=COUNTIF(' + L + 'V2:V,"High")'],
    ['  • Named contact (Medium)', '=COUNTIF(' + L + 'V2:V,"Medium")'],
    ['  • Generic contact only',   '=COUNTIF(' + L + 'V2:V,"Low")'],
    ['', ''],
    ['  • Headcount 1-4',          '=COUNTIF(' + L + 'O2:O,"1-4")'],
    ['  • Headcount 5-9',          '=COUNTIF(' + L + 'O2:O,"5-9")'],
    ['  • Headcount 10-24',        '=COUNTIF(' + L + 'O2:O,"10-24")'],
    ['  • Headcount 25+',          '=COUNTIF(' + L + 'O2:O,"25+")'],
    ['', ''],
    ['Avg Lead Score',             '=IFERROR(ROUND(AVERAGE(' + L + 'W2:W),1),0)'],
    ['Top Lead Score',             '=IFERROR(MAX(' + L + 'W2:W),0)'],
    ['', ''],
    ['Total excluded (sector)',    '=COUNTIF(' + X + 'D2:D,"Sector")'],
    ['Total dropped (out of radius)', '=COUNTIF(' + X + 'D2:D,"Geo")'],
  ];
  d.getRange(1, 1, rows.length, 2).setValues(rows);
  d.getRange('A1:B1').merge().setFontSize(14).setFontWeight('bold')
    .setFontColor('#ffffff').setBackground('#4B286D');
  d.getRange(3, 1, rows.length - 2, 1).setFontWeight('bold');
  d.setColumnWidth(1, 240); d.setColumnWidth(2, 120);
}

function installTriggers(ss) {
  var ours = { refreshLeadScores: 1 };
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (ours[t.getHandlerFunction()]) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('refreshLeadScores').timeBased().everyDays(1).atHour(6).create();
}

/******************** HELPERS ********************/
function getSpreadsheet() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('SPREADSHEET_ID');
  if (id) {
    try { return SpreadsheetApp.openById(id); } catch (e) { /* fall through */ }
  }
  var ss = SpreadsheetApp.create(CONFIG.SPREADSHEET_NAME);
  props.setProperty('SPREADSHEET_ID', ss.getId());
  return ss;
}

function nextId(sheet) {
  var last = sheet.getLastRow();
  var n = 0;
  if (last >= 2) {
    var ids = sheet.getRange(2, COL.ID, last - 1, 1).getValues();
    ids.forEach(function (r) {
      var m = /LEAD-(\d+)/.exec(r[0]);
      if (m) n = Math.max(n, parseInt(m[1], 10));
    });
  }
  return 'LEAD-' + ('0000' + (n + 1)).slice(-4);
}
