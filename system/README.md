# Same Person or Not: screening hit resolver

```
system/run <data folder> <output file>
```

Python 3 standard library only. No language model calls, no network. A run on the development set (819 hits, 72k customer records) takes about 10 seconds on a laptop and costs nothing.

## Results on the development set

| | |
|---|---|
| Practice labels | 50 / 50 right decisions, 0 unsafe clearances |
| Reason code / customer record on right decisions | 100% / 100% |
| Decision mix (all 819 hits) | 57% cleared, 15% same entity, 28% review |
| Stress test (3 reworded copies of the data) | all 819 decisions unchanged, 0 unsafe clearances |
| Run to run | byte-identical output |

## Architecture

```
alerts.jsonl ──► resolve customer ──► Person (facts + source IDs) ─┐
                 (link or search,                                   │
                  union-find people)                                ├─► decide ──► output line
hits.jsonl ────► hit facts ─────────► names, DOB items, countries ──┘   (contradictions first,
                 (dobs field → profile notes → search results)           then agreement, else REVIEW)
```

| File | What it does |
|---|---|
| `names.py` | Principle 8 exactly: accents, brackets, initials, placeholders and legal forms dropped; variant groups from `name_variants.json`; parts written together or apart; 1 edit for 4-6 letters, 2 for longer; "two parts match, or every part of the shorter name" |
| `dates.py` | Partial dates `(year, month or None, day or None)`. Unknown stays unknown. "Aged 45 in March 2019" becomes 1973 or 1974 |
| `countries.py` | ISO codes, demonyms ("Nigerian"), "City, Region, Country" and free-text mentions to one country name. "International" and "Europe" are not countries |
| `engine.py` | Customer resolution, hit facts, decision rules, reasons and evidence |

## Finding the customer

1. Follow the alert's link: `account_ref` → accounts, `login_handle` → accounts, or `email` → customers.
2. If the link gives more than one record (joint holders), keep those that fit the screened name, DOB, country and city.
3. With no link, search: every customer with a name part that matches a screened name part, filtered by the same fit test.
4. Group records into people with union-find: same phone (customer or account) plus the same full DOB, or the same document number on approved KYC checks.
5. If more than one person fits, each is decided separately. Same decision for all: that decision with `AMBIGUOUS`. Different decisions: `REVIEW` / `AMBIGUOUS_CUSTOMER_RECORD`.

A person's facts come from all their records. The most recent approved identity check wins for legal name, DOB and document country, whether it is a KYC row or an onboarding note ("Persona verified the passport of X, born ..."). Notes are parsed for the document, a birth cue and a date near it, with no fixed wording. Rejected or expired checks are ignored. If there is no verified DOB and the records give different DOBs, the DOB is treated as unknown rather than picking one. Support notes about where the customer lived or worked add countries.

## Finding the listed person

- DOB: the `dobs` field; otherwise the first paragraph of the profile notes ("born on ...", or an age at a date in many phrasings); otherwise web search results.
- Search results count only if they contain the listing phrase for the hit's category ("a politically exposed person" and so on), mention a country tied to the hit, and name the hit.
- Earliest dated report: only lines of the form `According to …; Month D, YYYY:`.
- Countries: `countries`, `nationality`, `citizenship`, the last part of each address, place of birth.

## Deciding

Clear only on a contradiction, in this order: entity type, deceased before screening, too young (under 16) or not yet incorporated at the earliest report, every hit DOB contradicted, verified legal name agrees with none of the hit's names, no country in common. A country difference never clears a hit whose name and DOB agree.

Confirm a person on name + DOB with nothing contradicting, and a company on name + country. Anything else is REVIEW, and the reason says what is missing (no DOB on one side, names that can't be confirmed, and so on), so the analyst knows what would settle it.

## Evidence

Every fact carries the ID of the record it came from. The evidence list holds only the IDs behind the decisive facts: the KYC check or note for a DOB or name contradiction, the customer records and notes that supplied the countries for a location decision, and the search result when the hit's DOB came from the web.

## Stress test: does it survive new wording?

The unseen set has "differently worded free text", so we test for that directly. `tests/perturb.py` makes a copy of the dev data with the same facts in different words:

- every date in notes, profiles, search results, KYC checks and customer records rewritten in another format ("the 3rd of March 1990", "3-Mar-1990", "March 3, 1990", "1990/03/03")
- ages written as words ("he was forty-six", "a thirty-year-old")
- synonyms in onboarding notes ("D.O.B.", "date of birth", "birth date"; "authenticated" for "verified")

```
python3 tests/perturb.py dev /tmp/dev-reworded 1
system/run /tmp/dev-reworded /tmp/out.jsonl
```

On three reworded copies, all 819 decisions match the run on the original data, the practice score stays 50/50, and there are no unsafe clearances. The first version of this test found two real bugs (a birth year written alone, like "D.O.B. 1995", was missed, and the check date was read as a birth date). Both are fixed, and a birth date less than 10 years before the ID check is now rejected as implausible.

Numeric dates where day and month can't be told apart (05/06/1990) keep only the year. That way a US/UK date mix-up can never produce a false month mismatch, and so never a wrong clearance.

If a record is malformed and something throws, that hit alone goes to REVIEW with a warning on stderr. The run never crashes.

## Determinism

No randomness, no model calls, sorted iteration everywhere. Five runs give the same file.

## Review console

`system/console.py` turns the output into a one-page review console for analysts: the customer and the listed person side by side (name, birth date, countries, age at first report) with a ✓, ✕ or ? on each row, the decision and reason, the records cited, how the customer was found, and for every REVIEW what would settle it.

```
python3 system/console.py dev output/dev.jsonl console.html
```

The page embeds dataset records, so it stays local (`console.html` is in `.gitignore`).

## Three cases

**Clear mismatch (H-58A39C → DIFFERENT_ENTITY, DOB_MISMATCH).** The alert's account is joint, and the screened name and DOB pick CUS-604925. The latest approved check KYC-232AE0 gives 1965-03-28. The hit lists 1962-09-10. Three years apart, so it's a different person.

**Match (H-91AC66 → SAME_ENTITY, NAME_DOB_LOCATION_MATCH).** Account ACC-8AEABB → CUS-962814 → onboarding → approved check KYC-038F14: born 1994-11-01, Bangladesh. The hit is Emran Ali, 1994 or 1995, Bangladesh. Name, DOB and country agree, and nothing contradicts them.

**Left for review (H-FA9F83 → REVIEW, INSUFFICIENT_DATA).** Customer CUS-783545 and the hit Diana Cristian agree on name and on Moldova. But the hit gives no DOB anywhere: no `dobs`, nothing in the profile, no matching search result. Nothing contradicts it and nothing confirms it, so a person decides.

## Known limits

- Free-text parsing is rule-based. Wording far from anything tested (a check described without any birth cue, an age given only as "in his forties") is missed. When that happens the fact is unknown, which leads to REVIEW, not to a wrong clearance.
- Free-text country mentions can add a country that isn't really the customer's. That only makes a location clearance less likely, which is the safe direction.
