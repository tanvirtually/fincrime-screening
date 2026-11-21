# Same Person or Not

When a bank screens its customers against sanctions and watchlists, it gets thousands of alerts that say "this name looks similar." Most are different people who happen to share a name. An analyst has to check each one by hand.

This system does that first check automatically. For every watchlist hit, it decides one of three things and explains why:

| Decision | What it means |
|---|---|
| **Different person** (`DIFFERENT_ENTITY`) | A hard fact rules the hit out, so it's cleared. |
| **Same person** (`SAME_ENTITY`) | Name and birth date (or, for a company, name and country) agree, and nothing contradicts them. It goes to the compliance team. |
| **Needs a human** (`REVIEW`) | The evidence can't settle it. An analyst looks at it, and the system says what's missing. |

The most expensive mistake is clearing someone who really is on the list. So the system only clears a hit when a fact contradicts it, and anything it's unsure about goes to a person.

## How to run it

```
system/run <data folder> <output file>
```

For example: `system/run dev output/dev.jsonl`

- **Needs:** Python 3 only. No extra packages, no internet, no AI model.
- **Time:** about 6 seconds for the full development set (819 hits, 72,000 customer records) on a laptop.
- **Cost:** nothing. There are no paid API calls.
- **Same answer every time:** it uses no randomness and no AI model, so repeated runs produce the same file, byte for byte.

## Results on the development set

| | |
|---|---|
| Practice answers | **50 out of 50 right**, with no wrong clearances |
| Reason code and customer record | right on all 50 |
| All 819 hits | 463 cleared (57%), 123 same person (15%), 233 sent to a human (28%) |
| Reworded copies of the data | 3 rewordings, all 819 decisions unchanged |
| Random spot check | 31 hits outside the practice set checked by hand, no wrong clearances |

## How it works

```
 Alert ──► 1. Find the customer ──► everything we know about them ─┐
            (follow the link, or                                    │
             search by name and birth date)                         ├─► 3. Decide ──► answer + reason + evidence
                                                                    │   (rule-outs first,
 Hit ────► 2. Gather the listed person's facts ────────────────────┘    then matches,
            (birth date, countries, reports)                            otherwise a human)
```

### 1. Find the customer

A customer's details are spread across five systems that don't share one ID: the customer records, accounts, onboarding, identity checks and support notes. The system pieces them together:

1. **Follow the alert's link.** That's an account number, a login name or an email address.
2. **If there's no link, search.** It looks for customers whose name, birth date, country and city fit what was screened.
3. **Join up records that belong to one person.** Records count as the same person if they share a phone number *and* the same birth date, or the same ID document number. A shared phone or address alone doesn't count, because family members often share them.
4. **Trust verified facts over typed ones.** The most recent *approved* ID check is the most reliable source for the legal name, birth date and document country. Rejected or expired checks are ignored. If there's no approved check and the records disagree on the birth date, it's treated as unknown rather than guessed.
5. **If several different people fit,** each is checked. If they'd get different answers, the hit goes to a human, marked as an unclear customer record.

### 2. Gather the listed person's facts

- **Birth date:** from the profile's birth-date field. Failing that, from the profile text ("born on…", or "aged 45 in March 2019", which means born in 1973 or 1974). Failing that, from web search results.
- **Web results are filtered hard.** Most are about other people with the same name. A result only counts if it describes the same kind of listing (for example "a politically exposed person"), mentions a country linked to the hit, and names the hit.
- **Countries:** from the profile's countries, nationality, citizenship, addresses and place of birth.
- **First report date:** from dated report lines in the profile, used to check whether the customer was even old enough at the time.

### 3. Decide

**Clear it only if a fact rules it out**, checked in this order:

