"""Shared text utilities for the content-fact-auditor scripts.

Python 3.9+ standard library only. No network access.

Responsibilities:
  * load_document(path, fmt)  -> visible text blocks + hidden text (HTML comments, hidden elements)
  * split_sentences(text, lang)
  * extract_values(text)      -> prices, times, dates, percents, quantities (normalized)
  * key_terms(text)           -> entity terms and attribute terms used for matching
"""

import re
import unicodedata
from html.parser import HTMLParser

SUPPORTED_FORMATS = ("md", "html", "txt")

# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------


def norm(text):
    """NFKC (full-width digits/letters to ASCII), unify dashes and tildes, collapse spaces."""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    t = t.replace("\u301c", "~").replace("\uff5e", "~")
    t = re.sub(r"[ \t\u3000]+", " ", t)
    return t.strip()


def fold(text):
    return norm(text).casefold()


JA_CHAR = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\u3005]")
LATIN_CHAR = re.compile(r"[A-Za-z]")


def detect_lang(text):
    ja = len(JA_CHAR.findall(text))
    la = len(LATIN_CHAR.findall(text))
    if ja == 0 and la == 0:
        return "en"
    return "ja" if ja >= 0.2 * (ja + la) else "en"


# --------------------------------------------------------------------------
# Document loading
# --------------------------------------------------------------------------

BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "main", "aside", "nav",
    "li", "ul", "ol", "dl", "dt", "dd", "tr", "table", "thead", "tbody", "tfoot",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "blockquote", "pre", "figure",
    "figcaption", "form", "fieldset", "address", "details", "summary", "caption",
}
CELL_TAGS = {"td", "th"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
}
DROP_TAGS = {"script", "style"}          # never visible, not reported
HIDDEN_TAGS = {"template", "noscript"}   # not shown to normal readers, reported
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


def _is_hidden(tag, attrs):
    if tag in HIDDEN_TAGS:
        return True
    d = {k.lower(): (v or "") for k, v in attrs}
    if "hidden" in d:
        return True
    if HIDDEN_STYLE.search(d.get("style", "")):
        return True
    if tag == "input" and d.get("type", "").lower() == "hidden":
        return True
    return False


class _HTMLExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []        # dicts: line, text, heading
        self.hidden = []        # dicts: kind, line, text
        self._buf = []
        self._buf_line = None
        self._heading = 0
        self._stack = []        # [tag, mode] mode in {"", "drop", "hidden"}
        self._hidden_buf = None  # [line, tag, [texts], depth_index]

    # helpers
    def _mode(self):
        for tag, mode in reversed(self._stack):
            if mode:
                return mode
        return ""

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.blocks.append({"line": self._buf_line or 1, "text": text, "heading": self._heading})
        self._buf = []
        self._buf_line = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCK_TAGS:
            self._flush()
        if tag in CELL_TAGS and self._buf:
            self._buf.append(" | ")
        if re.fullmatch(r"h[1-6]", tag) or tag == "title":
            self._flush()
            self._heading = int(tag[1]) if tag != "title" else 1
        if tag in VOID_TAGS:
            if tag == "img" and self._mode() == "":
                alt = dict(attrs).get("alt")
                if alt:
                    self.handle_data(" " + alt + " ")
            return
        mode = ""
        if tag in DROP_TAGS:
            mode = "drop"
        elif _is_hidden(tag, attrs) and self._mode() == "":
            mode = "hidden"
            self._hidden_buf = [self.getpos()[0], tag, [], len(self._stack)]
        self._stack.append([tag, mode])

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID_TAGS:
            return
        # pop to the matching tag (tolerates unclosed children)
        idx = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                idx = i
                break
        if idx is not None:
            if self._hidden_buf is not None and idx <= self._hidden_buf[3]:
                text = re.sub(r"\s+", " ", "".join(self._hidden_buf[2])).strip()
                if text:
                    self.hidden.append({
                        "kind": "hidden-element",
                        "line": self._hidden_buf[0],
                        "tag": self._hidden_buf[1],
                        "text": text,
                    })
                self._hidden_buf = None
            del self._stack[idx:]
        if tag in BLOCK_TAGS or re.fullmatch(r"h[1-6]", tag) or tag == "title":
            self._flush()
        if re.fullmatch(r"h[1-6]", tag) or tag == "title":
            self._heading = 0

    def handle_data(self, data):
        mode = self._mode()
        if mode == "drop":
            return
        if mode == "hidden":
            if self._hidden_buf is not None:
                self._hidden_buf[2].append(data)
            return
        if not self._buf and not data.strip():
            return
        if self._buf_line is None and data.strip():
            # getpos() is the start of this data chunk; skip leading newlines
            lead = len(data) - len(data.lstrip("\n\r "))
            self._buf_line = self.getpos()[0] + data[:lead].count("\n")
        self._buf.append(data)

    def handle_comment(self, data):
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.hidden.append({"kind": "html-comment", "line": self.getpos()[0], "text": text})

    def close(self):
        super().close()
        self._flush()


