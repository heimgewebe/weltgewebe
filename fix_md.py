with open("apps/api/PERFORMANCE_RATIONALE.md", "r") as f:
    text = f.read()

text = text.replace("# Performance Rationale: O(1) Lookups for Nodes and Edges\n\n\n## Issue", "# Performance Rationale: O(1) Lookups for Nodes and Edges\n\n## Issue\n")

with open("apps/api/PERFORMANCE_RATIONALE.md", "w") as f:
    f.write(text)
