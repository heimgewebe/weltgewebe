import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "doc-coverage.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    registry_file = os.path.join(REPO_ROOT, "audit", "impl-registry.yaml")

    implementations = []
    if os.path.exists(registry_file):
        with open(registry_file, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        current_impl = None
        current_list_field = None

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if line.startswith('  - id:'):
                if current_impl:
                    implementations.append(current_impl)
                current_impl = {'id': line_stripped.split('id:')[1].strip()}
                current_list_field = None
            elif current_impl is not None:
                if line_stripped.startswith('path:'):
                    current_impl['path'] = line_stripped.split('path:')[1].strip()
                    current_list_field = None
                elif line_stripped.startswith('impl_type:'):
                    current_impl['impl_type'] = line_stripped.split('impl_type:')[1].strip()
                    current_list_field = None
                elif line_stripped.startswith('status:'):
                    current_impl['status'] = line_stripped.split('status:')[1].strip()
                    current_list_field = None
                elif line_stripped.startswith('documented_by:'):
                    current_list_field = 'documented_by'
                    current_impl[current_list_field] = []
                    val = line_stripped.split('documented_by:', 1)[1].strip()
                    if val == '[]':
                        current_list_field = None
                    elif val.startswith('[') and val.endswith(']'):
                        items = [x.strip() for x in val[1:-1].split(',') if x.strip()]
                        current_impl[current_list_field].extend(items)
                        current_list_field = None
                elif line_stripped.startswith('verified_by:'):
                    current_list_field = 'verified_by'
                    current_impl[current_list_field] = []
                    val = line_stripped.split('verified_by:', 1)[1].strip()
                    if val == '[]':
                        current_list_field = None
                    elif val.startswith('[') and val.endswith(']'):
                        items = [x.strip() for x in val[1:-1].split(',') if x.strip()]
                        current_impl[current_list_field].extend(items)
                        current_list_field = None
                elif line_stripped.startswith('supersedes:'):
                    current_list_field = None
                elif line_stripped.startswith('deprecated_by:'):
                    current_list_field = None
                elif line_stripped.startswith('- ') and current_list_field:
                    val = line_stripped[2:].strip()
                    current_impl[current_list_field].append(val)

        if current_impl:
            implementations.append(current_impl)

    coverage = {}
    for impl in implementations:
        impl_type = impl.get('impl_type', 'unknown')
        if impl_type not in coverage:
            coverage[impl_type] = {'total': 0, 'covered': 0}

        coverage[impl_type]['total'] += 1
        docs = impl.get('documented_by', [])

        # Verify that at least one documented_by target exists relative to repo root
        has_valid_doc = False
        for doc in docs:
            doc_path = doc.strip()
            # Strip quotes if present
            if (doc_path.startswith('"') and doc_path.endswith('"')) or (doc_path.startswith("'") and doc_path.endswith("'")):
                doc_path = doc_path[1:-1]
            if doc_path:
                full_path = os.path.join(REPO_ROOT, doc_path)
                if os.path.exists(full_path):
                    has_valid_doc = True
                    break

        if has_valid_doc:
            coverage[impl_type]['covered'] += 1

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.doc-coverage\n")
        f.write("title: Doc Coverage\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Automatisch generierter Report über die Dokumentationsabdeckung.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Doc Coverage\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> **Note:** Coverage is calculated based on `audit/impl-registry.yaml` and the verified existence of documents referenced in `documented_by`.\n\n")

        if not coverage:
            f.write("> (No implementations found in audit/impl-registry.yaml)\n\n")
            f.write("| Component | Coverage |\n")
            f.write("| --- | --- |\n")
            f.write("| Apps | unknown |\n")
            f.write("| Contracts | unknown |\n")
        else:
            f.write("| Component Type | Coverage | Total | Documented |\n")
            f.write("| --- | --- | --- | --- |\n")
            for impl_type, stats in sorted(coverage.items()):
                total = stats['total']
                covered = stats['covered']
                pct = int((covered / total) * 100) if total > 0 else 0
                f.write(f"| {impl_type.capitalize()} | {pct}% | {total} | {covered} |\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating doc coverage: {e}", file=sys.stderr)
    sys.exit(1)
