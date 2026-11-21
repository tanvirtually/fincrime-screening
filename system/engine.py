"""Screening decisions, POLICY.md. Deterministic: same input, same output."""
import json
import os
import re
from collections import defaultdict

import countries as C
import dates as D
import names as N

# ---------------------------------------------------------------- loading


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


LIST_FIELDS = ("aliases", "dobs", "nationality", "citizenship", "countries", "addresses", "categories",
               "identifiers", "sources", "source_urls")


def _norm_hit(h):
    for k in LIST_FIELDS:
        v = h.get(k)
        if v is None:
            h[k] = []
        elif isinstance(v, str):
            h[k] = [x.strip() for x in v.split(";") if x.strip()]
        elif not isinstance(v, list):
            h[k] = [v]
        h[k] = [str(x) if not isinstance(x, (str, dict)) else x for x in h[k]]
        h[k] = [x if isinstance(x, str) else " ".join(str(y) for y in x.values()) for x in h[k]]
    return h


class Data:
    def __init__(self, folder):
        p = lambda n: os.path.join(folder, n)
        self.alerts = read_jsonl(p("alerts.jsonl"))
        self.hits = {h["hit_id"]: _norm_hit(h) for h in read_jsonl(p("hits.jsonl"))}
        self.customers = {c["record_id"]: c for c in read_jsonl(p("customers.jsonl"))}
        accounts = read_jsonl(p("accounts.jsonl"))
        onboarding = read_jsonl(p("onboarding.jsonl"))
        kyc = read_jsonl(p("kyc_checks.jsonl"))
        notes = read_jsonl(p("notes.jsonl"))
        search = read_jsonl(p("search_results.jsonl"))
        nv = json.load(open(p("name_variants.json"), encoding="utf-8"))
        N.load_variants(nv.get("groups", []), nv.get("legal_forms") or nv.get("company_legal_forms"))

        self.acc_by_id = defaultdict(list)
        self.acc_by_login = defaultdict(list)
        self.acc_by_cust = defaultdict(list)
        for a in accounts:
            self.acc_by_id[a["account_id"]].append(a)
            if a.get("login_handle"):
                self.acc_by_login[a["login_handle"].lower()].append(a)
            self.acc_by_cust[a["customer_id"]].append(a)
        self.onb_by_cust = defaultdict(list)
        for o in onboarding:
            self.onb_by_cust[o["customer_id"]].append(o)
        self.kyc_by_app = defaultdict(list)
        for k in kyc:
            self.kyc_by_app[k["applicant_id"]].append(k)
        self.notes_by_email = defaultdict(list)
        for n in notes:
            if n.get("requester_email"):
                self.notes_by_email[n["requester_email"].lower()].append(n)
        self.search_by_query = defaultdict(list)
        for s in search:
            self.search_by_query[s["query"].strip().lower()].append(s)
        self.cust_by_email = defaultdict(list)
        self.part_index = defaultdict(set)
        for c in self.customers.values():
            if c.get("email"):
                self.cust_by_email[c["email"].lower()].append(c["record_id"])
            comp = c.get("entity_type") == "Company"
            for nm in (c.get("full_name"), c.get("preferred_name"), c.get("login_name")):
                for part in N.parts(nm, comp):
                    self.part_index[part].add(c["record_id"])
        self.vocab = list(self.part_index)
        self._build_people()
        self._approved_checks = {}

    # ------------------------------------------------ people (principle 3)
    def _build_people(self):
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        by_phone_dob = defaultdict(list)
        for cid, c in self.customers.items():
            dob = D.parse_one(c.get("dob"))
            if not dob or not dob[1] or not dob[2]:
                continue
            phones = {self._phone(c.get("phone"))}
            for a in self.acc_by_cust.get(cid, []):
                phones.add(self._phone(a.get("phone")))
            for ph in phones:
                if ph:
                    by_phone_dob[(ph, dob)].append(cid)
        for ids in by_phone_dob.values():
            for o in ids[1:]:
                union(ids[0], o)
        by_doc = defaultdict(set)
        for cid in self.customers:
            for k in self.kyc_checks_for(cid):
                if k.get("result") == "approved" and k.get("document_number"):
                    by_doc[k["document_number"].strip().upper()].add(cid)
        for ids in by_doc.values():
            ids = sorted(ids)
            for o in ids[1:]:
                union(ids[0], o)
        self.person_of = {cid: find(cid) for cid in self.customers}
        self.members = defaultdict(list)
        for cid, root in self.person_of.items():
            self.members[root].append(cid)
        for v in self.members.values():
            v.sort()

    @staticmethod
    def _phone(p):
        if not p:
            return None
        d = re.sub(r"\D", "", p)
        return d if len(d) >= 7 else None

    def kyc_checks_for(self, cid):
        out = []
        for o in self.onb_by_cust.get(cid, []):
            out.extend(self.kyc_by_app.get(o["kyc_applicant_id"], []))
        return out


