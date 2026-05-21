use std::collections::BTreeSet;

const ROUTE_SOURCE_FILES: &[&str] = &[
    include_str!("../src/routes/accounts.rs"),
    include_str!("../src/routes/auth.rs"),
    include_str!("../src/routes/edges.rs"),
    include_str!("../src/routes/health.rs"),
    include_str!("../src/routes/meta.rs"),
    include_str!("../src/routes/mod.rs"),
    include_str!("../src/routes/nodes.rs"),
    include_str!("../src/routes/query.rs"),
];

const CSRF_COVERED_MUTATING_ROUTES: &[(&str, &str)] = &[
    ("POST", "/auth/session/refresh"),
    ("POST", "/auth/logout-all"),
    ("DELETE", "/auth/devices/:id"),
    ("PUT", "/auth/me/email"),
    ("POST", "/auth/step-up/magic-link/request"),
    ("POST", "/auth/step-up/magic-link/consume"),
    ("POST", "/auth/passkeys/register/options"),
    ("PATCH", "/nodes/:id"),
];

const CSRF_EXEMPT_MUTATING_ROUTES: &[(&str, &str)] = &[
    // Dev login is explicitly feature-gated and intentionally kept outside the CSRF policy.
    ("POST", "/auth/dev/login"),
    // Magic-link request/consume are pre-session or redirect-driven entry points with their own flow handling.
    ("POST", "/auth/magic-link/request"),
    ("POST", "/auth/magic-link/consume"),
    // Logout intentionally remains exempt so a sign-out action can be executed without the CSRF middleware path.
    ("POST", "/auth/logout"),
];

fn collect_declared_mutating_routes() -> BTreeSet<(String, String)> {
    ROUTE_SOURCE_FILES
        .iter()
        .flat_map(|source| collect_mutating_routes_from_source(source))
        .collect()
}

fn collect_mutating_routes_from_source(source: &str) -> BTreeSet<(String, String)> {
    let mut routes = BTreeSet::new();
    let mut cursor = 0;

    while let Some(route_start_rel) = source[cursor..].find(".route(") {
        let route_start = cursor + route_start_rel;
        let open_paren = route_start + ".route".len();
        let Some(route_end) = find_matching_paren(source, open_paren) else {
            break;
        };

        if let Some(route) = extract_mutating_route(&source[route_start..route_end]) {
            routes.insert(route);
        }

        cursor = route_end;
    }

    routes
}

fn find_matching_paren(source: &str, open_paren: usize) -> Option<usize> {
    let bytes = source.as_bytes();
    let mut depth = 0usize;

    for (index, byte) in bytes.get(open_paren..)?.iter().enumerate() {
        match byte {
            b'(' => depth += 1,
            b')' => {
                depth = depth.checked_sub(1)?;
                if depth == 0 {
                    return Some(open_paren + index + 1);
                }
            }
            _ => {}
        }
    }

    None
}

fn extract_mutating_route(route_call: &str) -> Option<(String, String)> {
    let path_start = route_call.find('"')? + 1;
    let path_end = route_call[path_start..].find('"')? + path_start;
    let path = route_call[path_start..path_end].to_string();

    let method = if route_call.contains("axum::routing::delete(") || route_call.contains("delete(")
    {
        "DELETE"
    } else if route_call.contains("axum::routing::put(") || route_call.contains("put(") {
        "PUT"
    } else if route_call.contains("axum::routing::patch(") || route_call.contains("patch(") {
        "PATCH"
    } else if route_call.contains("axum::routing::post(") || route_call.contains("post(") {
        "POST"
    } else {
        return None;
    };

    Some((method.to_string(), path))
}

fn route_set(routes: &[(&str, &str)]) -> BTreeSet<(String, String)> {
    routes
        .iter()
        .map(|(method, path)| ((*method).to_string(), (*path).to_string()))
        .collect()
}

fn format_route_set(routes: &BTreeSet<(String, String)>) -> String {
    routes
        .iter()
        .map(|(method, path)| format!("{} {}", method, path))
        .collect::<Vec<_>>()
        .join(", ")
}

#[test]
fn csrf_mutating_route_drift_guard_matches_router_declarations() {
    let discovered_routes = collect_declared_mutating_routes();
    let covered_routes = route_set(CSRF_COVERED_MUTATING_ROUTES);
    let exempt_routes = route_set(CSRF_EXEMPT_MUTATING_ROUTES);
    let policy_routes = covered_routes
        .union(&exempt_routes)
        .cloned()
        .collect::<BTreeSet<_>>();

    let uncovered_routes = discovered_routes
        .difference(&policy_routes)
        .cloned()
        .collect::<BTreeSet<_>>();
    let stale_routes = policy_routes
        .difference(&discovered_routes)
        .cloned()
        .collect::<BTreeSet<_>>();

    assert!(
        uncovered_routes.is_empty(),
        "mutating route drift detected; add each new route to CSRF_COVERED_MUTATING_ROUTES or CSRF_EXEMPT_MUTATING_ROUTES: {}",
        format_route_set(&uncovered_routes)
    );

    assert!(
        stale_routes.is_empty(),
        "CSRF policy lists contain routes that are no longer declared: {}",
        format_route_set(&stale_routes)
    );
}
