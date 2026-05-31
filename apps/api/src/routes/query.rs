use axum::http::StatusCode;
use serde::Serialize;
use std::collections::HashMap;
use std::fmt::Write as _;

/// Upper bound for the `limit` query parameter on list endpoints, applied so a
/// single request cannot force an unbounded in-memory collection.
pub const MAX_PAGE_SIZE: usize = 1000;

pub fn parse_usize_param(
    params: &HashMap<String, String>,
    key: &str,
    default: usize,
) -> Result<usize, StatusCode> {
    match params.get(key) {
        Some(raw) => raw.parse().map_err(|_| StatusCode::BAD_REQUEST),
        None => Ok(default),
    }
}

/// Page metadata returned alongside `items` in cursor pagination mode.
///
/// `next_cursor` is serialised as `null` on the last page; `has_more` indicates
/// whether a further page exists. A `total` count is intentionally omitted:
/// clients only need `has_more` to continue walking. The current in-memory
/// implementation may materialise and sort the filtered references, but the
/// wire contract does not expose or require a total count.
#[derive(Debug, Serialize)]
pub struct PageMeta {
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub has_more: bool,
}

/// Envelope for cursor pagination: the page of `items` plus `page` metadata.
#[derive(Debug, Serialize)]
pub struct CursorPage<T> {
    pub items: Vec<T>,
    pub page: PageMeta,
}

/// Unified list response.
///
/// `Legacy` serialises as a bare JSON array, preserving the historical
/// `limit`/`offset` contract that existing clients and tests rely on. `Cursor`
/// serialises as the `{ "items": [...], "page": {...} }` envelope. The
/// `untagged` representation means the wire shape depends solely on whether the
/// caller opted into cursor mode.
#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum ListResponse<T> {
    Cursor(CursorPage<T>),
    Legacy(Vec<T>),
}

/// Encode an id into an opaque, URL-safe cursor token (lowercase hex of the
/// id's UTF-8 bytes). Clients MUST treat the token as opaque.
pub fn encode_cursor(id: &str) -> String {
    let mut out = String::with_capacity(id.len() * 2);
    for byte in id.bytes() {
        // Writing to a String is infallible.
        let _ = write!(out, "{byte:02x}");
    }
    out
}

/// Decode a cursor token produced by [`encode_cursor`] back into the id.
///
/// Returns `400 Bad Request` for any malformed token (odd length, non-hex
/// digits, or invalid UTF-8) so callers never paginate from a silently-wrong
/// anchor.
pub fn decode_cursor(token: &str) -> Result<String, StatusCode> {
    let bytes = token.as_bytes();
    if bytes.len() % 2 != 0 {
        return Err(StatusCode::BAD_REQUEST);
    }
    let mut decoded = Vec::with_capacity(bytes.len() / 2);
    let mut idx = 0;
    while idx < bytes.len() {
        let hi = hex_val(bytes[idx]).ok_or(StatusCode::BAD_REQUEST)?;
        let lo = hex_val(bytes[idx + 1]).ok_or(StatusCode::BAD_REQUEST)?;
        decoded.push((hi << 4) | lo);
        idx += 2;
    }
    String::from_utf8(decoded).map_err(|_| StatusCode::BAD_REQUEST)
}

