//! T006 Hybrid Search Ranking Engine.
//!
//! Hard Priority Order (Section 8 of architecture/semantic-search.md):
//! 1. Exact normalized title
//! 2. Exact normalized tag
//! 3. Title prefix
//! 4. Typo tolerance / Trigram similarity
//! 5. Full-text token match
//! 6. Semantic similarity (at most ONE (1) additional candidate appended)
//! 7. Stable tie-break by node_id ASC.

use std::collections::HashSet;
use unicode_normalization::UnicodeNormalization;

use crate::routes::nodes::Node;

pub const DEFAULT_SEMANTIC_MINIMUM_COSINE: f64 = 0.55;
pub const DEFAULT_SEMANTIC_MINIMUM_MARGIN: f64 = 0.015;
pub const SEMANTIC_APPEND_LIMIT: usize = 1;

#[derive(Debug, Clone)]
pub struct SearchQuery {
    pub raw: String,
    pub normalized: String,
}

impl SearchQuery {
    pub fn new(query: &str) -> Self {
        Self {
            raw: query.to_string(),
            normalized: normalize_query(query),
        }
    }
}

pub fn normalize_query(value: &str) -> String {
    value
        .nfkc()
        .collect::<String>()
        .to_lowercase()
        .trim()
        .to_owned()
}

pub fn cosine_similarity(v1: &[f64], v2: &[f64]) -> f64 {
    if v1.len() != v2.len() || v1.is_empty() {
        return 0.0;
    }
    let mut dot = 0.0;
    let mut norm1 = 0.0;
    let mut norm2 = 0.0;
    for (a, b) in v1.iter().zip(v2.iter()) {
        dot += a * b;
        norm1 += a * a;
        norm2 += b * b;
    }
    if norm1 <= 0.0 || norm2 <= 0.0 || !dot.is_finite() {
        0.0
    } else {
        dot / (norm1.sqrt() * norm2.sqrt())
    }
}

fn trigrams(s: &str) -> HashSet<String> {
    let padded = format!("  {} ", s);
    let chars: Vec<char> = padded.chars().collect();
    let mut set = HashSet::new();
    if chars.len() >= 3 {
        for i in 0..=chars.len() - 3 {
            set.insert(chars[i..i + 3].iter().collect());
        }
    }
    set
}

pub fn trigram_similarity(s1: &str, s2: &str) -> f64 {
    let t1 = trigrams(s1);
    let t2 = trigrams(s2);
    if t1.is_empty() || t2.is_empty() {
        return 0.0;
    }
    let intersection_count = t1.intersection(&t2).count();
    let union_count = t1.union(&t2).count();
    if union_count == 0 {
        0.0
    } else {
        intersection_count as f64 / union_count as f64
    }
}

fn max_trigram_score(query: &str, title: &str, tags: &[String], searchable_text: &str) -> f64 {
    let norm_q = normalize_query(query);
    let mut score = trigram_similarity(&norm_q, &normalize_query(title));
    for tag in tags {
        score = score.max(trigram_similarity(&norm_q, &normalize_query(tag)));
    }
    score = score.max(trigram_similarity(
        &norm_q,
        &normalize_query(searchable_text),
    ));
    score
}

#[derive(Debug, Clone)]
pub struct ScoredNode {
    pub node: Node,
    pub rank_class: u8,
    pub rank_score: f64,
    pub embedding: Option<Vec<f64>>,
}