def _load_html(raw):
    p = _HTMLExtractor()
    p.feed(raw)
    p.close()
    return p.blocks, p.hidden


_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
_DROP_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_HIDDEN_EL_RE = re.compile(
    r"<(\w+)\b([^>]*(?:\shidden\b|display\s*:\s*none|visibility\s*:\s*hidden)[^>]*)>(.*?)</\1\s*>",
    re.S | re.I,
)
_TAG_RE = re.compile(r"<[^>\n]+>")


def _line_of(raw, pos):
    return raw.count("\n", 0, pos) + 1


def _blank_keep_lines(m):
    return re.sub(r"[^\n]", "", m.group(0))


def _clean_md_line(line):
    s = line
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"^\s{0,3}>\s?", "", s)
    s = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?", "", s)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)\*(?!\w)", r"\1", s)
    if re.match(r"^\s*\|", s):
        if re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", s):
            return ""
        s = " | ".join(c.strip() for c in s.strip().strip("|").split("|"))
    return s.strip()


def _load_text(raw, fmt):
    hidden = []
    for m in _COMMENT_RE.finditer(raw):
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        if text:
            hidden.append({"kind": "html-comment", "line": _line_of(raw, m.start()), "text": text})
    raw2 = _COMMENT_RE.sub(_blank_keep_lines, raw)
    raw2 = _DROP_RE.sub(_blank_keep_lines, raw2)

    def _hide(m):
        text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", m.group(3))).strip()
        if text:
            hidden.append({"kind": "hidden-element", "line": _line_of(raw2, m.start()),
                           "tag": m.group(1).lower(), "text": text})
        return _blank_keep_lines(m)

    raw2 = _HIDDEN_EL_RE.sub(_hide, raw2)
    raw2 = _TAG_RE.sub(" ", raw2)
    lines = raw2.split("\n")

    # front matter: keep only title/description values (title is treated like a heading)
    front = []
    if fmt == "md" and lines and lines[0].strip() == "---":
        for j in range(1, min(len(lines), 200)):
            if lines[j].strip() == "---":
                for k in range(0, j + 1):
                    mm = re.match(r"^(title|description)\s*:\s*(.*)$", lines[k])
                    if mm and mm.group(2).strip().strip("'\""):
                        front.append({"line": k + 1, "text": mm.group(2).strip().strip("'\""),
                                      "heading": 1 if mm.group(1) == "title" else 0})
                    lines[k] = ""
                break

    blocks = list(front)
    in_fence = False
    para = None  # [line, [texts]]

    def end_para():
        nonlocal para
        if para and "".join(para[1]).strip():
            blocks.append({"line": para[0], "text": " ".join(para[1]).strip(), "heading": 0})
        para = None

    for i, line in enumerate(lines, start=1):
        if fmt == "md" and re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            end_para()
            continue
        if in_fence:
            continue
        if not line.strip():
            end_para()
            continue
        h = re.match(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line) if fmt == "md" else None
        if h:
            end_para()
            blocks.append({"line": i, "text": _clean_md_line(h.group(2)), "heading": len(h.group(1))})
            continue
        cleaned = _clean_md_line(line) if fmt == "md" else line.strip()
        if not cleaned:
            end_para()
            continue
        is_item = bool(re.match(r"^\s*(?:[-*+]|\d+[.)]|\|)\s*", line)) or fmt == "txt"
        if is_item:
            end_para()
            blocks.append({"line": i, "text": cleaned, "heading": 0})
            continue
        if para is None:
            para = [i, [cleaned]]
        else:
            para[1].append(cleaned)
        if re.search(r"[。！？.!?」]$", cleaned):
            end_para()
    end_para()
    return blocks, hidden