# ---------------------------------------------------------------- notes

BIRTH_CUE = re.compile(r"\b(born|dob|d\.o\.b|birth|birthdate|date of birth|b\.)\b", re.I)
NEG_CUE = re.compile(r"\b(reject\w*|fail\w*|declin\w*|expired|could not|unable|unsuccessful\w*|denied|invalid|not verified|not be verified|mismatch\w*)\b", re.I)
VERIFY_CUE = re.compile(r"\b(verif\w*|validat\w*|confirm\w*|approv\w*|vetted|passed|cleared|authenticat\w*|checked|screening|identity)\b", re.I)
DOC_CUE = re.compile(r"\b(passport|national id|id card|identity card|driving licen[cs]e|driver'?s licen[cs]e|residence permit|document)\b", re.I)
LIVED_CUE = re.compile(r"\b(liv\w*|resid\w*|home|based|work\w*|employ\w*|career|domestic|reloc\w*|moved|stay\w*)\b", re.I)

DATE_TOKEN = re.compile(
    r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.]\d{1,2}[/.]\d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4}|"
    r"\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,? \d{4})\b",
    re.I)


def _dob_near_cue(t):
    """The date that a birth cue points at: the first one right after it, else just before it."""
    for cue in BIRTH_CUE.finditer(t):
        rest = t[cue.end():]
        cands = []
        found = D.find_dates(rest)
        if found and found[0][0] <= 30:
            cands.append((found[0][0], found[0][2]))
        m = re.match(r"[\s:,.(\-]*(?:[a-z]+\s+){0,3}?((?:19|20)\d{2})\b(?![-/.]\d)", rest, re.I)
        if m:
            cands.append((m.start(1), (int(m.group(1)), None, None)))
        if cands:
            return min(cands, key=lambda c: c[0])[1]
        before = [f for f in D.find_dates(t[:cue.start()]) if cue.start() - f[1] <= 25]
        if before:
            return before[-1][2]
    return None


def _dob_without_cue(t, created):
    """No 'born'/'DOB' word: the DOB is the only date at least 10 years before the note."""
    if not created:
        return None
    old = [d for _, _, d in D.find_dates(t) if d[0] <= created[0] - 10]
    old = list(dict.fromkeys(old))
    return old[0] if len(old) == 1 else None


def parse_kyc_note(note):
    """An onboarding note that records an identity check. Returns dict or None."""
    t = note.get("text") or ""
    has_cue = bool(BIRTH_CUE.search(t))
    if not (DOC_CUE.search(t) and (has_cue or VERIFY_CUE.search(t))):
        return None
    if NEG_CUE.search(t):
        return {"approved": False}
    created = D.parse_one(note.get("created_at"))
    dob = _dob_near_cue(t) if has_cue else _dob_without_cue(t, created)
    if dob and created and not (1900 <= dob[0] <= created[0] - 10):
        dob = None  # not a plausible birth date for someone checked on that day
    if not dob:
        return None
    name = caps_name(t)
    ctry = [c for c in C.in_text(t) if not (name and c.lower() in name.lower())]
    return {"approved": True, "name": name, "dob": dob, "country": ctry[0] if ctry else None,
            "date": note.get("created_at") or "", "id": note["note_id"]}


ACRONYMS = {"DOB", "D.O.B.", "D.O.B", "ID", "KYC", "AML", "UK", "US", "USA", "UAE", "EU", "PEP", "N/A"}
_TOKEN = re.compile(r"[^\s,;:()]+")


def _is_caps_word(tok):
    core = tok.strip(".'\u2019-")
    letters = [c for c in core if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters) and all(c.isalpha() or c in "'-.\u2019" for c in core)


def _is_placeholder(tok):
    return tok.upper().strip(".") in {"N/A", "NA", "XXX", "NONE", "UNKNOWN", "TEST", "NULL"} or tok.isdigit()


