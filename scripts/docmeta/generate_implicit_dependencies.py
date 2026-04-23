import os
import sys
import re
from scripts.docmeta.docmeta import REPO_ROOT

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "implicit-dependencies.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    makefile_path = os.path.join(REPO_ROOT, "Makefile")
    deps = []

    if os.path.exists(makefile_path):
        with open(makefile_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_target = None
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('#'):
                continue

            # Regex to match targets with or without dependencies
            # Matches target names with alphanumeric, dashes, dots, underscores
            match = re.match(r'^([a-zA-Z0-9_.-]+):', line)
            if match:
                current_target = match.group(1).strip()
            elif current_target and line.startswith('\t'):
                # Extract python/bash commands as implicit dependencies
                if line_stripped.startswith('python3 -m '):
                    module = line_stripped.split('python3 -m ')[1].split()[0]
                    deps.append({
                        'source': 'Makefile',
                        'target': current_target,
                        'dependency': module,
                        'evidence': line_stripped,
                        'documented': '*unclear*'
                    })
                elif line_stripped.startswith('bash '):
                    script = line_stripped.split('bash ')[1].split()[0]
                    deps.append({
                        'source': 'Makefile',
                        'target': current_target,
                        'dependency': script,
                        'evidence': line_stripped,
                        'documented': '*unclear*'
                    })

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.implicit-dependencies\n")
        f.write("title: Implicit Dependencies\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("summary: Heuristische Karte impliziter Abhängigkeiten.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Implicit Dependencies\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> **Note:** This report uses Makefile-based heuristic inference to identify script execution dependencies. Documentation status validation is not yet fully automated here.\n\n")

        f.write("| Source | Inferred Dependency | Evidence | Documented |\n")
        f.write("| --- | --- | --- | --- |\n")
        if deps:
            for dep in deps:
                # evidence may contain markdown syntax which breaks table formatting
                # Escape any pipe characters
                evidence_text = dep['evidence'].replace('|', '\\|')
                evidence = f"`{evidence_text}`"
                f.write(f"| {dep['source']} ({dep['target']}) | {dep['dependency']} | {evidence} | {dep['documented']} |\n")
        else:
            f.write("| Makefile | docs-guard | `make docs-guard` | *unclear* |\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating implicit dependencies: {e}", file=sys.stderr)
    sys.exit(1)