def guess_format(path):
    p = path.lower()
    if p.endswith((".html", ".htm", ".xhtml")):
        return "html"
    if p.endswith((".md", ".markdown", ".mdx")):
        return "md"
    if p.endswith(".txt"):
        return "txt"
    return None


def read_text_file(path):
    with open(path, "rb") as f:
        data = f.read()
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    for enc in ("cp932", "euc_jp", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def load_document(path, fmt="auto"):
    """Return (blocks, hidden, fmt). Raises ValueError with an actionable message."""
    if fmt in (None, "auto"):
        fmt = guess_format(path)
        if fmt is None:
            raise ValueError(
                "Cannot tell the format of %r from its extension. "
                "Use .md, .html or .txt, or pass --format md|html|txt." % path)
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported --format %r; expected one of md, html, txt." % fmt)
    raw = read_text_file(path)
    if not raw.strip():
        raise ValueError("Input file %r is empty." % path)
    if fmt == "html":
        blocks, hidden = _load_html(raw)
    else:
        blocks, hidden = _load_text(raw, fmt)
    return blocks, hidden, fmt


# --------------------------------------------------------------------------
# Sentence splitting
# --------------------------------------------------------------------------

EN_ABBREV = {
    "no", "mr", "mrs", "ms", "dr", "st", "vs", "e.g", "i.e", "etc", "approx", "jan", "feb",
    "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "mt", "ave",
    "inc", "ltd", "co", "u.s", "u.k", "fig", "vol", "est", "min", "max", "ft",
}


def split_sentences(text, lang="auto"):
    """Split a block into sentences. Japanese: 。！？ ; English: . ! ? + space + capital/digit."""
    out = []
    start = 0
    n = len(text)
    i = 0
    depth = 0  # inside 「」『』 quotes we do not split
    while i < n:
        ch = text[i]
        cut = None
        if ch in "「『":
            depth += 1
        elif ch in "」』" and depth:
            depth -= 1
        if depth:
            i += 1
            continue
        if lang in ("auto", "ja") and ch in "。！？":
            j = i + 1
            while j < n and text[j] in "」』）)":
                j += 1
            cut = j
        elif lang in ("auto", "en") and ch in ".!?":
            j = i + 1
            while j < n and text[j] in "\"'”’)":
                j += 1
            if j < n and text[j] == " ":
                k = j
                while k < n and text[k] == " ":
                    k += 1
                if k < n and (text[k].isupper() or text[k].isdigit() or text[k] in "\"“(['$¥€£"
                              or JA_CHAR.match(text[k])):
                    word = re.search(r"([A-Za-z.]+)$", text[start:i])
                    w = (word.group(1).lower().rstrip(".") if word else "")
                    if ch != "." or w not in EN_ABBREV:
                        if not (ch == "." and re.search(r"\b[A-Z]$", text[start:i])):
                            cut = j
        if cut is not None:
            s = text[start:cut].strip()
            if s:
                out.append(s)
            start = cut
            i = cut
            continue
        i += 1
    s = text[start:].strip()
    if s:
        out.append(s)
    return out


# --------------------------------------------------------------------------
# Value extraction
# --------------------------------------------------------------------------

NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"


def _num(s):
    return float(s.replace(",", ""))


_PRICE_RANGE_JPY = re.compile(r"(?P<a>%s)\s?(?:円)?\s?[~\-]\s?(?P<b>%s)\s?(?P<man>万)?\s?円" % (NUM, NUM))
_PRICE_JPY = re.compile(r"(?P<num>%s)\s?(?P<man>万|千)?\s?円" % NUM)
_PRICE_PREFIX = re.compile(
    r"(?P<cur>US\$|C\$|A\$|[¥$€£])\s?(?P<num>%s)(?:\s?(?P<suf>k|K|million|万))?"
    r"(?:\s?[-~]\s?(?:US\$|C\$|A\$|[¥$€£])?\s?(?P<num2>%s))?" % (NUM, NUM))
_PRICE_WORD = re.compile(
    r"(?P<num>%s)\s?(?P<w>dollars?|yen|euros?|pounds?|USD|JPY|EUR|GBP|CAD|AUD)\b" % NUM, re.I)
_PRICE_FREE = re.compile(
    r"\b(?:free of charge|free admission|free entry|admission is free|entry is free|"
    r"(?:is|are) free(?! to| of\b)|for free|get in free|gets in free|enter (?:for )?free|go free|"
    r"free for (?:kids|children|toddlers|babies|infants|under|ages?|seniors))\b|(?<=:)\s?free\b|\bfree\s*$|無料", re.I)

_CUR = {"¥": "JPY", "$": "USD", "US$": "USD", "C$": "CAD", "A$": "AUD", "€": "EUR", "£": "GBP",
        "dollar": "USD", "dollars": "USD", "yen": "JPY", "euro": "EUR", "euros": "EUR",
        "pound": "GBP", "pounds": "GBP", "usd": "USD", "jpy": "JPY", "eur": "EUR", "gbp": "GBP",
        "cad": "CAD", "aud": "AUD"}

_TIME_HM = re.compile(r"(?<![\d:])(?P<h>\d{1,2}):(?P<m>\d{2})(?![\d:])\s?(?P<ap>[ap]\.?\s?m\.?)?", re.I)
_TIME_H_AP = re.compile(r"(?<![\d:.])(?P<h>\d{1,2})\s?(?P<ap>[ap]\.?m\.?)(?![a-z])", re.I)
_TIME_JA = re.compile(r"(?P<h>\d{1,2})時(?!間)(?:(?P<m>\d{1,2})分|(?P<half>半))?")
_DATE_JA = re.compile(r"(?P<y>(?:19|20)\d{2})年(?:(?P<mo>\d{1,2})月(?:(?P<d>\d{1,2})日)?)?")
_DATE_JA_MD = re.compile(r"(?<![\d年])(?P<mo>\d{1,2})月(?P<d>\d{1,2})日")
_DATE_ISO = re.compile(r"(?<!\d)(?P<y>(?:19|20)\d{2})[-/.](?P<mo>\d{1,2})[-/.](?P<d>\d{1,2})(?!\d)")
_DATE_SLASH_MD = re.compile(r"(?<![\d/.:,])(?P<mo>\d{1,2})/(?P<d>\d{1,2})(?![\d/.%])")
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
           "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_DATE_EN = re.compile(
    r"\b(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,?\s+(?P<y>(?:19|20)\d{2}))?\b")
