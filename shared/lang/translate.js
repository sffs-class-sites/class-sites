/* SFFS shared embeds: a translation notice for viewers whose browser is not set to English.
 *
 * Every embed is written in English with lang="en", so Chrome, Safari and Edge offer their own
 * translation. An embed cannot start that itself; what it can do is, when the viewer's first
 * (preferred) language in navigator.languages is not English, show one line in that language with
 * a link that opens this same page through Google Translate in a new tab (works in every browser,
 * inside the Sites iframe). Only the first entry counts: a browser listing English first and
 * another language after it belongs to someone who reads English (2026-11-02, Ahin saw a
 * Portuguese notice that way). The viewer can dismiss it; the choice is remembered in this
 * browser only.
 */
(function () {
  var KEY = 'sffsLangDismiss';
  function safeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var langs = (navigator.languages && navigator.languages.length) ? navigator.languages : [navigator.language || 'en'];
  var first = String(langs[0] || 'en');
  var code = first.toLowerCase().split('-')[0];
  if (!code || code === 'en' || safeGet(KEY) === code) return;
  var pick = {tag: first, code: code};
  var wrap = document.getElementById('wrap') || document.body;
  var name = pick.code;
  try { name = new Intl.DisplayNames([pick.tag], {type: 'language'}).of(pick.code) || pick.code; } catch (e) {}
  name = name.charAt(0).toUpperCase() + name.slice(1);
  var pageUrl = location.origin + location.pathname + location.search;
  var href = 'https://translate.google.com/translate?sl=en&tl=' + encodeURIComponent(pick.code) + '&u=' + encodeURIComponent(pageUrl);
  var css = document.createElement('style');
  css.textContent = '.sffs-lang{display:flex;align-items:center;gap:8px;margin:0 0 8px;padding:6px 10px;border:1px solid #d6dff5;border-radius:999px;background:#eaeffb;font:600 .8rem/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1f2937}' +
    '.sffs-lang a{color:#3457a6;text-decoration:none;white-space:nowrap}.sffs-lang a:hover{text-decoration:underline}' +
    '.sffs-lang button{margin-left:auto;border:0;background:transparent;color:#5b6472;font:inherit;font-size:1rem;line-height:1;cursor:pointer;padding:0 2px}' +
    '@media (max-width:560px){.sffs-lang{font-size:.74rem;padding:5px 9px;margin-bottom:5px}}';
  document.head.appendChild(css);
  var box = document.createElement('div');
  box.className = 'sffs-lang'; box.setAttribute('lang', pick.tag); box.setAttribute('role', 'note');
  var a = document.createElement('a');
  a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
  a.textContent = '🌐 ' + name + ' ↗';
  a.title = 'Google Translate';
  var x = document.createElement('button');
  x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Dismiss');
  x.addEventListener('click', function () { safeSet(KEY, pick.code); box.remove(); });
  box.appendChild(a); box.appendChild(x);
  wrap.insertBefore(box, wrap.firstChild);
})();
