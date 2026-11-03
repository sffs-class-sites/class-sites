"""Shared check for the translation notice (shared/lang/translate.js) that every embed inlines.

check_lang(browser, url, check): a Spanish-first browser sees a one-line notice in Spanish whose
link opens this page through Google Translate in a new tab; dismissing it sticks for that
browser; an English browser sees nothing, and neither does a browser that lists English first
and another language after it (only the first, preferred language counts)."""


def check_lang(browser, url, check, label=""):
    tag = f"{label}: " if label else ""
    ctx = browser.new_context(viewport={"width": 700, "height": 600}, locale="es-MX")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_timeout(300)
    m = page.evaluate("""() => { const b = document.querySelector('.sffs-lang'), a = b && b.querySelector('a');
        return b ? {lang: b.getAttribute('lang'), text: a.textContent, href: a.href, target: a.target, rel: a.rel, first: document.getElementById('wrap').firstElementChild === b} : null; }""")
    check(m is not None and m["lang"] == "es-MX" and "Español" in m["text"], f"{tag}a Spanish-first browser sees the notice in Spanish ({m and m['text']!r})")
    check(m is not None and m["href"].startswith("https://translate.google.com/translate?sl=en&tl=es&u=") and url.split("?")[0] in m["href"].replace("%3A", ":").replace("%2F", "/")
          and m["target"] == "_blank" and "noopener" in m["rel"], f"{tag}the link opens this page through Google Translate in a new tab")
    check(m is not None and m["first"], f"{tag}the notice sits at the top of the embed")
    page.locator(".sffs-lang button").click()
    page.reload()
    page.wait_for_timeout(300)
    check(page.evaluate("() => !document.querySelector('.sffs-lang')"), f"{tag}dismissing the notice sticks for this browser")
    ctx.close()
    ctx = browser.new_context(viewport={"width": 700, "height": 600}, locale="en-US")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_timeout(300)
    check(page.evaluate("() => !document.querySelector('.sffs-lang')"), f"{tag}an English browser sees no notice")
    ctx.close()
    # Playwright's locale gives navigator.languages one entry; Chrome lists every language the
    # viewer added, preferred first, so set the list by hand.
    ctx = browser.new_context(viewport={"width": 700, "height": 600}, locale="en-US")
    ctx.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'pt-BR']})")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_timeout(300)
    check(page.evaluate("() => !document.querySelector('.sffs-lang')"), f"{tag}English first with Portuguese after it: no notice")
    ctx.close()