_DATE_EN_MY = re.compile(
    r"\b(?P<mon>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<y>(?:19|20)\d{2})\b")
_YEAR = re.compile(r"(?<![\d,.$¥€£])(?P<y>(?:19|20)\d{2})(?![\d,]|\s?(?:円|yen|dollars))")
_PERCENT = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s?(?:%|percent\b|per cent\b|パーセント)", re.I)
_WARI = re.compile(r"(?P<num>\d+(?:\.\d+)?)割(?!引)")

_QTY_UNITS = [
    # (regex for unit, normalized unit)
    (r"minutes?|mins?\b", "min"), (r"hours?|hrs?\b", "h"), (r"時間", "h"), (r"分(?!の)", "min"),
    (r"kilometers?|kilometres?|km\b", "km"), (r"meters?|metres?|m\b|メートル", "m"),
    (r"miles?\b", "mi"), (r"feet\b|ft\b", "ft"), (r"cm\b|センチ", "cm"), (r"mm\b", "mm"),
    (r"kg\b|キロ(?:グラム)?", "kg"), (r"g\b|グラム", "g"), (r"m2\b|sq\.? ?m\b|平米", "m2"),
    (r"坪", "tsubo"), (r"acres?\b", "acre"), (r"hectares?|ha\b|ヘクタール", "ha"),
    (r"seats?\b|席", "seat"), (r"parking (?:spaces?|spots?)|spaces?\b|spots?\b", "space"),
    (r"台", "unit-dai"), (r"rooms?\b|室|部屋", "room"), (r"floors?\b|階|F\b", "floor"),
    (r"stores?\b|shops?\b|locations?\b|branches\b|店舗|店(?!員)|軒", "store"),
    (r"years? old\b|歳|才", "age"), (r"months? old\b|か月|ヶ月|カ月", "month"),
    (r"people\b|persons?\b|visitors\b|guests\b|人|名", "person"),
    (r"species\b|種類?", "species"), (r"animals\b|頭|匹|羽", "animal"),
    (r"items?\b|個|点|品", "item"), (r"件", "case"), (r"本", "count-hon"), (r"枚", "sheet"),
    (r"times\b|回", "times"), (r"days?\b|日間", "day"), (r"weeks?\b|週間", "week"),
    (r"years?\b|年間", "year"),
]
_QTY = re.compile(
    r"(?P<num>%s)\s?(?P<unit>%s)" % (NUM, "|".join("(?:%s)" % u for u, _ in _QTY_UNITS)), re.I)