/// Evaluates lexical rank class and score for a candidate document.
/// Returns None if candidate has no lexical match with query.
pub fn calculate_lexical_rank_class(
    query: &SearchQuery,
    title: &str,
    tags: &[String],
    searchable_text: &str,
) -> Option<(u8, f64)> {
    let q = &query.normalized;
    if q.is_empty() {
        return None;
    }

    let norm_title = normalize_query(title);
    let norm_tags: Vec<String> = tags.iter().map(|t| normalize_query(t)).collect();

    // 1. Class 0: Exact Title
    if norm_title == *q {
        return Some((0, 1.0));
    }

    // 2. Class 1: Exact Tag
    if norm_tags.iter().any(|t| t == q) {
        return Some((1, 1.0));
    }

    // 3. Class 2: Title Prefix
    if norm_title.starts_with(q) {
        let score = q.len() as f64 / norm_title.len().max(1) as f64;
        return Some((2, score));
    }

    // Trigram score over title, tags, text
    let tri_score = max_trigram_score(&query.raw, title, tags, searchable_text);

    // Full-text token match
    let q_tokens: Vec<&str> = q.split_whitespace().collect();
    let norm_searchable = normalize_query(searchable_text);
    let matched_count = q_tokens
        .iter()
        .filter(|&&tok| norm_searchable.contains(tok))
        .count();

    // 4. Class 3: Typo tolerance / Trigram. Hard priority requires every
    // qualifying trigram match to rank before full-text token matches.
    if tri_score >= 0.30 {
        return Some((3, tri_score));
    }

    // 5. Class 4: Full-text token match
    if matched_count > 0 {
        let score = matched_count as f64 / q_tokens.len().max(1) as f64;
        return Some((4, score));
    }

    None
}

