"""Partial-date parsing and comparison, POLICY.md principles 5-7.

A date is a tuple (year, month, day); month/day may be None. Unknown stays unknown.
"""
import re

MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

NUM_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90}


def words_to_numbers(text):
    """'forty-six' -> '46', 'nineteen' -> '19'. Leaves everything else alone."""
    def tens(m):
        return str(TENS[m.group(1).lower()] + (NUM_WORDS.get((m.group(2) or "").lower(), 0)))
    text = re.sub(r"\b(" + "|".join(TENS) + r")(?:[-\s](one|two|three|four|five|six|seven|eight|nine))?\b",
                  tens, text, flags=re.I)
    return re.sub(r"\b(" + "|".join(k for k in NUM_WORDS if NUM_WORDS[k] >= 10) + r")\b",
                  lambda m: str(NUM_WORDS[m.group(1).lower()]), text, flags=re.I)


def _mon(tok):
    return MONTHS.get(tok.lower().rstrip("."))


MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
ORD = r"(?:st|nd|rd|th)?"
_PATTERNS = [
    ("ymd", r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"),
    ("dmy", r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})"),
    ("mdy_t", r"(" + MON + r")\s+(\d{1,2})" + ORD + r",?\s+(\d{4})"),
    ("dmy_t", r"(?:the\s+)?(\d{1,2})" + ORD + r"(?:\s+of)?[\s-]+(" + MON + r")[,\s-]+(\d{4})"),
    ("my_t", r"(" + MON + r"),?\s+(?:of\s+)?(\d{4})"),
    ("ym", r"(\d{4})-(\d{1,2})(?![-/.\d])"),
]
_DATE_RE = re.compile(r"\b(?:" + "|".join(f"(?P<{n}>{p})" for n, p in _PATTERNS) + r")\b", re.I)


def _mon(tok):
    t = tok.lower().rstrip(".")
    return MONTHS.get(t) or MONTHS.get(t[:3])


def _valid(y, m, d):
    if not (1800 <= y <= 2100):
        return None
    if m is not None and not 1 <= m <= 12:
        return None
    if d is not None and not 1 <= d <= 31:
        return None
    return (y, m, d)


def _from_match(m):
    kind = m.lastgroup
    g = [x for x in m.group(kind) and re.match(dict(_PATTERNS)[kind], m.group(kind), re.I).groups()]
    if kind == "ymd":
        return _valid(int(g[0]), int(g[1]), int(g[2]))
    if kind == "dmy":
        a, b = int(g[0]), int(g[1])
        if b > 12 and a <= 12:  # clearly month first
            a, b = b, a
        elif a <= 12 and b <= 12 and a != b:  # 05/06 could be May or June: keep only the year
            return _valid(int(g[2]), None, None)
        return _valid(int(g[2]), b, a)
    if kind == "mdy_t":
        return _valid(int(g[2]), _mon(g[0]), int(g[1]))
    if kind == "dmy_t":
        return _valid(int(g[2]), _mon(g[1]), int(g[0]))
    if kind == "my_t":
        return _valid(int(g[1]), _mon(g[0]), None)
    if kind == "ym":
        return _valid(int(g[0]), int(g[1]), None)
    return None


def find_dates(text):
    """All dates in free text: list of (start, end, (y, m, d))."""
    out = []
    for m in _DATE_RE.finditer(text or ""):
        d = _from_match(m)
        if d:
            out.append((m.start(), m.end(), d))
    return out


def parse_one(s):
    """Parse one date string into (y, m, d) or None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}", s):
        return _valid(int(s), None, None)
    found = find_dates(s)
    if found and found[0][0] == 0 and found[0][1] >= len(s.rstrip(" .,")):
        return found[0][2]
    if found and len(found) == 1:
        return found[0][2]
    m = re.fullmatch(r"(?:circa|c\.|about|approx\.?|abt\.?)?\s*(\d{4})s?", s, re.I)
    if m:
        return _valid(int(m.group(1)), None, None)
    return None


def parse_many(s):
    """A field like '1996; 1997' or '1970-01-02; 1971' -> list of dates."""
    if not s:
        return []
    out = []
    for piece in re.split(r"\s*[;|]\s*", str(s)):
        d = parse_one(piece)
        if d and d not in out:
            out.append(d)
    return out


AGE_RE = re.compile(
    r"\b(?:aged|age)\s+(\d{1,3})\b[^.;]{0,60}?\b(?:in|on)\s+((?:[A-Za-z]+\.?\s+)?(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?\d{4})",
    re.I)


def birth_years_from_age(age, at):
    """Aged N at date -> two possible birth years."""
    y = at[0]
    return [y - age - 1, y - age]


def ages_in_text(text):
    """Find 'aged 45 when sentenced in March 2019' style facts. Returns list of
    (possible_years, snippet)."""
    out = []
    for m in AGE_RE.finditer(text or ""):
        at = parse_one(m[2].strip()) or parse_one(m[2].strip().split()[-1])
        if at:
            out.append((birth_years_from_age(int(m[1]), at), m[0]))
    return out


def dob_agrees(cust, hit_years, hit_date=None):
    """Principle 7. cust: (y,m,d). hit given either as a full/partial date or
    as a list of possible years (age-derived)."""
    if hit_date:
        hy, hm, hd = hit_date
        if cust[0] != hy:
            return False
        if cust[1] and hm and cust[1] != hm:
            return False
        if cust[2] and hd and cust[1] == hm and cust[2] != hd:
            return False
        return True
    return cust[0] in hit_years


def dob_contradicts(cust, hit_date=None, hit_years=None):
    """Principle 6: customer's year more than 1 outside, or same year and
    month (or day) differ."""
    if hit_years is not None:
        return all(abs(cust[0] - y) > 1 for y in hit_years)
    hy, hm, hd = hit_date
    if abs(cust[0] - hy) > 1:
        return True
    if cust[0] == hy and cust[1] and hm:
        if cust[1] != hm:
            return True
        if cust[2] and hd and cust[2] != hd:
            return True
    return False


def age_at(dob, when):
    """Whole years old on date `when`, using unknown parts conservatively
    (returns the oldest the person could be)."""
    y, m, d = dob
    wy, wm, wd = when[0], when[1] or 12, when[2] or 31
    age = wy - y
    if m is not None and (wm, wd) < (m, d or 1):
        age -= 1
    return age


def fmt(d):
    if not d:
        return "unknown"
    y, m, dd = d
    if m and dd:
        return f"{y:04d}-{m:02d}-{dd:02d}"
    if m:
        return f"{y:04d}-{m:02d}"
    return str(y)


def definitely_after(a, b):
    """True only if date a is certainly later than date b, given unknown parts."""
    if a[0] != b[0]:
        return a[0] > b[0]
    if a[1] is None or b[1] is None:
        return False
    if a[1] != b[1]:
        return a[1] > b[1]
    if a[2] is None or b[2] is None:
        return False
    return a[2] > b[2]