def _qty_unit(raw_unit):
    for pat, name in _QTY_UNITS:
        if re.fullmatch("(?:%s)" % pat, raw_unit, re.I):
            return name
    return raw_unit.lower()


def _minutes(h, m, ap, pre):
    h = int(h)
    m = int(m or 0)
    if ap:
        a = ap.lower().replace(".", "").replace(" ", "")
        if a == "pm" and h < 12:
            h += 12
        if a == "am" and h == 12:
            h = 0
    elif pre and re.search(r"午後|夜|PM|pm", pre) and h < 12:
        h += 12
    return h * 60 + m


def _date_value(y, mo, d):
    return "%s-%s-%s" % (y or "XXXX", ("%02d" % int(mo)) if mo else "XX", ("%02d" % int(d)) if d else "XX")


def extract_values(text):
    """Return a list of {kind, raw, value, unit} from text (normalized with NFKC first).

    kinds: price, time, date, percent, quantity. Year-only dates have kind 'date' and
    'year_only': True (they are not used to decide contradictions).
    """
    t = norm(text)
    taken = []
    out = []

    def free(a, b):
        return all(b <= s or a >= e for s, e in taken)

    def add(m, item, span=None):
        a, b = span or m.span()
        if not free(a, b):
            return False
        taken.append((a, b))
        item["raw"] = t[a:b]
        out.append(item)
        return True

    for m in _PRICE_RANGE_JPY.finditer(t):
        mul = 10000 if m.group("man") else 1
        if free(*m.span()):
            taken.append(m.span())
            out.append({"kind": "price", "raw": m.group(0), "value": _num(m.group("a")) * mul, "unit": "JPY"})
            out.append({"kind": "price", "raw": m.group(0), "value": _num(m.group("b")) * mul, "unit": "JPY"})
    for m in _PRICE_JPY.finditer(t):
        mul = {"万": 10000, "千": 1000}.get(m.group("man") or "", 1)
        add(m, {"kind": "price", "value": _num(m.group("num")) * mul, "unit": "JPY"})
    for m in _PRICE_PREFIX.finditer(t):
        suf = (m.group("suf") or "").lower()
        mul = {"k": 1000, "million": 1000000, "万": 10000}.get(suf, 1)
        unit = _CUR.get(m.group("cur"), m.group("cur"))
        if add(m, {"kind": "price", "value": _num(m.group("num")) * mul, "unit": unit}) and m.group("num2"):
            out.append({"kind": "price", "raw": m.group(0), "value": _num(m.group("num2")) * mul, "unit": unit})
    for m in _PRICE_WORD.finditer(t):
        add(m, {"kind": "price", "value": _num(m.group("num")), "unit": _CUR.get(m.group("w").lower(), m.group("w").upper())})
    for m in _PRICE_FREE.finditer(t):
        add(m, {"kind": "price", "value": 0.0, "unit": None})

    for m in _TIME_HM.finditer(t):
        pre = t[max(0, m.start() - 4):m.start()]
        add(m, {"kind": "time", "value": _minutes(m.group("h"), m.group("m"), m.group("ap"), pre), "unit": "min"})
    for m in _TIME_H_AP.finditer(t):
        add(m, {"kind": "time", "value": _minutes(m.group("h"), 0, m.group("ap"), ""), "unit": "min"})
    for m in _TIME_JA.finditer(t):
        pre = t[max(0, m.start() - 4):m.start()]
        mm = 30 if m.group("half") else m.group("m")
        add(m, {"kind": "time", "value": _minutes(m.group("h"), mm, None, pre), "unit": "min"})

    for rx in (_DATE_ISO, _DATE_JA):
        for m in rx.finditer(t):
            gd = m.groupdict()
            if gd.get("mo") and not 1 <= int(gd["mo"]) <= 12:
                continue
            item = {"kind": "date", "value": _date_value(gd.get("y"), gd.get("mo"), gd.get("d")), "unit": None}
            if not gd.get("mo"):
                item["year_only"] = True
            add(m, item)
    for m in _DATE_JA_MD.finditer(t):
        if 1 <= int(m.group("mo")) <= 12 and 1 <= int(m.group("d")) <= 31:
            add(m, {"kind": "date", "value": _date_value(None, m.group("mo"), m.group("d")), "unit": None})
    for m in _DATE_EN.finditer(t):
        mo = _MONTHS[m.group("mon")[:3].lower()]
        if 1 <= int(m.group("d")) <= 31:
            add(m, {"kind": "date", "value": _date_value(m.group("y"), mo, m.group("d")), "unit": None})
    for m in _DATE_EN_MY.finditer(t):
        add(m, {"kind": "date", "value": _date_value(m.group("y"), _MONTHS[m.group("mon")[:3].lower()], None), "unit": None})
    for m in _DATE_SLASH_MD.finditer(t):
        if 1 <= int(m.group("mo")) <= 12 and 1 <= int(m.group("d")) <= 31:
            add(m, {"kind": "date", "value": _date_value(None, m.group("mo"), m.group("d")), "unit": None})

    for m in _PERCENT.finditer(t):
        add(m, {"kind": "percent", "value": _num(m.group("num")), "unit": "%"})
    for m in _WARI.finditer(t):
        add(m, {"kind": "percent", "value": _num(m.group("num")) * 10, "unit": "%"})

    for m in _QTY.finditer(t):
        # avoid matching the "m" of "a.m." / numbers glued to words like "2nd"
        if t[m.end():m.end() + 1].isalpha() and re.match(r"[A-Za-z]", m.group("unit")[-1:]):
            continue
        add(m, {"kind": "quantity", "value": _num(m.group("num")), "unit": _qty_unit(m.group("unit"))})

    for m in _YEAR.finditer(t):
        add(m, {"kind": "date", "value": _date_value(m.group("y"), None, None), "unit": None, "year_only": True})
    return out


