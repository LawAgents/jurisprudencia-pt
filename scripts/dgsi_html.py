"""Parsers for the HTML of dgsi.pt (Lotus Domino): listing pages and decision pages. Standard library only.

Pages are latin-1 without a charset declaration (one page of the measurement also had cp1252 bytes in 0x80-0x9f, so cp1252
is tried first and latin-1 is the fallback), and use numeric entities for characters outside latin-1.
"""
import html
import re
from datetime import date

from common import fold

# Label cells (first column of the field table) have a coloured background and a width of 23% to 26%; the colour changes
# with the page (#71B2CF, #99CC99 for Julgados de Paz, #6699CC for some secondary fields). White cells are spacers.
CELL_RE = re.compile(r'<td([^>]*bgcolor="#(?!FFFFFF)[0-9A-Fa-f]{6}"[^>]*)>(.*?)</td>', re.S | re.I)
LABEL_COLORS = ("71B2CF", "99CC99", "6699CC")
ROW_LINK_RE = re.compile(r'href="(/([a-z0-9]+)\.nsf/([0-9a-f]{32})/([0-9a-f]{32}))\?OpenDocument"', re.I)
NEXT_RE = re.compile(r'<a href="([^"]*)">\s*<b><font[^>]*>Seguinte<', re.I)
US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
SIZE_ONLY = re.compile(r"^\d+\s*kB$", re.I)


def decode(raw):
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def us_date(s):
    """Domino shows month/day/year ('10/20/2026'). Returns ISO or None."""
    m = US_DATE.match((s or "").strip())
    if not m:
        return None
    mo, d, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def text_lines(fragment):
    """Visible text of an HTML fragment as a list of lines: <br>, <p>, </p>, <div> and </div> start a new line, tags are
    dropped, entities decoded, runs of white space collapsed. Empty lines are dropped."""
    f = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    f = re.sub(r"\s+", " ", f)
    f = re.sub(r"<br\s*/?>|</?p\b[^>]*>|</?div\b[^>]*>|</tr>|</li>", "\n", f, flags=re.I)
    f = html.unescape(re.sub(r"<[^>]+>", "", f)).replace("\xa0", " ")
    lines = (re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in f.split("\n"))
    return [ln for ln in lines if ln]


def one_line(fragment):
    return " ".join(text_lines(fragment))


def label_key(cell_html):
    return re.sub(r"[^a-z0-9]+", " ", fold(one_line(cell_html))).strip()


def _is_label(attrs):
    color = re.search(r'bgcolor="#(\w{6})"', attrs, re.I).group(1).upper()
    return color in LABEL_COLORS or re.search(r'width="2\d%"', attrs, re.I) is not None


def parse_fields(raw):
    """{folded label: HTML fragment of its value} of a decision page. The first occurrence of a label wins."""
    t = decode(raw) if isinstance(raw, bytes) else raw
    labs = [(m, label_key(m.group(2))) for m in CELL_RE.finditer(t) if _is_label(m.group(1))]
    out = {}
    for i, (m, key) in enumerate(labs):
        if not key:
            continue
        end = labs[i + 1][0].start() if i + 1 < len(labs) else len(t)
        out.setdefault(key, t[m.end():end])
    return out


def page_ok(raw):
    """A decision page: complete HTML with a Processo field."""
    return b"</html>" in raw[-2048:].lower() and "processo" in parse_fields(raw)


def list_ok(raw):
    return b"</html>" in raw[-2048:].lower()


def parse_list(raw):
    """(rows, next_url) of a listing page. Row: unid, path (/db.nsf/view/unid), db, processo, relator, descritores
    (list), data (ISO or None). `next_url` is the 'Seguinte' link (path and query) or None."""
    t = decode(raw) if isinstance(raw, bytes) else raw
    headers = [label_key(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S | re.I)]
    rows = []
    for chunk in t.split("<tr")[1:]:
        m = ROW_LINK_RE.search(chunk)
        if not m:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.S | re.I)
        link_i = next(i for i, c in enumerate(cells) if ROW_LINK_RE.search(c))
        aligned = len(headers) == len(cells)
        proc = one_line(cells[link_i])
        data = next((d for d in (us_date(one_line(c)) for c in cells) if d), None)
        if aligned:
            rel_i = next((i for i, h in enumerate(headers) if h.startswith("relator")), None)
            des_i = next((i for i, h in enumerate(headers) if h.startswith("descrit")), None)
        else:  # the Tribunal Constitucional list has no header: date, link, descritor
            rel_i, des_i = None, link_i + 1
        rows.append({
            "unid": m.group(4), "path": m.group(1), "db": m.group(2),
            "processo": "" if SIZE_ONLY.match(proc) else proc,
            "relator": one_line(cells[rel_i]) if rel_i is not None and rel_i < len(cells) else "",
            "descritores": text_lines(cells[des_i]) if des_i is not None and des_i < len(cells) else [],
            "data": data,
        })
    nm = NEXT_RE.search(t)
    return rows, (html.unescape(nm.group(1)) if nm else None)
