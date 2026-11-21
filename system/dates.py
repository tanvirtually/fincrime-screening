"""Partial-date parsing and comparison, POLICY.md principles 5-7.

A date is a tuple (year, month, day); month/day may be None. Unknown stays unknown.
"""
import re

MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9


def _mon(tok):
    return MONTHS.get(tok.lower().rstrip("."))


def parse_one(s):
    """Parse one date string into (y, m, d) or None."""
    if not s:
        return None
    s = str(s).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ].*)?", s)
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        return int(m[1]), int(m[2]), None
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return int(m[1]), None, None
    # dd/mm/yyyy (UK style in this bank's data)
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:
        a, b = int(m[1]), int(m[2])
        if b > 12 and a <= 12:  # clearly mm/dd
            a, b = b, a
        return int(m[3]), b, a
    m = re.fullmatch(r"([A-Za-z]+)\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", s)
    if m and _mon(m[1]):
        return int(m[3]), _mon(m[1]), int(m[2])
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]+)\.?,? (\d{4})", s)
    if m and _mon(m[2]):
        return int(m[3]), _mon(m[2]), int(m[1])
    m = re.fullmatch(r"([A-Za-z]+)\.?,? (\d{4})", s)
    if m and _mon(m[1]):
        return int(m[2]), _mon(m[1]), None
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