def values_match(a, b):
    """True if two extracted values express the same thing."""
    if a["kind"] != b["kind"]:
        return False
    if a["kind"] == "date":
        pa, pb = a["value"].split("-"), b["value"].split("-")
        both = [(x, y) for x, y in zip(pa, pb) if "X" not in x and "X" not in y]
        return bool(both) and all(x == y for x, y in both)
    if a.get("unit") and b.get("unit") and a["unit"] != b["unit"]:
        return False
    return abs(float(a["value"]) - float(b["value"])) < 1e-9


def comparable(a, b):
    """True if b can be used to contradict a (same kind and compatible unit)."""
    if a["kind"] != b["kind"] or a.get("year_only") or b.get("year_only"):
        return False
    if a["kind"] == "date":
        pa, pb = a["value"].split("-"), b["value"].split("-")
        return any("X" not in x and "X" not in y for x, y in zip(pa, pb))
    if a["kind"] == "price" and (a.get("unit") is None or b.get("unit") is None):
        return False  # "free" vs a number: let the model read
    if a.get("unit") and b.get("unit") and a["unit"] != b["unit"]:
        return False
    return True


# --------------------------------------------------------------------------
# Key terms for matching
# --------------------------------------------------------------------------

EN_STOP = set("""
a about above after again against all also am an and any are aren as at be because been before
being below between both but by can cannot could did do does doing don down during each few for
from further had has have having he her here hers him his how i if in into is isn it its itself
just me more most my no nor not now of off on once only or other our ours out over own same she
should so some such than that the their theirs them then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you
your yours yes get got make made may might must per via etc one two three also lot lots many much
really great good nice well even still every day days time times way best like love loved kids
visit visited visiting plan before arrive just january february march april may june july august
september october november december jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday
wednesday thursday friday saturday sunday
""".split())
JA_STOP = {"場合", "こと", "もの", "ため", "よう", "今回", "実際", "注意", "以下", "以上", "可能",
           "必要", "おすすめ", "オススメ", "ポイント", "情報", "確認", "利用", "大切", "記事", "時期"}

