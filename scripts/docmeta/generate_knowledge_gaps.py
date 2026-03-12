import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT, parse_frontmatter

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "knowledge-gaps.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    gaps_found = []
    docs_dir = os.path.join(REPO_ROOT, "docs")

    for root, dirs, files in os.walk(docs_dir):
        if "_generated" in dirs:
            dirs.remove("_generated")

        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, REPO_ROOT)

                frontmatter = parse_frontmatter(file_path)
                if frontmatter:
                    doc_gaps = []
                    for key in ['audit_gaps', 'todo', 'unknown']:
                        val = frontmatter.get(key)
                        if val is not None:
                            if isinstance(val, list):
                                for item in val:
                                    item_str = str(item)
                                    if item_str and item_str.strip():
                                        doc_gaps.append(f"[{key}] {item_str.strip()}")
                            else:
                                val_str = str(val)
                                if val_str.strip():
                                    doc_gaps.append(f"[{key}] {val_str.strip()}")

                    if doc_gaps:
                        doc_id = frontmatter.get('id', rel_path)
                        gaps_found.append({
                            'id': doc_id,
                            'path': rel_path,
                            'gaps': doc_gaps
                        })

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.knowledge-gaps\n")
        f.write("title: Knowledge Gaps\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Automatisch markierte Wissenslücken in der Repo-Landschaft.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Knowledge Gaps\n\n")
        f.write("Generated automatically. Do not edit.\n\n")

        if not gaps_found:
            f.write("- **No critical knowledge gaps reported.**\n")
        else:
            for item in sorted(gaps_found, key=lambda x: x['id']):
                f.write(f"### {item['id']}\n")
                f.write(f"Source: `{item['path']}`\n\n")
                for gap in item['gaps']:
                    f.write(f"- {gap}\n")
                f.write("\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating knowledge gaps: {e}", file=sys.stderr)
    sys.exit(1)
