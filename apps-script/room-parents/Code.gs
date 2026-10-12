/**
 * Room parents master sheet: Draft -> Live publishing (CLAUDE.md §4, "Sheet-sourced personal data").
 *
 * Install: in the master sheet, Extensions -> Apps Script, paste this file, save, reload the
 * sheet, then run "Room parents -> Set up tabs" once. NOT deployed anywhere yet.
 *
 * Tabs:
 *   Draft    people edit here. The sites never read it.
 *   Live     what the sites publish. Protected: only PUBLISHERS (and the owner) can change it,
 *            and in practice only this script does.
 *   Log      one row per publish or undo: when, who, what changed.
 *   History  the previous Live, one row per version, for one-click undo.
 *
 * The Drive bot reads only Live, and only the columns on the Site Map's publish list.
 */

var COLUMNS = ['Class year', 'Name', 'Email'];   // required, in this order; extra columns are allowed
var PUBLISHERS = [];                             // emails allowed to publish, e.g. ['ahin@sffriendsschool.org']
var EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Room parents')
    .addItem('Publish Draft to the sites', 'publish')
    .addItem('Undo the last publish', 'undoLastPublish')
    .addSeparator()
    .addItem('Set up tabs (once)', 'setUp')
    .addToUi();
}

/**
 * Pure check, no Google services, so it can be tested anywhere.
 * header: array of column names. rows: arrays of cell values. liveCount: rows now on Live.
 * Returns {errors: [...], warnings: [...]}. Any error blocks the publish.
 */
function validateRows(header, rows, liveCount, today) {
  var errors = [], warnings = [];
  var col = {};
  COLUMNS.forEach(function (c) { col[c] = header.indexOf(c); });
  var missing = COLUMNS.filter(function (c) { return col[c] < 0; });
  if (missing.length) return {errors: ['Missing columns: ' + missing.join(', ')], warnings: []};
  var lo = today.getFullYear(), hi = lo + 10, filled = 0;
  rows.forEach(function (r, i) {
    var n = i + 2;
    if (r.join('').trim() === '') return;
    filled++;
    var year = String(r[col['Class year']]).trim(), name = String(r[col['Name']]).trim(), email = String(r[col['Email']]).trim();
    if (!/^\d{4}$/.test(year) || +year < lo || +year > hi) errors.push('Row ' + n + ': class year "' + year + '" should be a year from ' + lo + ' to ' + hi + '.');
    if (!name) errors.push('Row ' + n + ': name is blank.');
    if (email && !EMAIL.test(email)) errors.push('Row ' + n + ': "' + email + '" is not an email address.');
  });
  if (!filled) errors.push('Draft has no rows. To take everyone off the sites, ask Ahin.');
  if (liveCount >= 4 && filled < liveCount / 2) warnings.push('Draft has ' + filled + ' people; the sites show ' + liveCount + ' now. More than half would disappear.');
  return {errors: errors, warnings: warnings};
}

function tab_(name) {
  var t = SpreadsheetApp.getActive().getSheetByName(name);
  if (!t) throw new Error('No "' + name + '" tab. Run Room parents -> Set up tabs first.');
  return t;
}

function values_(sheet) {
  return sheet.getLastRow() ? sheet.getDataRange().getValues() : [];
}

function publish() {
  var ui = SpreadsheetApp.getUi();
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) { ui.alert('Someone else is publishing. Try again in a minute.'); return; }
  try {
    var draft = values_(tab_('Draft')), live = tab_('Live'), liveVals = values_(live);
    if (!draft.length) { ui.alert('Draft is empty.'); return; }
    var check = validateRows(draft[0].map(String), draft.slice(1), Math.max(liveVals.length - 1, 0), new Date());
    if (check.errors.length) {
      ui.alert('Not published. Fix these in Draft:\n\n' + check.errors.slice(0, 15).join('\n') +
               (check.errors.length > 15 ? '\n…and ' + (check.errors.length - 15) + ' more.' : ''));
      return;
    }
    if (check.warnings.length &&
        ui.alert('Check before publishing', check.warnings.join('\n') + '\n\nPublish anyway?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
    var who = Session.getActiveUser().getEmail() || 'unknown';
    tab_('History').appendRow([new Date(), who, JSON.stringify(liveVals)]);
    var rows = draft.filter(function (r, i) { return i === 0 || r.join('').trim() !== ''; });
    live.clearContents();
    live.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
    tab_('Log').appendRow([new Date(), who, 'Published', (rows.length - 1) + ' people (was ' + Math.max(liveVals.length - 1, 0) + ')']);
    ui.alert('Published ' + (rows.length - 1) + ' people. The class sites update within a day, or sooner if Ahin runs the deploy.');
  } finally {
    lock.releaseLock();
  }
}

function undoLastPublish() {
  var ui = SpreadsheetApp.getUi(), hist = tab_('History'), n = hist.getLastRow();
  if (n < 2) { ui.alert('Nothing to undo.'); return; }
  var prev = JSON.parse(hist.getRange(n, 3).getValue()), live = tab_('Live');
  if (ui.alert('Undo', 'Put back the version from ' + hist.getRange(n, 1).getValue() + '?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  live.clearContents();
  if (prev.length) live.getRange(1, 1, prev.length, prev[0].length).setValues(prev);
  hist.deleteRow(n);
  tab_('Log').appendRow([new Date(), Session.getActiveUser().getEmail() || 'unknown', 'Undo', 'Restored ' + Math.max(prev.length - 1, 0) + ' people']);
  ui.alert('Done. Live is back to the previous version.');
}

function setUp() {
  var ss = SpreadsheetApp.getActive();
  var spec = {Draft: COLUMNS, Live: COLUMNS, Log: ['When', 'Who', 'Action', 'Details'], History: ['When', 'Who', 'Previous Live (JSON)']};
  Object.keys(spec).forEach(function (name) {
    var t = ss.getSheetByName(name) || ss.insertSheet(name);
    if (!t.getLastRow()) t.appendRow(spec[name]);
    t.setFrozenRows(1);
  });
  ['Live', 'Log', 'History'].forEach(function (name) {
    var t = ss.getSheetByName(name);
    t.getProtections(SpreadsheetApp.ProtectionType.SHEET).forEach(function (p) { p.remove(); });
    var p = t.protect().setDescription(name + ': changed only by the Publish menu');
    p.removeEditors(p.getEditors());
    if (PUBLISHERS.length) p.addEditors(PUBLISHERS);
  });
  SpreadsheetApp.getUi().alert('Tabs ready. Only the sheet owner' + (PUBLISHERS.length ? ' and ' + PUBLISHERS.join(', ') : '') + ' can publish.');
}