/// Ranks eligible candidates lexically according to Section 8 priority classes:
/// Class 0 (Exact title) < Class 1 (Exact tag) < Class 2 (Prefix) < Class 3 (Trigram) < Class 4 (FTS).
/// Stable tie-breaks: rank_score DESC, node.id ASC.
pub fn rank_lexical(_query: &SearchQuery, candidates: Vec<ScoredNode>) -> Vec<ScoredNode> {
    let mut matched: Vec<ScoredNode> = candidates
        .into_iter()
        .filter(|item| item.rank_class <= 4)
        .collect();

    matched.sort_by(|a, b| {
        a.rank_class
            .cmp(&b.rank_class)
            .then_with(|| {
                b.rank_score
                    .partial_cmp(&a.rank_score)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| a.node.id.cmp(&b.node.id))
    });

    matched
}

/// Performs hybrid ranking and fusion.
///
/// Pre-conditions:
/// 1. `lexical_candidates` are already visible, authorized, filtered, and sorted lexically.
/// 2. `all_eligible_candidates` contains all visible, authorized, filtered candidates.
///
/// Post-conditions:
/// - Hard lexical precedence is preserved: exact title/tag/prefix/FTS rank order is maintained.
/// - At most ONE (1) additional semantic candidate is appended if query_vector is provided,
///   its cosine similarity >= `semantic_minimum_cosine`, and margin >= `semantic_minimum_margin`.
/// - Stable tie-breaks: node.id ASC.
pub fn rank_hybrid(
    query_vector: Option<&[f64]>,
    lexical_candidates: Vec<ScoredNode>,
    all_eligible_candidates: &[ScoredNode],
    semantic_minimum_cosine: f64,
    semantic_minimum_margin: f64,
) -> Vec<ScoredNode> {
    let mut result = lexical_candidates;
    let Some(q_vec) = query_vector else {
        return result;
    };

    let lexical_ids: HashSet<String> = result.iter().map(|item| item.node.id.clone()).collect();

    // Find semantic similarity for candidates not in lexical list
    let mut semantic_candidates: Vec<(ScoredNode, f64)> = Vec::new();

    for candidate in all_eligible_candidates {
        if lexical_ids.contains(&candidate.node.id) {
            continue;
        }
        if let Some(c_vec) = &candidate.embedding {
            let sim = cosine_similarity(q_vec, c_vec);
            if sim >= semantic_minimum_cosine {
                let mut scored = candidate.clone();
                scored.rank_class = 6;
                scored.rank_score = sim;
                semantic_candidates.push((scored, sim));
            }
        }
    }

    // Sort semantic candidates by cosine DESC, node.id ASC (stable tie-break)
    semantic_candidates.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.node.id.cmp(&b.0.node.id))
    });

    if !semantic_candidates.is_empty() {
        let (top_cand, top_score) = &semantic_candidates[0];
        let margin_ok = if semantic_candidates.len() > 1 {
            let second_score = semantic_candidates[1].1;
            (top_score - second_score) >= semantic_minimum_margin
        } else {
            true
        };

        if margin_ok {
            // Append exactly ONE semantic candidate
            result.push(top_cand.clone());
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routes::nodes::Location;

    fn test_node(id: &str, title: &str, tags: Vec<&str>) -> Node {
        Node {
            id: id.to_string(),
            kind: "Werkstatt".to_string(),
            title: title.to_string(),
            created_at: "2026-01-01T00:00:00Z".to_string(),
            updated_at: "2026-01-01T00:00:00Z".to_string(),
            created_by_account_id: None,
            summary: Some("Test summary".to_string()),
            info: Some("Test info".to_string()),
            tags: tags.into_iter().map(String::from).collect(),
            address: Some("Test str. 1".to_string()),
            location: Location {
                lat: 52.5,
                lon: 13.4,
            },
        }
    }

    #[test]
    fn exact_title_and_exact_tag_rank_before_prefix() {
        let q = SearchQuery::new("Fahrrad");

        let n1 = test_node("node-1", "Fahrrad", vec![]); // Exact title -> Class 0
        let n2 = test_node("node-2", "Werkstatt", vec!["Fahrrad"]); // Exact tag -> Class 1
        let n3 = test_node("node-3", "Fahrradhilfe", vec![]); // Prefix -> Class 2

        let (c1, _) = calculate_lexical_rank_class(&q, &n1.title, &n1.tags, "Fahrrad").unwrap();
        let (c2, _) =
            calculate_lexical_rank_class(&q, &n2.title, &n2.tags, "Werkstatt Fahrrad").unwrap();
        let (c3, _) =
            calculate_lexical_rank_class(&q, &n3.title, &n3.tags, "Fahrradhilfe").unwrap();

        assert_eq!(c1, 0);
        assert_eq!(c2, 1);
        assert_eq!(c3, 2);
    }


    #[test]
    fn pure_trigram_match_ranks_before_full_text_match() {
        let q = SearchQuery::new("Fahrrad gemeinschaftswerkstatt");
        let trigram = calculate_lexical_rank_class(
            &q,
            "Fahrrad gemeinschaftswerkstat",
            &[],
            "kein token treffer",
        )
        .expect("trigram match");
        let full_text = calculate_lexical_rank_class(
            &q,
            "Unverbundener Titel",
            &[],
            "Fahrrad",
        )
        .expect("full-text match");

        assert_eq!(trigram.0, 3);
        assert_eq!(full_text.0, 4);
        assert!(trigram.0 < full_text.0);
    }

    #[test]
    fn stable_tie_break_by_node_id() {
        let q = SearchQuery::new("Werkstatt");
        let n1 = test_node("node-b", "Werkstatt", vec![]);
        let n2 = test_node("node-a", "Werkstatt", vec![]);

        let scored = vec![
            ScoredNode {
                node: n1,
                rank_class: 0,
                rank_score: 1.0,
                embedding: None,
            },
            ScoredNode {
                node: n2,
                rank_class: 0,
                rank_score: 1.0,
                embedding: None,
            },
        ];

        let ranked = rank_lexical(&q, scored);
        assert_eq!(ranked[0].node.id, "node-a");
        assert_eq!(ranked[1].node.id, "node-b");
    }

    #[test]
    fn hybrid_ranking_appends_at_most_one_semantic_candidate() {
        let lexical = vec![ScoredNode {
            node: test_node("node-lexical", "Fahrrad", vec![]),
            rank_class: 0,
            rank_score: 1.0,
            embedding: Some(vec![1.0, 0.0]),
        }];

        let eligible = vec![
            lexical[0].clone(),
            ScoredNode {
                node: test_node("node-sem-1", "Radhilfe", vec![]),
                rank_class: 99,
                rank_score: 0.0,
                embedding: Some(vec![0.9, 0.1]),
            },
            ScoredNode {
                node: test_node("node-sem-2", "Zweirad", vec![]),
                rank_class: 99,
                rank_score: 0.0,
                embedding: Some(vec![0.8, 0.2]),
            },
        ];

        let query_vec = vec![1.0, 0.0];
        let ranked = rank_hybrid(Some(&query_vec), lexical, &eligible, 0.55, 0.015);

        // Lexical candidate plus AT MOST ONE semantic candidate = 2 candidates total
        assert_eq!(ranked.len(), 2);
        assert_eq!(ranked[0].node.id, "node-lexical");
        assert_eq!(ranked[1].node.id, "node-sem-1");
    }
}