_FACILITY_EN = (r"Zoo|Aquarium|Museum|Park|Mall|Station|Hotel|Inn|Center|Centre|Cafe|Café|Restaurant|"
                r"Garden|Gardens|Library|Store|Shop|Market|Theater|Theatre|Farm|Castle|Temple|Shrine|"
                r"Tower|Plaza|Hall|Stadium|Resort|Pool|Beach")
_ENTITY_EN = re.compile(
    r"\b(?:[A-Z][\w'&.-]*\s+){0,4}(?:%s)\b|\b[A-Z][a-z'&-]+(?:\s+(?:of|the|de|and|&)?\s*[A-Z][\w'&-]+)+\b" % _FACILITY_EN)
_FACILITY_JA = (r"水族館|動物園|植物園|博物館|美術館|科学館|資料館|公園|遊園地|パーク|ランド|モール|センター|"
                r"ホテル|旅館|駅|店|館|園|寺|神社|カフェ|レストラン|施設|ガーデン|プラザ|タワー|ミュージアム|"
                r"牧場|農園|城|温泉|ビーチ|プール")
_ENTITY_JA = re.compile(r"[\u30a0-\u30ff\u4e00-\u9fffA-Za-z0-9・ー々]{1,20}?(?:%s)" % _FACILITY_JA)
_QUOTED_JA = re.compile(r"[「『]([^」』]{2,30})[」』]")
_KATA = re.compile(r"[\u30a1-\u30fa\u30fc]{2,}")
_KANJI = re.compile(r"[\u4e00-\u9fff\u3005]{2,}")
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def _stem(w):
    w = w.lower().strip("'-")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith(("sses", "xes", "ches", "shes")):
        return w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


_EN_START_FILLER = {"the", "a", "an", "when", "there", "our", "my", "we", "it", "this", "that"}


def key_terms(text):
    """Return (entity_terms, attr_terms). Terms are casefolded; EN attr terms are stemmed."""
    t = norm(text)
    entities = []
    for m in _ENTITY_EN.finditer(t):
        words = m.group(0).split()
        while words and words[0].lower() in _EN_START_FILLER:
            words = words[1:]
        if len(words) >= 2 or (words and re.fullmatch(_FACILITY_EN, words[-1])):
            entities.append(" ".join(words).casefold())
    for m in _ENTITY_JA.finditer(t):
        e = m.group(0)
        if len(e) >= 3:
            entities.append(e.casefold())
    for m in _QUOTED_JA.finditer(t):
        entities.append(m.group(1).casefold())
    entities = sorted(set(e for e in entities if e), key=len, reverse=True)

    attrs = []
    for w in _EN_WORD.findall(t):
        s = _stem(w)
        if s in EN_STOP or len(s) < 3:
            continue
        if any(s in e.split() or _stem(e.split()[-1]) == s for e in entities if " " in e or e.isascii()):
            continue
        attrs.append(s)
    for rx in (_KANJI, _KATA):
        for w in rx.findall(t):
            if w in JA_STOP:
                continue
            if any(w in e for e in entities):
                continue
            attrs.append(w.casefold())
    seen = []
    for a in attrs:
        if a not in seen:
            seen.append(a)
    return entities, seen


def text_has_term(folded_text, en_tokens, term):
    """Check a term against a passage. ASCII terms use stemmed tokens; others use substring."""
    if term.isascii() and " " not in term:
        return term in en_tokens
    return term in folded_text


def tokens_of(text):
    return set(_stem(w) for w in _EN_WORD.findall(norm(text)))
