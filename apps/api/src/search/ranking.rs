//! T006 hybrid search semantic append.
//!
//! The lexical prefix is authoritative PostgreSQL T003 output. This module does
//! not reimplement lexical scoring; it only preserves that order and may append
//! at most one confidence-gated semantic candidate with a stable node-id tie-break.

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

    pub fn embedding_text(&self) -> String {
        format!(
            "Aufgabe: Finde den relevantesten sichtbaren Weltgewebe-Knoten.\nAnfrage: {}",
            self.raw
        )
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

#[derive(Debug, Clone)]
pub struct ScoredNode {
    pub node: Node,
    pub rank_class: u8,
    pub rank_score: f64,
    pub embedding: Option<Vec<f64>>,
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
            has_authoritative_created_at: true,
            created_by_account_id: None,
            search_visibility: Default::default(),
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
    fn query_embedding_text_matches_t004_reference_contract() {
        let query = SearchQuery::new("Hilfe mit dem Telefon");
        assert_eq!(
            query.embedding_text(),
            "Aufgabe: Finde den relevantesten sichtbaren Weltgewebe-Knoten.\nAnfrage: Hilfe mit dem Telefon"
        );
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
