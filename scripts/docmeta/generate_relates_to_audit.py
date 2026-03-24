"""
Relates-To Audit Generator — structural observation of relates_to usage.

Read-only analysis that makes relates_to patterns visible:
1. Type distribution: summary of relation types across the repo
2. Supersedes gap detection: similar-named docs without supersedes links
3. Cluster analysis: connected components in the relates_to subgraph
4. Concrete examples: relation lists from docs with most relates_to for review

No quota-based warnings, no percentage thresholds, no feedback loops.
Pure structural observation.

Output: docs/_generated/relates-to-audit.md
"""

import os
import sys
from collections import defaultdict

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.relations_parser import extract_relations_from_content

MAX_NEGATIVE_EXAMPLES = 3

# Heuristic suffixes that suggest supersession
SUPERSESSION_SUFFIXES = ["-v2", "-v3", "-new", "-deprecated", "-legacy", "-alt", "-revised"]


def collect_relations_graph():
    """
    Walk all docs/*.md (excluding _generated) and build the relations graph.

    Returns:
        edges: list of (source, type, target) tuples
        all_docs: set of all doc paths found
    """
    docs_dir = os.path.join(REPO_ROOT, "docs")
    edges = []
    all_docs = set()

    for root, dirs, files in os.walk(docs_dir):
        if "_generated" in root:
            continue
        for file in files:
            if not file.endswith(".md"):
                continue
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, REPO_ROOT)
            all_docs.add(rel_path)

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            relations = extract_relations_from_content(content)
            for rel in relations:
                if not isinstance(rel, dict):
                    continue
                rel_type = rel.get("type", "")
                target = rel.get("target", "")
                if rel_type and target:
                    edges.append((rel_path, rel_type, target))

    return edges, all_docs


def compute_per_doc_type_counts(edges):
    """
    For each source document, count relations by type.

    Returns:
        dict: {doc: {"relates_to": n, "depends_on": n, "supersedes": n, "total": n}}
    """
    counts = defaultdict(lambda: {"relates_to": 0, "depends_on": 0, "supersedes": 0, "total": 0})
    for source, rel_type, _ in edges:
        if rel_type in counts[source]:
            counts[source][rel_type] += 1
        counts[source]["total"] += 1
    return dict(counts)


def find_supersedes_gaps(all_docs):
    """
    Phase 3: Find pairs of docs with similar names suggesting supersession.

    Heuristic: strip known suffixes and compare base names within same directory.

    Returns:
        list of (doc_a, doc_b, reason) tuples
    """
    gaps = []
    docs_by_dir = defaultdict(list)
    for doc in all_docs:
        dir_path = os.path.dirname(doc)
        docs_by_dir[dir_path].append(doc)

    for dir_path, docs in docs_by_dir.items():
        basenames = {}
        for doc in docs:
            name = os.path.basename(doc)
            stem = name.rsplit(".", 1)[0] if "." in name else name
            basenames[doc] = stem

        for doc_a in docs:
            stem_a = basenames[doc_a]
            for doc_b in docs:
                if doc_a >= doc_b:
                    continue
                stem_b = basenames[doc_b]
                reason = _check_supersession_pattern(stem_a, stem_b)
                if reason:
                    gaps.append((doc_a, doc_b, reason))

    gaps.sort()
    return gaps


def _check_supersession_pattern(stem_a, stem_b):
    """
    Check if two stems suggest a supersession relationship.

    Returns reason string or None.
    """
    for suffix in SUPERSESSION_SUFFIXES:
        if stem_b == stem_a + suffix:
            return f"'{stem_b}' looks like a revision of '{stem_a}' (suffix: {suffix})"
        if stem_a == stem_b + suffix:
            return f"'{stem_a}' looks like a revision of '{stem_b}' (suffix: {suffix})"
    return None


def find_relates_to_clusters(edges):
    """
    Phase 4: Build relates_to-only graph and find connected components.

    Returns:
        list of clusters, each cluster is a sorted list of doc paths,
        sorted by cluster size (largest first)
    """
    adj = defaultdict(set)
    nodes = set()
    for source, rel_type, target in edges:
        if rel_type == "relates_to":
            adj[source].add(target)
            adj[target].add(source)
            nodes.add(source)
            nodes.add(target)

    visited = set()
    clusters = []

    for node in sorted(nodes):
        if node in visited:
            continue
        # BFS to find connected component
        component = []
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in sorted(adj.get(current, [])):
                if neighbor not in visited:
                    queue.append(neighbor)
        if component:
            clusters.append(sorted(component))

    clusters.sort(key=lambda c: -len(c))
    return clusters


def compute_type_distribution(edges):
    """Count relations by type for the summary."""
    dist = defaultdict(int)
    for _, rel_type, _ in edges:
        dist[rel_type] += 1
    return dict(dist)


