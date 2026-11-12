"""House style for text shown in the embeds (Ahin, 2026-11-12).

After a colon, the next word starts with a capital letter: "Tuition and fees: Every SFFS bill ...",
not "...: every SFFS bill". Times ("8:30") and links ("https://") are untouched, since the rule only
looks at a colon followed by whitespace and then a lowercase letter.

Text quoted from elsewhere is exempt: an email's subject line in the Updates ledger is the key the
build uses to link to that email's full text, so it must stay exactly as the email had it.

Used by every embed's data check (the build or validator refuses text that breaks the rule) and by
tests/style_check.py, which reads the rendered pages, so wording in the page templates is held to it too.
"""
import re

AFTER_COLON = re.compile(r"(:\s+)([a-z])")


def colon_issues(text):
    """Each place in `text` where a colon is followed by a lowercase letter, as a short quoted snippet."""
    return [repr(text[max(0, m.start() - 25):m.end() + 15]) for m in AFTER_COLON.finditer(text or "")]


def fix_after_colon(text):
    """`text` with the first letter after each colon capitalised."""
    return AFTER_COLON.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def walk_strings(obj, path="", skip=()):
    """Yield (path, string) for every string in a JSON-like object, leaving out keys in `skip` and keys
    starting with "_" (notes to editors)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip or str(k).startswith("_"):
                continue
            yield from walk_strings(v, f"{path}.{k}" if path else k, skip)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]", skip)
    elif isinstance(obj, str):
        yield path, obj


def starts_lowercase(text):
    """True when `text` begins with a lowercase letter. For a field the page prints after its own colon
    ("Drop-off: " + text, "Due Oct 28: " + what), where the colon is in the template and not in the data."""
    return bool(text) and text[0].islower()


# Keys that hold identifiers, links or quoted text rather than our own wording.
NOT_PROSE = {"url", "href", "uid", "id", "source", "sources", "subject", "stream", "dtstamp", "pdf_url", "ics"}


def data_issues(obj, skip=NOT_PROSE):
    """Every rule break in a data file's prose, as 'path: snippet' lines (empty when clean)."""
    return [f"{p}: {s}" for p, t in walk_strings(obj, skip=skip) for s in colon_issues(t)]
