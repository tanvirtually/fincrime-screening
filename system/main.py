import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: system/run <data folder> <output file>")
    rows = engine.run(sys.argv[1])
    os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        for r in rows:
            if "_error" in r:
                print(f"warning: {r['hit_id']} sent to REVIEW after error {r['_error']}", file=sys.stderr)
            f.write(json.dumps({k: r[k] for k in ("hit_id", "alert_id", "decision", "reason_code",
                                                  "customer_record_id", "reason", "evidence")},
                               ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