def caps_name(text):
    """Longest run of ALL-CAPS words (any alphabet), placeholders allowed inside."""
    best, run = [], []
    for m in _TOKEN.finditer(text):
        tok = m.group(0).rstrip(".")
        gap = text[run[-1][1]:m.start()] if run else " "
        if (_is_caps_word(tok) or (run and _is_placeholder(tok)) or (not run and _is_placeholder(tok))) \
                and tok.upper() not in ACRONYMS and gap.strip() == "":
            run.append((tok, m.end()))
        else:
            if len(run) > len(best):
                best = run
            run = [(tok, m.end())] if (_is_caps_word(tok) and tok.upper() not in ACRONYMS) else []
    if len(run) > len(best):
        best = run
    words = [w for w, _ in best]
    if not any(_is_caps_word(w) for w in words):
        return None
    return " ".join(words)


def lived_countries(note):
    t = note.get("text") or ""
    if not LIVED_CUE.search(t):
        return []
    return C.in_text(t)


# ---------------------------------------------------------------- customer side


class Person:
    """Everything known about one customer, each fact with its source id."""

    def __init__(self, data, records):
        self.records = records
        cs = [data.customers[r] for r in records]
        self.company = any(c.get("entity_type") == "Company" for c in cs)
        self.entity_type = "Company" if self.company else "Individual"
        self.record_names = [(c["full_name"], c["record_id"]) for c in cs if c.get("full_name")]
        self.other_names = [(c[k], c["record_id"]) for c in cs for k in ("preferred_name", "login_name") if c.get(k)]
        self.countries = defaultdict(set)
        for c in cs:
            for k in ("residence_country", "nationality"):
                v = C.norm(c.get(k))
                if v:
                    self.countries[v].add(c["record_id"])
        # verified checks
        checks = []
        for r in records:
            for k in data.kyc_checks_for(r):
                if k.get("result") == "approved":
                    checks.append({"name": k.get("verified_name"), "dob": D.parse_one(k.get("verified_dob")),
                                   "country": C.norm(k.get("document_country")), "date": k.get("checked_at") or "",
                                   "id": k["check_id"]})
        emails = sorted({c["email"].lower() for c in cs if c.get("email")})
        self.note_ids = []
        for e in emails:
            for n in data.notes_by_email.get(e, []):
                k = parse_kyc_note(n)
                if k and k.get("approved"):
                    checks.append(k)
                elif not k:
                    for ctry in lived_countries(n):
                        self.countries[ctry].add(n["note_id"])
        checks.sort(key=lambda k: (k["date"], k["id"]))
        self.check = checks[-1] if checks else None
        if self.check and self.check.get("country"):
            self.countries[self.check["country"]].add(self.check["id"])
        # date of birth: verified first, else declared on the record(s)
        self.dob, self.dob_src = None, None
        if self.check and self.check.get("dob"):
            self.dob, self.dob_src = self.check["dob"], self.check["id"]
        else:
            declared = []
            for c in cs:
                d = D.parse_one(c.get("dob"))
                if d and d not in [x for x, _ in declared]:
                    declared.append((d, c["record_id"]))
            if len(declared) == 1:
                self.dob, self.dob_src = declared[0]
        self.verified_name = self.check.get("name") if self.check else None
        self.verified_src = self.check["id"] if self.check else None


def screened_fits(data, cid, s):
    """Principle 2: does this record fit what was screened?"""
    c = data.customers[cid]
    comp = s.get("entity_type") == "Company"
    if s.get("name"):
        nm = [c.get("full_name"), c.get("preferred_name"), c.get("login_name")]
        if not any(N.names_agree(s["name"], x, comp) for x in nm if x):
            return False
    sd = D.parse_one(s.get("dob"))
    if sd:
        cd = D.parse_one(c.get("dob"))
        if cd:
            if cd[0] != sd[0] or (cd[1] and sd[1] and cd[1] != sd[1]) or (cd[2] and sd[2] and cd[2] != sd[2]):
                return False
    if s.get("country"):
        want = C.norm(s["country"])
        have = {C.norm(c.get("residence_country")), C.norm(c.get("nationality"))}
        if want and want not in have:
            return False
    if s.get("city"):
        city = N.strip(s["city"])
        if city not in N.strip(c.get("city") or "") and city not in N.strip(c.get("address") or ""):
            return False
    return True


