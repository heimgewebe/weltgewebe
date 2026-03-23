"""
Relates-To Audit Generator — semantic diagnosis of relates_to usage.

Read-only analysis that makes relates_to quality visible:
1. Dominance analysis: docs where >80% of relations are relates_to (with ≥5 total)
2. Missing direction: docs using only relates_to despite many connections
3. Supersedes gap detection: similar-named docs without supersedes links
4. Cluster analysis: connected components in the relates_to subgraph

Output: docs/_generated/relates-to-audit.md
"""

import os
import re
import sys
from collections import defaultdict

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.validate_relations import extract_relations_from_content

# Thresholds
DOMINANCE_RATIO = 0.8
MIN_RELATIONS_FOR_DOMINANCE = 5
MIN_RELATIONS_FOR_DIRECTION = 5

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


def find_dominant_relates_to(doc_counts):
    """
    Phase 1: Find docs where >80% of relations are relates_to AND total ≥ 5.

    Returns:
        list of (doc, relates_to_count, total_count, ratio) sorted by relates_to_count desc
    """
    results = []
    for doc, counts in doc_counts.items():
        total = counts["total"]
        rt = counts["relates_to"]
        if total >= MIN_RELATIONS_FOR_DOMINANCE and total > 0:
            ratio = rt / total
            if ratio > DOMINANCE_RATIO:
                results.append((doc, rt, total, ratio))
    results.sort(key=lambda x: -x[1])
    return results


def find_direction_candidates(doc_counts):
    """
    Phase 2: Find docs using ONLY relates_to with ≥5 relations.

    Returns:
        list of (doc, relates_to_count) sorted by count desc
    """
    results = []
    for doc, counts in doc_counts.items():
        total = counts["total"]
        rt = counts["relates_to"]
        if total >= MIN_RELATIONS_FOR_DIRECTION and rt == total:
            results.append((doc, rt))
    results.sort(key=lambda x: -x[1])
    return results


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


def write_output(edges, all_docs, doc_counts, dominant, direction_candidates,
                 supersedes_gaps, clusters):
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
        f.write("summary: Semantik-Diagnose der relates_to-Nutzung — Dominanz, fehlende Richtung, Cluster.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Relates-To Audit\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> Alle Ergebnisse sind heuristisch — keine automatischen Korrekturen.\n\n")

        # 1. Summary
        f.write("### Zusammenfassung\n\n")
        f.write("| Metrik | Wert |\n")
        f.write("| --- | --- |\n")
        f.write(f"| Relationen gesamt | {total_rels} |\n")
        for rel_type in sorted(type_dist.keys()):
            f.write(f"| — {rel_type} | {type_dist[rel_type]} |\n")
        f.write(f"| relates_to Anteil | {rt_pct:.0f}% |\n")
        f.write("\n")

        # 2. Dominant relates_to docs
        f.write("### Auffällige Dokumente (relates_to-dominant)\n\n")
        f.write(f"> Dokumente mit ≥{MIN_RELATIONS_FOR_DOMINANCE} Relationen, davon >{DOMINANCE_RATIO*100:.0f}% relates_to.\n\n")
        if dominant:
            f.write("| Dokument | relates_to | gesamt | Anteil |\n")
            f.write("| --- | --- | --- | --- |\n")
            for doc, rt, total, ratio in dominant:
                f.write(f"| `{doc}` | {rt} | {total} | {ratio*100:.0f}% |\n")
            f.write("\n")
        else:
            f.write("_Keine auffälligen Dokumente._\n\n")

        # 3. Direction candidates
        f.write("### Kandidaten für präzisere Relationen\n\n")
        f.write(f"> Dokumente mit ≥{MIN_RELATIONS_FOR_DIRECTION} Relationen, die ausschließlich relates_to nutzen.\n\n")
        if direction_candidates:
            f.write("| Dokument | relates_to |\n")
            f.write("| --- | --- |\n")
            for doc, count in direction_candidates:
                f.write(f"| `{doc}` | {count} |\n")
            f.write("\n")
        else:
            f.write("_Keine Kandidaten gefunden._\n\n")

        # 4. Supersedes gaps
        f.write("### Mögliche supersedes-Lücken\n\n")
        f.write("> Heuristisch erkannte Dokument-Paare, die möglicherweise eine supersedes-Relation benötigen.\n\n")
        if supersedes_gaps:
            for doc_a, doc_b, reason in supersedes_gaps:
                f.write(f"- `{doc_a}` ↔ `{doc_b}` — {reason}\n")
            f.write("\n")
        else:
            f.write("_Keine Lücken erkannt._\n\n")

        # 5. Cluster analysis
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

        # 6. Disclaimer
        f.write("### Hinweise\n\n")
        f.write("- Alle Ergebnisse sind heuristisch und dienen der Sichtbarmachung.\n")
        f.write("- `relates_to` ist kein Fehler — aber es darf nicht zur Ausweichlösung für alles werden.\n")
        f.write("- Keine automatischen Korrekturen werden vorgenommen.\n")

    return out_file


def main():
    """Main entry point for the relates-to audit generator."""
    try:
        edges, all_docs = collect_relations_graph()
        doc_counts = compute_per_doc_type_counts(edges)
        dominant = find_dominant_relates_to(doc_counts)
        direction_candidates = find_direction_candidates(doc_counts)
        supersedes_gaps = find_supersedes_gaps(all_docs)
        clusters = find_relates_to_clusters(edges)
        out_file = write_output(edges, all_docs, doc_counts, dominant,
                                direction_candidates, supersedes_gaps, clusters)
        print(f"Generated {out_file}")
    except Exception as e:
        print(f"Error generating relates-to audit: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
