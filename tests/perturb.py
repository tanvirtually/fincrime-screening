"""Make a reworded copy of the dev data to test robustness.

python3 perturb.py <dev folder> <out folder> <seed>
Rewrites free text (notes, profile notes, search snippets) and date formats,
without changing any fact. Decisions on the copy should match the labels.
"""
import json
import os
import random
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))
import dates as D

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


def num_word(n):
    if n < 20:
        return ONES[n]
    t, o = divmod(n, 10)
    return TENS[t] + ("-" + ONES[o] if o else "")


def fmt_date(d, rng):
    y, m, dd = d
    if m and dd:
        style = rng.choice(["iso", "long", "us", "ord", "uk_slash_safe", "abbr"])
        if style == "iso":
            return f"{y}-{m:02d}-{dd:02d}"
        if style == "long":
            return f"{dd} {MONTHS[m-1]} {y}"
        if style == "us":
            return f"{MONTHS[m-1]} {dd}, {y}"
        if style == "ord":
            suf = "th" if 11 <= dd <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(dd % 10, "th")
            return f"the {dd}{suf} of {MONTHS[m-1]} {y}"
        if style == "abbr":
            return f"{dd}-{MONTHS[m-1][:3]}-{y}"
        if dd > 12:
            return f"{dd:02d}/{m:02d}/{y}"
        return f"{y}/{m:02d}/{dd:02d}"
    if m:
        return rng.choice([f"{MONTHS[m-1]} {y}", f"{MONTHS[m-1][:3]} {y}", f"{MONTHS[m-1]}, {y}"])
    return str(y)


def redate(text, rng):
    out, last = [], 0
    for a, b, d in D.find_dates(text):
        out.append(text[last:a])
        out.append(fmt_date(d, rng))
        last = b
    out.append(text[last:])
    return "".join(out)


SYN = [
    (r"\bDOB\b", ["date of birth", "D.O.B.", "birth date", "DOB"]),
    (r"\bborn\b", ["born", "born on" if False else "born"]),
    (r"\bverified\b", ["authenticated", "verified", "confirmed"]),
    (r"\bsuccessfully validated\b", ["approved", "successfully checked"]),
    (r"\bpassport\b", ["passport", "travel passport"]),
]


def reword(text, rng):
    for pat, opts in SYN:
        text = re.sub(pat, lambda m: rng.choice(opts), text)
    return text


def ages_to_words(text, rng):
    def rep(m):
        n = int(m.group(1))
        return m.group(0).replace(m.group(1), num_word(n)) if rng.random() < 0.6 and 10 <= n < 100 else m.group(0)
    text = re.sub(r"\b(?:aged|age of|was|is|at age)\s+(\d{2})\b", rep, text)
    text = re.sub(r"\b(\d{2})-year-old\b", rep, text)
    text = re.sub(r",\s*(\d{2})\s*,", rep, text)
    return text


def main():
    src, dst, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    rng = random.Random(seed)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        if f not in ("notes.jsonl", "hits.jsonl", "search_results.jsonl", "kyc_checks.jsonl", "customers.jsonl"):
            shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    with open(os.path.join(dst, "notes.jsonl"), "w") as w:
        for l in open(os.path.join(src, "notes.jsonl")):
            r = json.loads(l)
            r["text"] = reword(redate(r["text"], rng), rng)
            w.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(dst, "hits.jsonl"), "w") as w:
        for l in open(os.path.join(src, "hits.jsonl")):
            r = json.loads(l)
            pn = r.get("profile_notes")
            if pn:
                parts = pn.split("\n\n")
                if not parts[0].startswith("According to"):
                    parts[0] = ages_to_words(redate(parts[0], rng), rng)
                r["profile_notes"] = "\n\n".join(parts)
            w.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(dst, "search_results.jsonl"), "w") as w:
        for l in open(os.path.join(src, "search_results.jsonl")):
            r = json.loads(l)
            r["snippet"] = ages_to_words(redate(r["snippet"], rng), rng)
            w.write(json.dumps(r, ensure_ascii=False) + "\n")
    for name, field in (("kyc_checks.jsonl", "verified_dob"), ("customers.jsonl", "dob")):
        with open(os.path.join(dst, name), "w") as w:
            for l in open(os.path.join(src, name)):
                r = json.loads(l)
                d = D.parse_one(r.get(field))
                if d and d[1] and d[2]:
                    r[field] = fmt_date(d, rng).replace("the ", "")
                w.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