def resolve(data, alert):
    """Returns (list of person record-lists, path notes)."""
    s = alert["customer"]
    cands = []
    path = []
    if alert.get("account_ref"):
        cands = [a["customer_id"] for a in data.acc_by_id.get(alert["account_ref"], [])]
        path.append(f"account {alert['account_ref']}")
    elif alert.get("login_handle"):
        cands = [a["customer_id"] for a in data.acc_by_login.get(alert["login_handle"].lower(), [])]
        path.append(f"login {alert['login_handle']}")
    elif alert.get("email"):
        cands = list(data.cust_by_email.get(alert["email"].lower(), []))
        path.append(f"email {alert['email']}")
    cands = sorted(set(cands))
    if len(cands) > 1:
        fit = [c for c in cands if screened_fits(data, c, s)]
        cands = fit or cands
    elif not cands:
        comp = s.get("entity_type") == "Company"
        pool = set()
        for p in N.parts(s.get("name"), comp):
            for v in data.vocab:
                if N.part_match(p, v):
                    pool |= data.part_index[v]
        cands = sorted(c for c in pool if screened_fits(data, c, s))
        path.append("search by screened details")
    people = {}
    for c in cands:
        root = data.person_of[c]
        people.setdefault(root, [])
        if c not in people[root]:
            people[root].append(c)
    out = []
    for root, linked in sorted(people.items()):
        out.append((linked[0], data.members[root]))
    return out, path


# ---------------------------------------------------------------- hit side

LISTING = {"sanctions": "a sanctioned individual", "pep": "a politically exposed person",
           "enforcement": "the subject of enforcement action", "adverse media": "named in adverse media",
           "soe": "a state-owned enterprise official"}
REPORT_RE = re.compile(r"^According to [^\n;]*; ([A-Z][a-z]+\.? \d{1,2}, \d{4}):", re.M)
AGE_CUE = re.compile(
    r"\b(?:aged?|age of|at age|at the age of)\s+(\d{1,3})\b"
    r"|\b(\d{1,3})[- ]years?[- ]old\b"
    r"|\b(\d{1,3})\s+years?\s+of\s+age\b"
    r"|\b(?:was|is|were|reached|turned)\s+(\d{1,3})\b(?!\s*(?:years?\s+(?:in|for|of\s+(?!age))|months|%|percent|times|counts?|people|defendants))"
    r"|,\s*(\d{1,3})\s*,"
    r"|\bat\s+(\d{1,3})\s*[.,;]?\s*$", re.I)
MONTH_YEAR = re.compile(r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4})\b", re.I)


def hit_countries(h):
    out = {}
    for k in ("countries", "nationality", "citizenship"):
        for v in h.get(k) or []:
            c = C.norm(v)
            if c:
                out.setdefault(c, k)
    for a in h.get("addresses") or []:
        a = re.sub(r"\[[^\]]*\]", "", str(a)).strip().rstrip(",")
        c = C.norm(a.split(",")[-1]) if a else None
        if c:
            out.setdefault(c, "addresses")
    if h.get("place_of_birth"):
        c = C.norm(h["place_of_birth"])
        if c:
            out.setdefault(c, "place_of_birth")
    return out