def collect_negative_examples(edges, doc_counts, max_examples=MAX_NEGATIVE_EXAMPLES):
    """
    Collect concrete relates_to relation lists from docs with high relates_to usage.

    Selects docs with the most relates_to relations to show as concrete examples.

    Returns:
        list of (doc, [(target, rel_type), ...]) tuples, max_examples entries
    """
    # Find docs with the most relates_to, preferring docs that are 100% relates_to
    candidates = []
    for doc, counts in doc_counts.items():
        rt = counts["relates_to"]
        if rt >= 2:
            candidates.append((doc, rt, counts["total"]))
    candidates.sort(key=lambda x: (-x[1], x[0]))

    # Collect relation details for top candidates
    examples = []
    for doc, _, _ in candidates[:max_examples]:
        rels = []
        for source, rel_type, target in edges:
            if source == doc:
                rels.append((target, rel_type))
        rels.sort()
        if rels:
            examples.append((doc, rels))

    return examples


def write_output(edges, all_docs, doc_counts, supersedes_gaps, clusters,
                 negative_examples):
    """Write the relates-to-audit.md output file."""
    out_file = os.path.join(REPO_ROOT, "docs", "_generated", "relates-to-audit.md")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    type_dist = compute_type_distribution(edges)
    total_rels = len(edges)
    rt_count = type_dist.get("relates_to", 0)
    rt_pct = (rt_count / total_rels * 100) if total_rels > 0 else 0

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.relates-to-audit\n")
        f.write("title: Relates-To Audit\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("summary: Strukturelle Beobachtung der relates_to-Nutzung — Typen, Cluster, Beispiele.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Relates-To Audit\n\n")
        f.write("Generated automatically. Do not edit.\n\n")

        # 1. Summary
        f.write("### Zusammenfassung\n\n")
        f.write("| Metrik | Wert |\n")
        f.write("| --- | --- |\n")
        f.write(f"| Relationen gesamt | {total_rels} |\n")
        for rel_type in sorted(type_dist.keys()):
            f.write(f"| — {rel_type} | {type_dist[rel_type]} |\n")
        f.write(f"| relates_to Anteil | {rt_pct:.0f}% |\n")
        f.write("\n")

        # 2. Supersedes gaps
        f.write("### Mögliche supersedes-Lücken\n\n")
        f.write("> Dokument-Paare mit namensähnlichen Mustern, die möglicherweise eine supersedes-Relation benötigen.\n\n")
        if supersedes_gaps:
            for doc_a, doc_b, reason in supersedes_gaps:
                f.write(f"- `{doc_a}` ↔ `{doc_b}` — {reason}\n")
            f.write("\n")
        else:
            f.write("_Keine Lücken erkannt._\n\n")

        # 3. Cluster analysis
        f.write("### Cluster-Analyse (relates_to)\n\n")
        f.write("> Zusammenhängende Gruppen im relates_to-Graphen.\n\n")
        if clusters:
            for i, cluster in enumerate(clusters):
                f.write(f"**Cluster {i+1}** ({len(cluster)} Dokumente):\n\n")
                for doc in cluster:
                    f.write(f"- `{doc}`\n")
                f.write("\n")
        else:
            f.write("_Keine Cluster gefunden._\n\n")

        # 4. Concrete examples
        f.write("### Konkrete Beispiele zur Prüfung\n\n")
        f.write("> Dokumente mit den meisten relates_to-Zielen und ihren konkreten Relationen.\n\n")
        if negative_examples:
            for doc, rels in negative_examples:
                f.write(f"**`{doc}`**:\n\n")
                for target, rel_type in rels:
                    f.write(f"- {rel_type} → `{target}`\n")
                f.write("\n")
        else:
            f.write("_Keine Beispiele verfügbar._\n\n")

        # 5. Disclaimer
        f.write("### Hinweise\n\n")
        f.write("- Alle Ergebnisse dienen der strukturellen Sichtbarmachung.\n")
        f.write("- `relates_to` ist kein Fehler — die Verteilung zeigt den aktuellen Stand.\n")
        f.write("- Keine automatischen Korrekturen werden vorgenommen.\n")

    return out_file


def main():
    """Main entry point for the relates-to audit generator."""
    try:
        edges, all_docs = collect_relations_graph()
        doc_counts = compute_per_doc_type_counts(edges)
        supersedes_gaps = find_supersedes_gaps(all_docs)
        clusters = find_relates_to_clusters(edges)
        negative_examples = collect_negative_examples(edges, doc_counts)
        out_file = write_output(edges, all_docs, doc_counts, supersedes_gaps,
                                clusters, negative_examples)
        print(f"Generated {out_file}")
    except Exception as e:
        print(f"Error generating relates-to audit: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
