import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict

ASCII_LOWER_TABLE = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)

def normalize_ascii_lower(value: str) -> str:
    return value.translate(ASCII_LOWER_TABLE)

def main():
    parser = argparse.ArgumentParser(description="Audit JSONL accounts for email uniqueness.")
    parser.add_argument("--accounts-jsonl", action="append", required=True, help="Path to accounts JSONL file.")
    parser.add_argument("--format", choices=["json"], default="json", help="Output format.")
    parser.add_argument("--fail-on-duplicates", action="store_true", help="Exit non-zero if duplicates are found.")
    
    args = parser.parse_args()

    findings = []
    
    summary = {
        "records_total": 0,
        "records_with_email": 0,
        "records_missing_email": 0,
        "records_null_email": 0,
        "records_empty_after_trim": 0,
        "records_invalid_json": 0,
        "records_non_object_json": 0,
        "records_missing_id": 0,
        "records_non_string_email": 0,
        "records_trim_changes_value": 0,
        "records_case_changes_value": 0,
        "duplicate_current_runtime_key_groups": 0,
        "duplicate_proposed_constraint_key_groups": 0
    }

    current_groups = defaultdict(list)
    proposed_groups = defaultdict(list)

    def finding_key(item: dict) -> tuple[str, int, str, str]:
        return (
            item.get("source_path", ""),
            int(item.get("line_number", -1)),
            str(item.get("id", "")),
            str(item.get("classifications", [""])[0]) if item.get("classifications") else ""
        )

    seen_finding_keys = set()

    def add_finding(item: dict) -> None:
        key = finding_key(item)
        if key not in seen_finding_keys:
            findings.append(item)
            seen_finding_keys.add(key)

    def add_classification(item: dict, classification: str) -> None:
        classes = item.setdefault("classifications", [])
        if classification not in classes:
            classes.append(classification)

    if args.accounts_jsonl:
        for path_str in args.accounts_jsonl:
            p = Path(path_str)
            if not p.is_file():
                print(f"File not found: {path_str}", file=sys.stderr)
                sys.exit(1)
            
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                            
                        summary["records_total"] += 1
                        
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            summary["records_invalid_json"] += 1
                            item_err = {
                                "source_path": path_str,
                                "line_number": line_num,
                                "classifications": ["invalid_json"]
                            }
                            add_finding(item_err)
                            continue

                        if not isinstance(data, dict):
                            summary["records_non_object_json"] += 1
                            item_err = {
                                "source_path": path_str,
                                "line_number": line_num,
                                "classifications": ["non_object_json"]
                            }
                            add_finding(item_err)
                            continue

                        id_val = data.get("id")
                        if id_val is None:
                            summary["records_missing_id"] += 1
                            item_err = {
                                "source_path": path_str,
                                "line_number": line_num,
                                "classifications": ["missing_id"]
                            }
                            add_finding(item_err)
                            continue
                            
                        id_str = str(id_val)

                        item = {
                            "source_path": path_str,
                            "line_number": line_num,
                            "id": id_str,
                            "classifications": []
                        }

                        if "email" not in data:
                            add_classification(item, "missing_email")
                            summary["records_missing_email"] += 1
                            add_finding(item)
                            continue
                            
                        raw_email = data["email"]
                        if raw_email is None:
                            add_classification(item, "null_email")
                            summary["records_null_email"] += 1
                            item["raw_email"] = None
                            add_finding(item)
                            continue

                        if not isinstance(raw_email, str):
                            add_classification(item, "non_string_email")
                            summary["records_non_string_email"] += 1
                            item["raw_email"] = raw_email
                            add_finding(item)
                            continue

                        item["raw_email"] = raw_email
                        summary["records_with_email"] += 1
                        
                        trimmed_email = raw_email.strip()
                        item["trimmed_email"] = trimmed_email
                        
                        if trimmed_email == "":
                            add_classification(item, "empty_after_trim")
                            summary["records_empty_after_trim"] += 1
                            add_finding(item)
                            continue
                            
                        if raw_email != trimmed_email:
                            summary["records_trim_changes_value"] += 1
                            
                        current_runtime_key = normalize_ascii_lower(raw_email)
                        proposed_constraint_key = normalize_ascii_lower(trimmed_email)
                        
                        if current_runtime_key != raw_email:
                            summary["records_case_changes_value"] += 1
                            
                        item["current_runtime_key"] = current_runtime_key
                        item["proposed_constraint_key"] = proposed_constraint_key
                        
                        current_groups[current_runtime_key].append(item)
                        proposed_groups[proposed_constraint_key].append(item)
            except Exception as e:
                print(f"Error reading file {path_str}: {e}", file=sys.stderr)
                sys.exit(1)

    duplicate_groups_out = {
        "current_runtime_key": [],
        "proposed_constraint_key": []
    }

    def sort_key(i):
        return (i["id"], i["source_path"], i["line_number"])

    # Process current runtime duplicates
    for key, items in sorted(current_groups.items()):
        if len(items) > 1:
            summary["duplicate_current_runtime_key_groups"] += 1
            sorted_items = sorted(items, key=sort_key)
            for i in sorted_items:
                add_classification(i, "duplicate_current_runtime_key")
                add_finding(i)

            duplicate_groups_out["current_runtime_key"].append({
                "key": key,
                "items": sorted_items
            })

    # Process proposed constraint duplicates
    for key, items in sorted(proposed_groups.items()):
        if len(items) > 1:
            summary["duplicate_proposed_constraint_key_groups"] += 1
            sorted_items = sorted(items, key=sort_key)
            for i in sorted_items:
                add_classification(i, "duplicate_proposed_constraint_key")
                add_finding(i)

            duplicate_groups_out["proposed_constraint_key"].append({
                "key": key,
                "items": sorted_items
            })

    # Sort all findings deterministically
    findings.sort(key=lambda x: (x.get("id", ""), x["source_path"], x["line_number"]))

    output = {
        "summary": summary,
        "policy": {
            "current_runtime_key": "ascii_lower(raw_email)",
            "proposed_constraint_key": "ascii_lower(trim(raw_email)) for non-empty emails"
        },
        "findings": findings,
        "duplicate_groups": duplicate_groups_out
    }

    if args.format == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.fail_on_duplicates and summary["duplicate_proposed_constraint_key_groups"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
