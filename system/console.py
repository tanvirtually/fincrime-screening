"""Build the analyst console: one self-contained HTML file for local viewing.

    python3 system/console.py <data folder> <output jsonl> <console.html>

The page embeds dataset details, so keep it local: don't commit or publish it.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dates as D
import engine as E


def next_step(row, person, items):
    if row["decision"] != "REVIEW":
        return None
    if row["reason_code"] == "AMBIGUOUS_CUSTOMER_RECORD":
        return "Confirm which customer this alert is about, then rerun. Each candidate leads to a different answer."
    if row["customer_record_id"] is None:
        return "Find the customer in the bank's systems. Nothing fits the screened details."
    steps = []
    if person and not person.dob:
        steps.append("Get a verified date of birth for the customer (KYC refresh)")
    if not items:
        steps.append("Find the listed person's date of birth in the provider's source documents")
    if person and not person.verified_name:
        steps.append("Check the customer's legal name against an ID document")
    if not steps:
        steps.append("Compare the full profile by hand: the facts neither match nor contradict")
    return ". ".join(steps) + "."


def compare_rows(data, alert, h, people, items):
    """Name / birth date / countries, customer vs hit, with agree / conflict / unknown."""
    if not people:
        return []
    rec, p = people[0]
    hn = E.hit_names(h)
    comp = p.company
    verified = p.verified_name
    pool = [verified] if verified else [n for n, _ in p.record_names]
    agree = E.N.any_agree(pool, hn, comp)
    name_state = "agree" if agree else ("conflict" if verified else "unknown")
    cust_name = verified or (pool[0] if pool else None)
    rel, _ = E.dob_relation(p.dob, items)
    hc = sorted(E.hit_countries(h))
    cc = sorted(p.countries)
    shared = sorted(set(cc) & set(hc))
    loc = "agree" if shared else ("conflict" if cc and hc else "unknown")
    out = [
        {"label": "Type", "cust": p.entity_type, "hit": h.get("entity_type"),
         "state": "agree" if p.entity_type == h.get("entity_type") else "conflict", "src": None},
        {"label": "Name", "cust": cust_name, "hit": agree[1] if agree else h.get("name"),
         "state": name_state, "src": p.verified_src if verified else (p.records[0] if p.records else None),
         "note": "from an approved ID check" if verified else "as typed on the account"},
        {"label": "Born" if not comp else "Incorporated", "cust": D.fmt(p.dob) if p.dob else None,
         "hit": "; ".join(E.fmt_years(i) for i in items) or None,
         "state": {"agree": "agree", "contradict": "conflict"}.get(rel, "unknown"), "src": p.dob_src},
        {"label": "Countries", "cust": ", ".join(cc) or None, "hit": ", ".join(hc) or None, "state": loc, "src": None},
    ]
    er = E.earliest_report(h)
    if er and p.dob and not comp:
        age = D.age_at(p.dob, er)
        out.append({"label": "Age at first report", "cust": f"at most {max(age, 0)}", "hit": D.fmt(er),
                    "state": "conflict" if age < 16 else "agree", "src": p.dob_src})
    if h.get("deceased_date"):
        out.append({"label": "Died", "cust": "screened " + alert["screened_at"], "hit": h["deceased_date"],
                    "state": "conflict", "src": None})
    return out


def build(folder, out_path):
    data = E.Data(folder)
    practice = {}
    pl = os.path.join(folder, "practice_labels.jsonl")
    if os.path.exists(pl):
        for l in open(pl, encoding="utf-8"):
            r = json.loads(l)
            practice[r["hit_id"]] = r["decision"]
    rows = {json.loads(l)["hit_id"]: json.loads(l) for l in open(out_path, encoding="utf-8")}
    alerts = []
    for a in data.alerts:
        resolved, path = E.resolve(data, a)
        people = [(rec, E.Person(data, m)) for rec, m in resolved]
        cust = []
        for rec, p in people:
            recs = []
            for r in p.records:
                c = data.customers[r]
                recs.append({k: c.get(k) for k in ("record_id", "full_name", "preferred_name", "dob", "nationality",
                                                   "residence_country", "city", "email", "phone", "status")})
            cust.append({
                "linked": rec, "records": recs,
                "check": ({"id": p.check["id"], "name": p.check.get("name"), "dob": D.fmt(p.check.get("dob")),
                           "country": p.check.get("country"), "date": p.check.get("date")} if p.check else None),
                "dob": D.fmt(p.dob) if p.dob else None, "dob_src": p.dob_src,
                "countries": {k: sorted(v) for k, v in sorted(p.countries.items())},
            })
        hits = []
        for hid in a["hit_ids"]:
            h = data.hits.get(hid)
            r = rows.get(hid)
            if not h or not r:
                continue
            items, src, ids = E.hit_dobs(data, h)
            er = E.earliest_report(h)
            rows_cmp = compare_rows(data, a, h, people, items)
            hits.append({
                "hit_id": hid, "name": h.get("name"), "type": h.get("entity_type"),
                "aliases": (h.get("aliases") or [])[:8],
                "category": h.get("primary_category") or (h.get("categories") or [None])[0],
                "dobs": [E.fmt_years(i) for i in items], "dob_src": src, "dob_ids": ids,
                "countries": sorted(E.hit_countries(h)),
                "earliest_report": D.fmt(er) if er else None,
                "deceased": h.get("deceased_date"),
                "position": h.get("position_or_allegation"),
                "decision": r["decision"], "code": r["reason_code"], "reason": r["reason"],
                "evidence": r["evidence"], "customer_record_id": r["customer_record_id"],
                "next": next_step(r, people[0][1] if len(people) == 1 else None, items),
                "rows": rows_cmp, "practice": practice.get(hid),
            })
        alerts.append({"alert_id": a["alert_id"], "screened_at": a["screened_at"], "screened": a["customer"],
                       "link": a.get("account_ref") or a.get("login_handle") or a.get("email"),
                       "link_kind": "account" if a.get("account_ref") else "login" if a.get("login_handle")
                       else "email" if a.get("email") else None,
                       "path": path, "customers": cust, "hits": hits})
    return alerts


def main():
    folder, out_path, html_path = sys.argv[1:4]
    alerts = build(folder, out_path)
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "console_template.html"), encoding="utf-8").read()
    payload = json.dumps(alerts, ensure_ascii=False).replace("</", "<\\/")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(tpl.replace("/*__DATA__*/[]", payload))
    print(f"wrote {html_path}: {len(alerts)} alerts")


if __name__ == "__main__":
    main()