fn hex_val(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

/// Determine pagination mode from query parameters.
///
/// Cursor mode is opt-in: it is active when `pagination=cursor` is set or when a
/// non-empty `cursor` token is present (matching the `?cursor=...&limit=...`
/// convention recommended in the optimisation report). Returns
/// `(cursor_mode, after_id)`, where `after_id` is the decoded anchor (exclusive
/// lower bound) or `None` for the first page. A present-but-malformed `cursor`
/// yields `400 Bad Request`.
pub fn parse_cursor_params(
    params: &HashMap<String, String>,
) -> Result<(bool, Option<String>), StatusCode> {
    let pagination_is_cursor = params
        .get("pagination")
        .map(|value| value == "cursor")
        .unwrap_or(false);

    match params.get("cursor") {
        Some(token) if !token.is_empty() => Ok((true, Some(decode_cursor(token)?))),
        // An explicit empty cursor means "start from the beginning" in cursor mode.
        Some(_) => Ok((true, None)),
        None => Ok((pagination_is_cursor, None)),
    }
}

/// Validate cursor mode pagination parameters.
///
/// In cursor mode, `limit` must be greater than 0 (cannot materialize a page
/// without a forward anchor). Returns `400 Bad Request` if validation fails.
pub fn validate_cursor_limit(cursor_mode: bool, limit: usize) -> Result<(), StatusCode> {
    if cursor_mode && limit == 0 {
        return Err(StatusCode::BAD_REQUEST);
    }
    Ok(())
}

/// Build a cursor page from references into a backing store.
///
/// The sorting contract is **stable id ascending** for every cursor endpoint.
/// `id_of` extracts the sort/cursor key; `project` maps each retained item to
/// the response shape (e.g. an account's public projection). The cursor anchors
/// on the last returned id, so the next page contains strictly larger ids and
/// can therefore never duplicate or skip an entry across a stable store.
///
/// **Precondition:** The caller must validate `limit > 0` in cursor mode via
/// [`validate_cursor_limit`] before calling this function. The caller passes
/// `limit` already clamped to [`MAX_PAGE_SIZE`].
pub fn cursor_page<I, O>(
    mut refs: Vec<&I>,
    limit: usize,
    after_id: Option<&str>,
    id_of: impl Fn(&I) -> &str,
    project: impl Fn(&I) -> O,
) -> CursorPage<O> {
    refs.sort_by(|&a, &b| id_of(a).cmp(id_of(b)));

    let start = match after_id {
        Some(anchor) => refs.partition_point(|&item| id_of(item) <= anchor),
        None => 0,
    };
    let rest = &refs[start..];
    let take = rest.len().min(limit);
    let has_more = take > 0 && rest.len() > take;

    let items: Vec<O> = rest[..take].iter().map(|&item| project(item)).collect();
    let next_cursor = if has_more {
        Some(encode_cursor(id_of(rest[take - 1])))
    } else {
        None
    };

    CursorPage {
        items,
        page: PageMeta {
            limit,
            next_cursor,
            has_more,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cursor_round_trips_including_non_ascii() {
        let id = "abc-123_äöü";
        let token = encode_cursor(id);
        assert!(token.bytes().all(|b| b.is_ascii_hexdigit()));
        assert_eq!(decode_cursor(&token).unwrap(), id);
    }

    #[test]
    fn decode_rejects_malformed_cursor() {
        // Non-hex digit.
        assert_eq!(decode_cursor("zz"), Err(StatusCode::BAD_REQUEST));
        // Odd length.
        assert_eq!(decode_cursor("abc"), Err(StatusCode::BAD_REQUEST));
    }

    #[test]
    fn parse_cursor_params_distinguishes_modes() {
        let legacy = HashMap::new();
        assert_eq!(parse_cursor_params(&legacy).unwrap(), (false, None));

        let mut opt_in = HashMap::new();
        opt_in.insert("pagination".to_string(), "cursor".to_string());
        assert_eq!(parse_cursor_params(&opt_in).unwrap(), (true, None));

        let mut with_cursor = HashMap::new();
        with_cursor.insert("cursor".to_string(), encode_cursor("x1"));
        assert_eq!(
            parse_cursor_params(&with_cursor).unwrap(),
            (true, Some("x1".to_string()))
        );

        let mut bad_cursor = HashMap::new();
        bad_cursor.insert("cursor".to_string(), "zz".to_string());
        assert_eq!(
            parse_cursor_params(&bad_cursor),
            Err(StatusCode::BAD_REQUEST)
        );
    }

    // Mirrors a real domain row (e.g. a Node): the id is a field, so `id_of`
    // borrows it and `project` clones the id — the same shape the endpoints use.
    struct Item {
        id: String,
    }

    fn item(id: &str) -> Item {
        Item { id: id.to_string() }
    }

    fn id_of(it: &Item) -> &str {
        &it.id
    }

    fn project(it: &Item) -> String {
        it.id.clone()
    }

    #[test]
    fn cursor_page_walks_in_id_order_without_gaps_or_duplicates() {
        // Deliberately unsorted input proves the helper sorts by id ascending.
        let data: Vec<Item> = ["c", "a", "e", "b", "d"].into_iter().map(item).collect();

        let p1 = cursor_page(data.iter().collect(), 2, None, id_of, project);
        assert_eq!(p1.items, vec!["a", "b"]);
        assert!(p1.page.has_more);
        let after1 = decode_cursor(p1.page.next_cursor.as_deref().unwrap()).unwrap();
        assert_eq!(after1, "b");

        let p2 = cursor_page(data.iter().collect(), 2, Some(&after1), id_of, project);
        assert_eq!(p2.items, vec!["c", "d"]);
        assert!(p2.page.has_more);
        let after2 = decode_cursor(p2.page.next_cursor.as_deref().unwrap()).unwrap();

        let p3 = cursor_page(data.iter().collect(), 2, Some(&after2), id_of, project);
        assert_eq!(p3.items, vec!["e"]);
        assert!(!p3.page.has_more);
        assert!(p3.page.next_cursor.is_none());
    }

    #[test]
    fn cursor_page_empty_store_reports_no_more() {
        let data: Vec<Item> = Vec::new();
        let page = cursor_page(data.iter().collect(), 10, None, id_of, project);
        assert!(page.items.is_empty());
        assert!(!page.page.has_more);
        assert!(page.page.next_cursor.is_none());
    }

    #[test]
    fn validate_cursor_limit_rejects_zero_in_cursor_mode() {
        // In cursor mode, limit=0 returns 400.
        assert_eq!(validate_cursor_limit(true, 0), Err(StatusCode::BAD_REQUEST));
        // In legacy mode, limit=0 is allowed (caller's responsibility).
        assert_eq!(validate_cursor_limit(false, 0), Ok(()));
        // In cursor mode, limit > 0 is allowed.
        assert_eq!(validate_cursor_limit(true, 1), Ok(()));
        assert_eq!(validate_cursor_limit(true, 100), Ok(()));
    }
}
