/* SFFS class and grade model (CLAUDE.md section 1). Inlined into every shared embed by build/classinfo.py,
   with the rows of shared/school-years.json in place of __SCHOOL_YEARS__. build/classinfo.py mirrors
   this logic in Python; tests/test_classinfo.py and tests/render_check.py keep the two in step.

   A site follows a class (its graduation year, ?class=2034), never a grade. The grade is worked out
   at view time: grade = 8 - (gradYear - schoolYearEndYear). Kindergarten is grade 0.
   The school year rolls over the day after the last day of school. ?grade=N previews another grade. */
var SFFS = (function () {
  var YEARS = __SCHOOL_YEARS__;
  var ORD = ['Kindergarten', '1st grade', '2nd grade', '3rd grade', '4th grade', '5th grade', '6th grade', '7th grade', '8th grade'];

  function ymd(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }

  /* The school year a date falls in. Rollover is the last day of school: through that day the
     year is still on; from the next day the following year has begun (summer counts as next year). */
  function schoolYear(today) {
    var y = today.getFullYear(), guess = today.getMonth() >= 6 ? y + 1 : y;  // July onward: the year ending next calendar year
    var known = null;
    for (var i = 0; i < YEARS.length; i++) if (YEARS[i].end_year === guess) known = YEARS[i];
    if (!known) return { end_year: guess, label: (guess - 1) + '–' + String(guess).slice(2), assumed: true };
    if (today <= ymd(known.last_day)) return { end_year: known.end_year, label: known.label, assumed: false };
    var next = guess + 1;
    return { end_year: next, label: (next - 1) + '–' + String(next).slice(2), assumed: true };
  }

  function grade(gradYear, endYear) { return 8 - (gradYear - endYear); }

  function gradeName(g) {
    if (g < 0) return 'not yet at SFFS';
    if (g > 8) return 'graduated';
    return ORD[g];
  }

  /* Everything an embed needs from its address: ?class=YYYY, optional ?grade=N (preview) and
     ?today=YYYY-MM-DD (tests). Returns {cls, year, grade, gradeName, status, preview, heading}. */
  function classInfo(search, today) {
    var m = /[?&]class=(\d{4})(?:&|$)/.exec(search || '');
    var g = /[?&]grade=(\d)(?:&|$)/.exec(search || '');
    var t = /[?&]today=(\d{4}-\d{2}-\d{2})(?:&|$)/.exec(search || '');
    today = today || (t ? ymd(t[1]) : new Date());
    today = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    var year = schoolYear(today);
    if (!m) return { cls: null, year: year, grade: null, gradeName: null, status: 'none', preview: false, heading: '' };
    var cls = +m[1], gr = g ? +g[1] : grade(cls, year.end_year), preview = !!g;
    var status = gr < 0 ? 'future' : gr > 8 ? 'alumni' : 'ok';
    var heading = status === 'ok' ? gradeName(gr) + ' · Class of ' + cls : 'Class of ' + cls + ' · ' + gradeName(gr);
    if (preview) heading += ' (preview)';
    if (year.assumed && window.console) console.warn('SFFS: no row for the school year ending ' + year.end_year + ' in school-years.json; assuming it ends June 30.');
    return { cls: cls, year: year, grade: gr, gradeName: gradeName(gr), status: status, preview: preview, heading: heading };
  }

  return { YEARS: YEARS, schoolYear: schoolYear, grade: grade, gradeName: gradeName, classInfo: classInfo };
})();
