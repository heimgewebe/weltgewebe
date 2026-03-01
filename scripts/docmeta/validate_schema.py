import os
import sys
import json
import re

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def validate_data_against_schema(data, schema, path="root"):
    errors = []
    if schema.get("type") == "object":
        if not isinstance(data, dict):
            return [f"{path}: expected object, got {type(data).__name__}"]

        # Check required fields
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path}: missing required field '{req}'")

        # Check properties
        props = schema.get("properties", {})
        for k, v in data.items():
            if k in props:
                errors.extend(validate_data_against_schema(v, props[k], f"{path}.{k}"))
            elif not schema.get("additionalProperties", True):
                errors.append(f"{path}: unexpected property '{k}'")

    elif schema.get("type") == "string":
        if not isinstance(data, str):
            return [f"{path}: expected string, got {type(data).__name__}"]

        if "enum" in schema and data not in schema["enum"]:
            errors.append(f"{path}: '{data}' is not one of {schema['enum']}")

        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: length {len(data)} is less than minLength {schema['minLength']}")

        if "pattern" in schema and not re.match(schema["pattern"], data):
            errors.append(f"{path}: '{data}' does not match pattern {schema['pattern']}")

    elif schema.get("type") == "array":
        if not isinstance(data, list):
            return [f"{path}: expected array, got {type(data).__name__}"]

        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate_data_against_schema(item, schema["items"], f"{path}[{i}]"))

    return errors

def main():
    schema_path = os.path.join(REPO_ROOT, "contracts", "docmeta.schema.json")
    if not os.path.exists(schema_path):
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []

    zones = repo_index.get('zones', {})

    for zone_name, zone_data in zones.items():
        rel_zone_path = zone_data.get('path', '')
        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in canonical_docs:
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(zone_path, doc_file)

            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if frontmatter is None:
                errors.append(f"No valid frontmatter found in '{rel_file_path}'.")
                continue

            # ensure arrays are properly formatted lists if possible.
            # `depends_on` and `verifies_with` could be string parsed as strings by the basic yaml parser
            # Need to normalize them before validating

            for key in ["depends_on", "verifies_with"]:
                val = frontmatter.get(key)
                if isinstance(val, str):
                    if val.startswith('[') and val.endswith(']'):
                        frontmatter[key] = [v.strip() for v in val[1:-1].split(',') if v.strip()]
                    elif not val.strip():
                        frontmatter[key] = []
                    else:
                        frontmatter[key] = [val.strip()]
                elif val is None:
                    # let validation handle missing fields
                    pass

            validation_errors = validate_data_against_schema(frontmatter, schema, path="root")
            for err in validation_errors:
                errors.append(f"Schema violation in '{rel_file_path}': {err}")

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nDocmeta schema validation failed.", file=sys.stderr)
        sys.exit(1)

    print("Docmeta schema validation passed (0 errors).")

if __name__ == '__main__':
    main()
