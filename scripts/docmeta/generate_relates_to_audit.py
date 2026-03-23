"""
Relates-To Audit Generator — semantic diagnosis of relates_to usage.

Read-only analysis that makes relates_to quality visible:
1. Dominance analysis: docs where >80% of relations are relates_to (with ≥5 total)
2. Missing direction: docs using only relates_to despite many connections
3. Supersedes gap detection: similar-named docs without supersedes links
4. Cluster analysis: connected components in the relates_to subgraph
5. Extreme dominance warnings: per-doc warnings at ≥90% relates_to
6. System dominance warning: global hint when >95% of all relations are relates_to
7. Negative examples: concrete relation lists from 2-3 docs for review
8. Review hints: contextual call-to-action when warnings exist
9. Delta tracking: compare current relates_to stats with previous run
10. Positive examples: docs using multiple relation types as orientation

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
EXTREME_DOMINANCE_RATIO = 0.9
SYSTEM_DOMINANCE_THRESHOLD = 0.95
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


def generate_system_dominance_warning(type_dist, total_rels):
    """
    Generate a system-level warning if relates_to dominates globally.

    Returns warning string or None.
    """
    if total_rels == 0:
        return None
    rt_count = type_dist.get("relates_to", 0)
    rt_ratio = rt_count / total_rels
    if rt_ratio > SYSTEM_DOMINANCE_THRESHOLD:
        return (
            f"relates_to dominiert das System stark ({rt_ratio*100:.0f}% aller Relationen). "
            "Dies kann ein Hinweis auf semantische Unterbestimmung sein."
        )
    return None


def find_extreme_dominance_docs(doc_counts):
    """
    Find docs with extreme relates_to dominance (≥90%) for per-doc warnings.

    Returns:
        list of (doc, relates_to_count, total_count, ratio) sorted by relates_to_count desc
    """
    results = []
    for doc, counts in doc_counts.items():
        total = counts["total"]
        rt = counts["relates_to"]
        if total >= MIN_RELATIONS_FOR_DOMINANCE and total > 0:
            ratio = rt / total
            if ratio >= EXTREME_DOMINANCE_RATIO:
                results.append((doc, rt, total, ratio))
    results.sort(key=lambda x: -x[1])
    return results


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


def parse_previous_stats(out_file):
    """
    Parse the previous relates-to-audit.md to extract stats for delta tracking.

    Returns:
        dict with keys 'total', 'relates_to', 'relates_to_pct' or None if unavailable
    """
    if not os.path.exists(out_file):
        return None

    try:
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    stats = {}
    # Match "| Relationen gesamt | 140 |"
    total_match = re.search(r"\| Relationen gesamt \| (\d+) \|", content)
    if total_match:
        stats["total"] = int(total_match.group(1))

    # Match "| — relates_to | 139 |"
    rt_match = re.search(r"\| — relates_to \| (\d+) \|", content)
    if rt_match:
        stats["relates_to"] = int(rt_match.group(1))

    # Match "| relates_to Anteil | 99% |"
    pct_match = re.search(r"\| relates_to Anteil \| (\d+)% \|", content)
    if pct_match:
        stats["relates_to_pct"] = int(pct_match.group(1))

    if "total" in stats and "relates_to" in stats:
        return stats
    return None


def compute_delta(current_total, current_rt, previous_stats):
    """
    Compute delta between current and previous relates_to stats.

    Returns:
        dict with 'total_delta', 'rt_delta', 'message' or None if no previous data
    """
    if previous_stats is None:
        return None

    prev_total = previous_stats.get("total", 0)
    prev_rt = previous_stats.get("relates_to", 0)

    total_delta = current_total - prev_total
    rt_delta = current_rt - prev_rt

    if total_delta == 0 and rt_delta == 0:
        return {"total_delta": 0, "rt_delta": 0, "message": None}

    message = None
    if rt_delta > 0 and total_delta > 0:
        new_rt_ratio = rt_delta / total_delta if total_delta > 0 else 0
        if new_rt_ratio > SYSTEM_DOMINANCE_THRESHOLD:
            message = (
                f"relates_to-Anteil steigt — "
                f"{rt_delta} von {total_delta} neuen Relationen sind relates_to. "
                "Mögliche weitere Verallgemeinerung."
            )

    return {"total_delta": total_delta, "rt_delta": rt_delta, "message": message}


def find_positive_examples(doc_counts, edges):
    """
    Find docs that use multiple relation types as positive orientation.

    Selects docs that have at least 2 different relation types.

    Returns:
        list of (doc, {type: count}) sorted by total desc
    """
    results = []
    for doc, counts in doc_counts.items():
        types_used = sum(1 for t in ["relates_to", "depends_on", "supersedes"] if counts.get(t, 0) > 0)
        if types_used >= 2:
            type_breakdown = {}
            for t in ["relates_to", "depends_on", "supersedes"]:
                if counts.get(t, 0) > 0:
                    type_breakdown[t] = counts[t]
            results.append((doc, type_breakdown))
    results.sort(key=lambda x: -sum(x[1].values()))
    return results


def generate_review_hint(extreme_docs, direction_candidates):
    """
    Generate a review hint when warnings or candidates exist.

    Returns:
        list of doc paths that should be reviewed, or empty list
    """
    docs = set()
    for doc, _, _, _ in extreme_docs:
        docs.add(doc)
    for doc, _ in direction_candidates:
        docs.add(doc)
    return sorted(docs)


def write_output(edges, all_docs, doc_counts, dominant, direction_candidates,
                 supersedes_gaps, clusters, extreme_docs, system_warning,
                 negative_examples, positive_examples, delta, review_docs):
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

        # System-level dominance warning
        if system_warning:
            f.write(f"> ⚠️ **{system_warning}**\n\n")

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

        # 6. Extreme dominance warnings
        f.write("### Warnungen (extreme Dominanz)\n\n")
        f.write(f"> Dokumente mit ≥{MIN_RELATIONS_FOR_DOMINANCE} Relationen, davon ≥{EXTREME_DOMINANCE_RATIO*100:.0f}% relates_to.\n\n")
        if extreme_docs:
            for doc, rt, total, ratio in extreme_docs:
                f.write(f"- ⚠️ `{doc}` ({rt}/{total} = {ratio*100:.0f}% relates_to)\n")
                f.write("  Dieses Dokument nutzt fast ausschließlich relates_to. "
                        "Prüfe, ob einzelne Relationen präziser als depends_on oder supersedes modelliert werden sollten.\n")
            f.write("\n")
        else:
            f.write("_Keine extremen Dominanzen._\n\n")

        # 7. Negative examples
        f.write("### Konkrete Beispiele zur Prüfung\n\n")
        f.write("> Ausgewählte Dokumente mit ihren relates_to-Zielen. "
                "Diese könnten möglicherweise differenziert werden.\n\n")
        if negative_examples:
            for doc, rels in negative_examples:
                f.write(f"**`{doc}`**:\n\n")
                for target, rel_type in rels:
                    f.write(f"- {rel_type} → `{target}`\n")
                f.write("\n")
        else:
            f.write("_Keine Beispiele verfügbar._\n\n")

        # 8. Positive examples
        f.write("### Positive Beispiele (Orientierung)\n\n")
        f.write("> Dokumente, die mehrere Relationstypen nutzen — als Vorbild für differenzierte Modellierung.\n\n")
        if positive_examples:
            for doc, type_breakdown in positive_examples:
                parts = [f"{count}× {t}" for t, count in sorted(type_breakdown.items())]
                f.write(f"- `{doc}` — {', '.join(parts)}\n")
            f.write("\n")
        else:
            f.write("_Keine Dokumente mit mehreren Relationstypen gefunden._\n\n")

        # 9. Delta tracking
        f.write("### Entwicklung (Delta)\n\n")
        if delta and (delta["total_delta"] != 0 or delta["rt_delta"] != 0):
            f.write(f"| Metrik | Veränderung |\n")
            f.write(f"| --- | --- |\n")
            f.write(f"| Relationen gesamt | {delta['total_delta']:+d} |\n")
            f.write(f"| relates_to | {delta['rt_delta']:+d} |\n")
            f.write("\n")
            if delta.get("message"):
                f.write(f"> ⚠️ {delta['message']}\n\n")
        else:
            f.write("_Kein Vergleich mit vorherigem Lauf verfügbar oder keine Änderung._\n\n")

        # 10. Review hint
        f.write("### Prüfhinweis bei Änderungen\n\n")
        if review_docs:
            f.write("> Bei Änderungen an diesen Dokumenten: "
                    "prüfe aktiv, ob relates_to präzisiert werden kann.\n\n")
            for doc in review_docs:
                f.write(f"- `{doc}`\n")
            f.write("\n")
        else:
            f.write("_Keine Dokumente mit Prüfbedarf._\n\n")

        # 11. Disclaimer
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
        extreme_docs = find_extreme_dominance_docs(doc_counts)
        type_dist = compute_type_distribution(edges)
        system_warning = generate_system_dominance_warning(type_dist, len(edges))
        negative_examples = collect_negative_examples(edges, doc_counts)
        positive_examples = find_positive_examples(doc_counts, edges)
        out_file = os.path.join(REPO_ROOT, "docs", "_generated", "relates-to-audit.md")
        previous_stats = parse_previous_stats(out_file)
        rt_count = type_dist.get("relates_to", 0)
        delta = compute_delta(len(edges), rt_count, previous_stats)
        review_docs = generate_review_hint(extreme_docs, direction_candidates)
        out_file = write_output(edges, all_docs, doc_counts, dominant,
                                direction_candidates, supersedes_gaps, clusters,
                                extreme_docs, system_warning, negative_examples,
                                positive_examples, delta, review_docs)
        print(f"Generated {out_file}")
    except Exception as e:
        print(f"Error generating relates-to audit: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