def _age_facts(text):
    """Age-at-date statements in a short text -> list of (years, snippet)."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text or ""):
        s2 = D.words_to_numbers(sent)
        found = D.find_dates(s2)
        if found:
            when_d = found[0][2]
            cleaned = s2
            for a, b, _ in reversed(found):
                cleaned = cleaned[:a] + " " + cleaned[b:]
        else:
            yr = re.search(r"\b(19|20)\d{2}\b", s2)
            if not yr:
                continue
            when_d = (int(yr.group(0)), None, None)
            cleaned = s2[:yr.start()] + " " + s2[yr.end():]
        cleaned = re.sub(r"\b(19|20)\d{2}\b", " ", cleaned)
        ages = []
        for m in AGE_CUE.finditer(cleaned):
            ages += [int(g) for g in m.groups() if g]
        ages = sorted({a for a in ages if 10 <= a <= 110})
        if len(ages) == 1:
            out.append((D.birth_years_from_age(ages[0], when_d), sent.strip()))
    return out


BORN_RE = re.compile(r"\b(?:born|date of birth|dob|d\.o\.b\.?|birth ?date)\b", re.I)


def _born_fact(text):
    """'X was born on 17 July 1939' / 'born in 1952' / 'DOB: 1960-04-10' -> date or None."""
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text or ""):
        cue = BORN_RE.search(sent)
        if not cue:
            continue
        rest = sent[cue.end():]
        found = D.find_dates(rest)
        if found and found[0][0] < 25:
            return found[0][2]
        m = re.match(r"\W{0,3}(?:on|in|:)?\s*(?:the year\s+)?((?:19|20)\d{2})\b", rest, re.I)
        if m:
            return (int(m.group(1)), None, None)
    return None


def hit_dobs(data, h):
    """Principle 5. Returns (list of dob items, source label, evidence ids).
    Each item: ('date', (y,m,d)) or ('years', [y1, y2])."""
    items = [("date", d) for d in (D.parse_one(x) for x in h.get("dobs") or []) if d]
    if items:
        return items, "listed date of birth", []
    if h.get("entity_type") == "Company":
        return [], None, []
    notes = h.get("profile_notes") or ""
    first = notes.strip().split("\n\n")[0] if notes.strip() else ""
    if first and not first.startswith("According to"):
        d = _born_fact(first)
        if d:
            return [("date", d)], "profile notes", []
        ages = _age_facts(first)
        if ages:
            ys = sorted({y for a in ages for y in a[0]})
            return [("years", ys)], "profile notes", []
    # web search results
    cat = (h.get("primary_category") or (h.get("categories") or [None])[0] or "").strip().lower()
    phrase = LISTING.get(cat, "named on a watchlist")
    tied = set(hit_countries(h))
    q = " ".join(sorted(N.parts(h.get("name")) or []))
    results = data.search_by_query.get(q, [])
    items, ids = [], []
    for r in sorted(results, key=lambda r: r["result_id"]):
        snip = r.get("snippet") or ""
        if phrase not in snip.lower():
            continue
        if not tied or not (set(C.in_text(snip)) & tied):
            continue
        if not any(N.names_agree(h.get("name"), x) for x in [r.get("title", "").split(" - ")[0], snip]):
            continue
        ages = _age_facts(snip)
        if ages:
            items.append(("years", ages[0][0]))
            ids.append(r["result_id"])
    if items:
        return items, "search results", ids
    return [], None, []


def earliest_report(h):
    ds = []
    for m in REPORT_RE.finditer(h.get("profile_notes") or ""):
        d = D.parse_one(m.group(1))
        if d:
            ds.append(d)
    return min(ds) if ds else None


def hit_names(h):
    out = [h.get("name")] + list(h.get("aliases") or [])
    for k in ("best_matching_name",):
        if h.get(k):
            out.append(h[k])
    fml = " ".join(x for x in (h.get("first_name"), h.get("middle_name"), h.get("last_name")) if x)
    if fml:
        out.append(fml)
    seen, res = set(), []
    for n in out:
        if n and n not in seen:
            seen.add(n)
            res.append(n)
    return res


# ---------------------------------------------------------------- deciding


def fmt_years(item):
    kind, v = item
    if kind == "date":
        return D.fmt(v)
    return " or ".join(str(y) for y in v)


def dob_relation(cdob, items):
    """('agree'|'contradict'|'unknown', agreeing_item)"""
    if not cdob or not items:
        return "unknown", None
    for it in items:
        kind, v = it
        if kind == "date" and D.dob_agrees(cdob, None, v):
            return "agree", it
        if kind == "years" and D.dob_agrees(cdob, v):
            return "agree", it
    allc = all((D.dob_contradicts(cdob, hit_date=v) if k == "date" else D.dob_contradicts(cdob, hit_years=v))
               for k, v in items)
    return ("contradict" if allc else "unknown"), None


def decide_person(data, alert, h, person):
    """One hit against one person. Returns dict with decision, code, reason, evidence."""
    company = person.company
    hcomp = h.get("entity_type") == "Company"
    hn = hit_names(h)
    hc = hit_countries(h)
    cc = person.countries
    screened = D.parse_one(alert.get("screened_at"))

    if company != hcomp:
        return dict(decision="DIFFERENT_ENTITY", code="ENTITY_TYPE_MISMATCH",
                    reason=f"The customer is {'a company' if company else 'a person'} but the hit is "
                           f"{'a company' if hcomp else 'a person'} ({h.get('name')}).",
                    evidence=list(person.records[:1]))

    # names
    verified = person.verified_name
    vparts = N.real_part_count(verified, company) if verified else 0
    # the verified legal name outranks the record; one with under two real parts can't decide anything
    name_pool = [verified] if verified else [n for n, _ in person.record_names]
    name_ok = None
    if company or any(N.real_part_count(n) >= 2 for n in name_pool):
        name_ok = N.any_agree(name_pool, hn, company)

    # dates of birth
    items, dsrc, dids = hit_dobs(data, h)
    rel, agree_item = dob_relation(person.dob, items)

    # countries
    shared = sorted(set(cc) & set(hc))
    contradictions = []

    # deceased
    if h.get("deceased_date") and screened:
        dd = D.parse_one(h["deceased_date"])
        if dd and D.definitely_after(screened, dd):
            contradictions.append(("DECEASED", f"The hit's profile gives a date of death of {D.fmt(dd)}, before the customer was screened on {alert['screened_at']}.", []))

    # time
    er = earliest_report(h)
    if er and person.dob:
        if company:
            if D.definitely_after(person.dob, er):
                contradictions.append(("TEMPORAL_IMPOSSIBILITY",
                    f"The customer was incorporated in {D.fmt(person.dob)} ({person.dob_src}), after the hit's earliest dated report on {D.fmt(er)}.",
                    [person.dob_src]))
        else:
            oldest = D.age_at(person.dob, er)
            if oldest < 16:
                contradictions.append(("TEMPORAL_IMPOSSIBILITY",
                    f"The customer was born {'on' if person.dob[2] else 'in'} {D.fmt(person.dob)} ({person.dob_src}), so they were at most {max(oldest, 0)} when the hit's profile reports activity on {D.fmt(er)}.",
                    [person.dob_src]))

    if rel == "contradict":
        hd = "; ".join(fmt_years(i) for i in items)
        what = {"listed date of birth": f"the hit's listed date of birth is {hd}",
                "profile notes": f"the hit's profile notes put its birth year at {hd}",
                "search results": f"the hit's search results put its birth year at {hd}"}[dsrc]
        word = "incorporation date" if company else "date of birth"
        contradictions.append(("DOB_MISMATCH", f"The customer's {word} is {D.fmt(person.dob)} ({person.dob_src}) but {what}.",
                               [person.dob_src] + dids))

    if verified and (company or vparts >= 2) and not N.any_agree([verified], hn, company):
        contradictions.append(("NAME_MISMATCH_VERIFIED",
            f"The customer's verified name is {verified} ({person.verified_src}), which does not match the hit's name {h.get('name')}.",
            [person.verified_src]))

    loc_contra = bool(cc) and bool(hc) and not shared
    name_dob_agree = bool(name_ok) and rel == "agree"
    if loc_contra and not name_dob_agree:
        src = sorted({s for v in cc.values() for s in v})
        contradictions.append(("LOCATION_MISMATCH",
            f"The customer is linked only to {', '.join(sorted(cc))} but the hit is linked only to {', '.join(sorted(hc))}.",
            src))

    if contradictions:
        code, reason, ev = contradictions[0]
        extra = " ".join(r for _, r, _ in contradictions[1:2])
        return dict(decision="DIFFERENT_ENTITY", code=code, reason=(reason + " " + extra).strip(),
                    evidence=_dedupe(ev + [e for _, _, e2 in contradictions[1:2] for e in e2]))

    # agreement
    parts = []
    ev = []
    if agree_item and person.dob:
        parts.append(f"The customer's date of birth {D.fmt(person.dob)} ({person.dob_src}) agrees with the hit's {fmt_years(agree_item)}.")
        ev += [person.dob_src] + dids
    if shared:
        parts.append(f"Both the customer and the hit are linked to {', '.join(shared)}.")
        ev += sorted({s for c in shared for s in cc[c]})
    if name_ok:
        parts.append(f"The customer's name agrees with the hit's name {name_ok[1]}.")
    if company:
        if name_ok and shared:
            return dict(decision="SAME_ENTITY", code="NAME_LOCATION_MATCH", reason=" ".join(parts), evidence=_dedupe(ev))
    else:
        if name_dob_agree and not loc_contra:
            code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
            return dict(decision="SAME_ENTITY", code=code, reason=" ".join(parts), evidence=_dedupe(ev))

    missing = []
    if loc_contra and name_dob_agree:
        missing.append("the countries differ but the name and date of birth agree, so a country difference alone cannot clear it")
    if rel == "unknown":
        if not person.dob:
            missing.append("the customer has no date of birth on file")
        elif not items:
            missing.append("the hit gives no date of birth to compare with")
        else:
            missing.append("the dates of birth neither clearly agree nor contradict")
    if not name_ok:
        missing.append("the names cannot be confirmed as agreeing")
    if not cc or not hc:
        missing.append("there are no countries to compare on one side")
    tail = ("Nothing settles it: " + "; ".join(missing) + ". A person should review it.") if missing else \
        "Nothing in the customer's records contradicts the hit, but there is not enough agreement to confirm it."
    return dict(decision="REVIEW", code="INSUFFICIENT_DATA", reason=(" ".join(parts) + " " + tail).strip(),
                evidence=_dedupe(ev) or list(person.records[:1]))


def _dedupe(xs):
    out = []
    for x in xs:
        if x and x not in out:
            out.append(x)
    return out


def decide(data, alert, hit_id, people_cache):
    h = data.hits[hit_id]
    people = people_cache
    if not people:
        return dict(hit_id=hit_id, alert_id=alert["alert_id"], decision="REVIEW", reason_code="INSUFFICIENT_DATA",
                    customer_record_id=None,
                    reason=f"No customer record in the bank's systems fits the screened customer {alert['customer'].get('name')}, so the hit {h.get('name')} cannot be compared with anyone. A person should review it.",
                    evidence=[])
    results = [(rec, decide_person(data, alert, h, p)) for rec, p in people]
    if len(results) == 1:
        rec, r = results[0]
        return dict(hit_id=hit_id, alert_id=alert["alert_id"], decision=r["decision"], reason_code=r["code"],
                    customer_record_id=rec, reason=r["reason"], evidence=r["evidence"])
    decisions = {r["decision"] for _, r in results}
    recs = [rec for rec, _ in results]
    if len(decisions) == 1:
        rec, r = results[0]
        ev = _dedupe([e for _, rr in results for e in rr["evidence"]])
        return dict(hit_id=hit_id, alert_id=alert["alert_id"], decision=r["decision"], reason_code=r["code"],
                    customer_record_id="AMBIGUOUS",
                    reason=f"{len(results)} different customers fit the screened details ({', '.join(recs)}) and each leads to the same decision. " + r["reason"],
                    evidence=ev)
    summary = "; ".join(f"{rec}: {r['decision']}" for rec, r in results)
    return dict(hit_id=hit_id, alert_id=alert["alert_id"], decision="REVIEW", reason_code="AMBIGUOUS_CUSTOMER_RECORD",
                customer_record_id="AMBIGUOUS",
                reason=f"{len(results)} different customers fit the screened details and they lead to different decisions ({summary}). A person should decide which customer this alert is about.",
                evidence=recs)


def _safe_review(alert_id, hit_id, err):
    return dict(hit_id=hit_id, alert_id=alert_id, decision="REVIEW", reason_code="INSUFFICIENT_DATA",
                customer_record_id=None,
                reason="The system could not process this hit automatically, so it goes to a person to review.",
                evidence=[], _error=repr(err))


def run(folder):
    data = Data(folder)
    out = []
    done = set()
    for alert in data.alerts:
        try:
            resolved, _ = resolve(data, alert)
            people = [(rec, Person(data, members)) for rec, members in resolved]
        except Exception as e:  # never let one alert kill the run
            people, err = None, e
        for hid in alert.get("hit_ids") or []:
            if hid not in data.hits or hid in done:
                continue
            done.add(hid)
            if people is None:
                out.append(_safe_review(alert["alert_id"], hid, err))
                continue
            try:
                out.append(decide(data, alert, hid, people))
            except Exception as e:
                out.append(_safe_review(alert["alert_id"], hid, e))
    # hits not listed in any alert's hit_ids
    by_alert = {a["alert_id"]: a for a in data.alerts}
    for hid, h in sorted(data.hits.items()):
        if hid in done:
            continue
        alert = by_alert.get(h.get("alert_id"))
        try:
            resolved, _ = resolve(data, alert)
            people = [(rec, Person(data, m)) for rec, m in resolved]
            out.append(decide(data, alert, hid, people))
        except Exception as e:
            out.append(_safe_review(h.get("alert_id"), hid, e))
    return out
