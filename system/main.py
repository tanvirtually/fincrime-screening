import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine

# Output contract (POLICY.md reason-code table). Every reason code belongs to exactly one decision.
REASONS_FOR = {
    "DIFFERENT_ENTITY": {"TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "LOCATION_MISMATCH",
                         "NAME_MISMATCH_VERIFIED", "ENTITY_TYPE_MISMATCH", "DECEASED"},
    "SAME_ENTITY": {"NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH", "NAME_LOCATION_MATCH"},
    "REVIEW": {"INSUFFICIENT_DATA", "AMBIGUOUS_CUSTOMER_RECORD"},
}
FIELDS = ("hit_id", "alert_id", "decision", "reason_code", "customer_record_id", "reason", "evidence")


def contract_problem(r):
    """Why a row breaks the output contract, or None if it's fine."""
    if r.get("decision") not in REASONS_FOR:
        return f"unknown decision {r.get('decision')!r}"
    if r.get("reason_code") not in REASONS_FOR[r["decision"]]:
        return f"reason code {r.get('reason_code')!r} does not belong to {r['decision']}"
    if not isinstance(r.get("evidence"), list) or not all(isinstance(e, str) for e in r["evidence"]):
        return "evidence is not a list of record IDs"
    if not isinstance(r.get("reason"), str) or not r["reason"].strip():
        return "empty reason"
    cid = r.get("customer_record_id")
    if cid is not None and not isinstance(cid, str):
        return "customer_record_id is not a string or null"
    return None


def safe_row(r):
    """Never ship a broken line: a row that breaks the contract goes to a human instead."""
    problem = contract_problem(r)
    if problem is None:
        return r
    print(f"warning: {r.get('hit_id')} sent to REVIEW, {problem}", file=sys.stderr)
    return {**r, "decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA",
            "evidence": [e for e in (r.get("evidence") or []) if isinstance(e, str)],
            "customer_record_id": r.get("customer_record_id") if isinstance(r.get("customer_record_id"), str) else None,
            "reason": "The automated check could not produce a valid decision for this hit. A person should review it."}


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: system/run <data folder> <output file>")
    rows = engine.run(sys.argv[1])
    os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        for r in rows:
            if "_error" in r:
                print(f"warning: {r['hit_id']} sent to REVIEW after error {r['_error']}", file=sys.stderr)
            r = safe_row(r)
            f.write(json.dumps({k: r.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
