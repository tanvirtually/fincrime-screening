"""Name comparison, POLICY.md principle 8."""
import re
import unicodedata

PLACEHOLDERS = {"na", "n/a", "test", "unknown", "xxx", "none", "null", "nil", "tbc", "tbd"}

LEGAL_FORMS = set(
    "ab ag as asa bv co company corp corporation gmbh inc kg limited llc llp lp ltd "
    "na nv oy oyj plc sa sarl sas se sf sl spa srl".split()
)

VARIANT_GROUPS = []  # filled by load_variants()
_variant_index = {}

# Short forms the data pack's list leaves out. Bengali and Malay records often
# write Muhammad as "Md", "Mhd" or "Muhd". Treating them as the same part only
# makes names agree more often, so it can stop a clearance but never cause one.
EXTRA_GROUPS = [
    ["muhammad", "mohammed", "mohammad", "mohamed", "muhammed", "mohamad", "mohd",
     "muhamad", "md", "mhd", "muhd"],
]

# Apostrophes inside a name (O'Brien, D'Souza, curly or straight) are dropped,
# not turned into a space, so O'Dea, ODea and "O Dea" all become "odea".
APOSTROPHES = re.compile(r"['’‘`´]")


def load_variants(groups, legal_forms=None):
    """groups: list of lists of name forms (from name_variants.json)."""
    global VARIANT_GROUPS, _variant_index, LEGAL_FORMS
    VARIANT_GROUPS = [[strip(n) for n in g] for g in list(groups) + EXTRA_GROUPS]
    _variant_index = {}
    for i, g in enumerate(VARIANT_GROUPS):
        for n in g:
            _variant_index.setdefault(n, set()).add(i)
    if legal_forms:
        LEGAL_FORMS = {strip(f) for f in legal_forms}


def strip(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def parts(name, company=False):
    """Distinct real name parts. Drops brackets, punctuation, initials, placeholders."""
    if not name:
        return []
    s = strip(name)
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}", " ", s)
    if s.strip() in PLACEHOLDERS:
        return []
    s = APOSTROPHES.sub("", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    raw = s.split()
    # Irish "O Dea" written apart: join the lone O to the next part.
    joined = []
    i = 0
    while i < len(raw):
        if raw[i] == "o" and i + 1 < len(raw) and len(raw[i + 1]) >= 2 and not company:
            joined.append("o" + raw[i + 1])
            i += 2
        else:
            joined.append(raw[i])
            i += 1
    out = []
    for p in joined:
        if len(p) == 1 or p in PLACEHOLDERS or any(ch.isdigit() for ch in p):
            continue
        if company and p in LEGAL_FORMS:
            continue
        if p not in out:
            out.append(p)
    return out


def _edits(a, b, limit):
    """Levenshtein distance, early exit past limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def part_match(a, b):
    if a == b:
        return True
    if _variant_index.get(a, set()) & _variant_index.get(b, set()):
        return True
    short = min(len(a), len(b))
    if short < 4:
        return False
    limit = 1 if short <= 6 else 2
    return _edits(a, b, limit) <= limit


def _match(xs, ys):
    """One-to-one part matching. A joined part (abdulsalam) matching two adjacent
    parts (abdul salam) is one matched pair covering both.
    Returns (pairs, covered_x, covered_y)."""
    cx, cy, pairs = set(), set(), 0
    for a, b, ca, cb in ((xs, ys, cx, cy), (ys, xs, cy, cx)):
        for i, p in enumerate(a):
            if i in ca:
                continue
            for j in range(len(b) - 1):
                if j in cb or j + 1 in cb:
                    continue
                if part_match(p, b[j] + b[j + 1]):
                    ca.add(i); cb.update({j, j + 1}); pairs += 1
                    break
    for i, p in enumerate(xs):
        if i in cx:
            continue
        for j, q in enumerate(ys):
            if j not in cy and part_match(p, q):
                cx.add(i); cy.add(j); pairs += 1
                break
    return pairs, cx, cy


def names_agree(a, b, company=False):
    """True if two names agree under principle 8."""
    xs, ys = parts(a, company), parts(b, company)
    if not xs or not ys:
        return False
    pairs, cx, cy = _match(xs, ys)
    if pairs >= 2:
        return True
    if len(xs) <= len(ys) and len(cx) == len(xs):
        return True
    if len(ys) <= len(xs) and len(cy) == len(ys):
        return True
    return False


def any_agree(customer_names, hit_names, company=False):
    """Return the first (customer_name, hit_name) pair that agrees, else None."""
    for c in customer_names:
        for h in hit_names:
            if names_agree(c, h, company):
                return c, h
    return None


def real_part_count(name, company=False):
    return len(parts(name, company))