1. One is a person and the other is a company.
2. The listed person died before the customer was screened.
3. The customer was under 16 (or the company didn't exist yet) at the first report.
4. Every birth date the listed person has is more than a year away from the customer's.
5. The customer's verified legal name doesn't match any of the listed person's names.
6. They have no country in common. This is **never** used when the name and birth date both match. That case goes to a human.

**Confirm it** when a person's name and birth date agree, or a company's name and country agree, and nothing contradicts them.

**Otherwise, a human reviews it.** The reason says what's missing (for example "the hit gives no date of birth"), so the analyst knows what would settle it.

### Matching names

Names are messy, so the comparison follows the organisers' rules (POLICY.md, rule 8):

- Capitals, accents, punctuation and anything in brackets are ignored. Single letters count as initials, not names.
- Known variants count as the same name (Muhammad, Mohammed, Mohamed, Md).
- Names written together or apart match (Abdulsalam and Abdul Salam; O'Brien, OBrien and O Brien).
- Small spelling differences are allowed: 1 letter for names of 4 to 6 letters, 2 for longer ones.
- Two names agree when at least two parts match, or every part of the shorter name matches. A shared "Mohammed" alone is not enough.
- Placeholders like N/A, TEST or UNKNOWN are ignored.

`tests/test_names.py` checks these rules on Irish, Bengali, Nepali and Tamil/Sri Lankan names.

### Identity, not risk

The system answers one question: *is this the same person?* It doesn't weigh how serious a listing is, or treat any name or country as more suspicious. Risk decisions belong to the compliance team, after identity is settled.

## Evidence

Every fact remembers which record it came from. Each answer lists only the records that decided it, for example:

- the ID check behind a birth-date mismatch
- the customer records and notes that gave the countries
- the search result, when the listed person's birth date came from the web

## Testing against new wording

The organisers test on unseen data with different wording, so we test for that directly. `tests/perturb.py` makes a copy of the data where the facts stay the same but the words change:

- dates in other formats ("the 3rd of March 1990", "3-Mar-1990", "1990/03/03")
- ages written as words ("he was forty-six")
- different phrasing in onboarding notes ("D.O.B.", "date of birth"; "authenticated" instead of "verified")

```
python3 tests/perturb.py dev /tmp/dev-reworded 1
system/run /tmp/dev-reworded /tmp/out.jsonl
```

On three reworded copies, all 819 decisions stay the same and the practice score stays 50/50.

This test also found real bugs, which are now fixed. A birth year written on its own ("D.O.B. 1995") was being missed, and the date of an ID check was being read as a birth date.

A date like 05/06/1990, where day and month could be either way round, keeps only the year. That way a UK/US date mix-up can never cause a wrong clearance.

If a record is broken and causes an error, that one hit goes to a human with a warning. The run never stops part-way.

## Review console

`system/console.py` builds a one-page review screen for analysts. It shows the customer and the listed person side by side (name, birth date, countries, age at first report), with a ✓, ✕ or ? on each row. Below that come the decision, the reason, the records used, how the customer was found and, for anything sent to a human, what would settle it.

```
python3 system/console.py dev output/dev.jsonl console.html
```

The page contains customer data, so it stays on your computer and isn't committed (`console.html` is in `.gitignore`).

## Three examples

**Clearly a different person (H-58A39C → DIFFERENT_ENTITY, DOB_MISMATCH).** The alert's account is shared by two people. The screened name and birth date point to customer CUS-604925. Their latest approved ID check (KYC-232AE0) says born 28 March 1965. The listed person was born 10 September 1962, more than two years earlier, so it's a different person.

**A match (H-91AC66 → SAME_ENTITY, NAME_DOB_LOCATION_MATCH).** The account leads to customer CUS-962814, whose approved ID check (KYC-038F14) says born 1 November 1994, Bangladesh. The listed person is Emran Ali, born 1994 or 1995, Bangladesh. Name, birth date and country all agree, and nothing contradicts them.

**Left for a human (H-FA9F83 → REVIEW, INSUFFICIENT_DATA).** Customer CUS-783545 and the listed person, Diana Cristian, share a name and a country (Moldova). But the listed person has no birth date anywhere: not in the profile and not in any matching search result. Nothing rules her out and nothing confirms her, so an analyst decides.

## Files

| File | What it does |
|---|---|
| `run` | The entry point: `system/run <data folder> <output file>` |
| `main.py` | Reads the data, runs the engine, writes one line per hit |
| `engine.py` | Finds the customer, gathers the hit's facts, makes the decision, writes the reason and evidence |
| `names.py` | Name matching (rule 8) |
| `dates.py` | Reads dates in many formats, including partial ones. An unknown part stays unknown |
| `countries.py` | Turns country codes, nationalities ("Nigerian") and addresses into one country name |
| `console.py`, `console_template.html` | The review console |

## Known limits

- Free text is read with rules, not an AI model. Very unusual wording (an age given only as "in his forties") can be missed. When that happens the fact is treated as unknown, which leads to a human review, not a wrong clearance.
- A country mentioned in a note can be added to a customer even if they only visited. That makes a location clearance less likely, which is the safe direction.
